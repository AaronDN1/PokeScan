"""TCGdex v2 catalog provider with bounded, retryable HTTP access."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.application.normalization import normalize_card_name, normalize_collector_number


class CatalogProvider(Protocol):
    """Source-neutral card metadata provider used by the catalog builder."""

    name: str

    async def cards(self, *, limit: int | None = None) -> AsyncIterator[dict[str, Any]]:
        """Yield normalized card records."""
        ...


@dataclass(frozen=True, slots=True)
class TcgDexOptions:
    """Network and language options for a deterministic export."""

    language: str = "en"
    timeout_seconds: float = 25.0
    retries: int = 3
    concurrency: int = 12
    page_size: int = 100


class TcgDexCatalogProvider:
    """Read legitimate structured metadata and permitted card images from TCGdex."""

    name = "tcgdex"
    api_origin = "https://api.tcgdex.net/v2"

    def __init__(self, options: TcgDexOptions) -> None:
        self.options = options

    async def cards(self, *, limit: int | None = None) -> AsyncIterator[dict[str, Any]]:
        """Yield full normalized cards while bounding outstanding detail requests."""
        briefs = await self._list_cards(limit=limit)
        timeout = httpx.Timeout(self.options.timeout_seconds)
        limits = httpx.Limits(max_connections=self.options.concurrency)
        semaphore = asyncio.Semaphore(self.options.concurrency)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:

            async def fetch(brief: dict[str, Any]) -> dict[str, Any] | None:
                async with semaphore:
                    card_id = str(brief.get("id", ""))
                    if not card_id:
                        return None
                    try:
                        detail = await self._get_json(
                            client,
                            f"{self.api_origin}/{self.options.language}/cards/{card_id}",
                        )
                    except RuntimeError:
                        return None
                    return self._normalize(detail) if isinstance(detail, dict) else None

            batch_size = max(self.options.concurrency * 3, 24)
            for offset in range(0, len(briefs), batch_size):
                batch = briefs[offset : offset + batch_size]
                for item in await asyncio.gather(*(fetch(brief) for brief in batch)):
                    if item is not None:
                        yield item

    async def _list_cards(self, *, limit: int | None) -> list[dict[str, Any]]:
        timeout = httpx.Timeout(self.options.timeout_seconds)
        cards: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            page = 1
            while limit is None or len(cards) < limit:
                requested = self.options.page_size
                payload = await self._get_json(
                    client,
                    f"{self.api_origin}/{self.options.language}/cards",
                    params={
                        "pagination:page": page,
                        "pagination:itemsPerPage": requested,
                    },
                )
                if not isinstance(payload, list) or not payload:
                    break
                cards.extend(item for item in payload if isinstance(item, dict))
                if len(payload) < requested:
                    break
                page += 1
        return cards[:limit] if limit is not None else cards

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, int] | None = None,
    ) -> Any:
        error: Exception | None = None
        for attempt in range(self.options.retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as caught:
                error = caught
                if attempt + 1 < self.options.retries:
                    await asyncio.sleep(0.35 * (2**attempt))
        raise RuntimeError(
            f"TCGdex request failed after {self.options.retries} attempts"
        ) from error

    def _normalize(self, card: dict[str, Any]) -> dict[str, Any]:
        raw_set = card.get("set")
        set_data: dict[str, Any] = raw_set if isinstance(raw_set, dict) else {}
        set_id = str(set_data.get("id", "unknown"))
        source_card_id = str(card["id"])
        local_id = str(card.get("localId", "")).strip()
        image_base = card.get("image")
        official_total = None
        raw_card_count = set_data.get("cardCount")
        card_count: dict[str, Any] = (
            raw_card_count if isinstance(raw_card_count, dict) else {}
        )
        if card_count.get("official") is not None:
            official_total = str(card_count["official"])
        price = self._price(card.get("pricing"))
        return {
            "id": f"tcgdex:{self.options.language}:{set_id}:{source_card_id}",
            "source": self.name,
            "source_card_id": source_card_id,
            "set_id": set_id,
            "name": str(card.get("name", "Unknown")).strip(),
            "normalized_name": normalize_card_name(str(card.get("name", ""))),
            "collector_number": local_id,
            "normalized_collector_number": normalize_collector_number(local_id),
            "printed_total": official_total,
            "set_name": str(set_data.get("name", "Unknown set")).strip(),
            "rarity": str(card["rarity"]) if card.get("rarity") is not None else None,
            "language": "English" if self.options.language == "en" else self.options.language,
            "reference_image_url": f"{image_base}/high.webp" if image_base else None,
            "marketplace_id": None,
            "marketplace_url": None,
            "price": price,
        }

    @staticmethod
    def _price(pricing: Any) -> dict[str, Any] | None:
        if not isinstance(pricing, dict):
            return None
        tcgplayer = pricing.get("tcgplayer")
        market = TcgDexCatalogProvider._find_numeric(tcgplayer, "marketPrice")
        if market is None:
            return None
        return {
            "amount": market,
            "currency": "USD",
            "source": "tcgplayer_via_tcgdex",
            "updated_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _find_numeric(value: Any, key: str) -> float | None:
        if isinstance(value, dict):
            candidate = value.get(key)
            if isinstance(candidate, int | float):
                return float(candidate)
            for nested in value.values():
                found = TcgDexCatalogProvider._find_numeric(nested, key)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = TcgDexCatalogProvider._find_numeric(nested, key)
                if found is not None:
                    return found
        return None
