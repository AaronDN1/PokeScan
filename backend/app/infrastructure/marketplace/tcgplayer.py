"""Exact TCGplayer product links and approved condition-level market prices."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlsplit

import httpx

from app.application.normalization import (
    collector_similarity,
    name_similarity,
    normalize_card_name,
    normalize_collector_number,
)
from app.domain.models import Card


@dataclass(frozen=True, slots=True)
class MarketplaceMapping:
    """A source-verified link from one catalog card to one marketplace product."""

    product_id: str | None
    product_url: str
    market_price: float | None = None
    printing_hint: str | None = None
    source_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConditionMarketPrices:
    """TCGplayer's recent SKU market prices for the requested conditions."""

    near_mint: float | None
    lightly_played: float | None
    moderately_played: float | None
    printing_name: str | None


def _numeric(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get("results", payload.get("Results"))
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


class PokemonTcgMarketplaceResolver:
    """Resolve exact cards through Pokémon TCG API's licensed TCGplayer links."""

    api_origin = "https://api.pokemontcg.io"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = client is None
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            headers=headers,
        )

    async def resolve(self, card: Card) -> MarketplaceMapping:
        """Return a direct product URL when possible and an exact search otherwise."""
        payload = await self._get_direct(card.source_card_id)
        if payload is None or not self._matches(card, payload):
            payload = await self._search(card)
        if payload is not None:
            mapping = await self._mapping(payload)
            if mapping is not None:
                return mapping
        return MarketplaceMapping(
            product_id=None,
            product_url=self._search_url(card),
        )

    async def _get_direct(self, source_card_id: str) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"{self.api_origin}/v2/cards/{quote(source_card_id, safe='')}"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        data = payload.get("data") if isinstance(payload, dict) else None
        return data if isinstance(data, dict) else None

    async def _search(self, card: Card) -> dict[str, Any] | None:
        query = (
            f'name:"{card.name.replace(chr(34), "")}" '
            f'number:"{card.collector_number.replace(chr(34), "")}" '
            f'set.name:"{card.set_name.replace(chr(34), "")}"'
        )
        try:
            response = await self._client.get(
                f"{self.api_origin}/v2/cards",
                params={"q": query, "pageSize": 20, "select": "id,name,number,set,tcgplayer"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return None
        candidates = [
            item
            for item in items
            if isinstance(item, dict) and self._matches(card, item)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: self._match_score(card, item))

    @staticmethod
    def _matches(card: Card, item: dict[str, Any]) -> bool:
        return PokemonTcgMarketplaceResolver._match_score(card, item) >= 2.35

    @staticmethod
    def _match_score(card: Card, item: dict[str, Any]) -> float:
        raw_set = item.get("set")
        set_data = raw_set if isinstance(raw_set, dict) else {}
        observed_number = normalize_collector_number(str(item.get("number", ""))) or ""
        expected_number = card.normalized_collector_number
        return (
            name_similarity(normalize_card_name(str(item.get("name", ""))), card.normalized_name)
            + collector_similarity(observed_number, expected_number)
            + name_similarity(
                normalize_card_name(str(set_data.get("name", ""))),
                normalize_card_name(card.set_name),
            )
        )

    async def _mapping(self, item: dict[str, Any]) -> MarketplaceMapping | None:
        raw_tcgplayer = item.get("tcgplayer")
        tcgplayer = raw_tcgplayer if isinstance(raw_tcgplayer, dict) else {}
        raw_url = tcgplayer.get("url")
        if not isinstance(raw_url, str):
            return None
        direct_url, product_id = await self._resolve_direct_url(raw_url)
        if direct_url is None:
            return None
        raw_prices = tcgplayer.get("prices")
        prices = raw_prices if isinstance(raw_prices, dict) else {}
        printing_hint, market_price = self._preferred_market(prices)
        source_updated_at = self._parse_updated_at(tcgplayer.get("updatedAt"))
        return MarketplaceMapping(
            product_id=product_id,
            product_url=direct_url,
            market_price=market_price,
            printing_hint=printing_hint,
            source_updated_at=source_updated_at,
        )

    async def _resolve_direct_url(self, raw_url: str) -> tuple[str | None, str | None]:
        current = raw_url
        for _attempt in range(5):
            parsed = urlsplit(current)
            hostname = parsed.hostname.casefold() if parsed.hostname else ""
            if hostname == "tcgplayer.com" or hostname.endswith(".tcgplayer.com"):
                match = re.search(r"/product/(\d+)", parsed.path)
                if match:
                    product_id = match.group(1)
                    return f"https://www.tcgplayer.com/product/{product_id}", product_id
                return f"https://www.tcgplayer.com{parsed.path}", None
            if hostname not in {"prices.pokemontcg.io", "pokemontcg.io"}:
                return None, None
            try:
                response = await self._client.get(current, follow_redirects=False)
            except httpx.HTTPError:
                return None, None
            location = response.headers.get("location")
            if not location or response.status_code not in {301, 302, 303, 307, 308}:
                return None, None
            current = urljoin(current, location)
        return None, None

    @staticmethod
    def _preferred_market(prices: dict[str, Any]) -> tuple[str | None, float | None]:
        priority = (
            ("normal", "Normal"),
            ("holofoil", "Holofoil"),
            ("reverseHolofoil", "Reverse Holofoil"),
            ("1stEditionNormal", "1st Edition Normal"),
            ("1stEditionHolofoil", "1st Edition Holofoil"),
        )
        for key, label in priority:
            value = prices.get(key)
            if isinstance(value, dict):
                market = _numeric(value.get("market"))
                if market is not None:
                    return label, market
        return None, None

    @staticmethod
    def _parse_updated_at(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        for pattern in ("%Y/%m/%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern).replace(tzinfo=UTC)
            except ValueError:
                continue
        return None

    @staticmethod
    def _search_url(card: Card) -> str:
        query = " ".join((card.name, card.collector_number, card.set_name))
        return "https://www.tcgplayer.com/search/pokemon/product?" + urlencode(
            {
                "productLineName": "pokemon",
                "q": query,
                "view": "grid",
            }
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class TcgPlayerConditionClient:
    """Use approved TCGplayer credentials for SKU-level market prices."""

    api_origin = "https://api.tcgplayer.com"

    def __init__(
        self,
        *,
        public_key: str | None,
        private_key: str | None,
        api_version: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._public_key = public_key
        self._private_key = private_key
        self._api_version = api_version.strip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(12.0))
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._printings: dict[int, str] | None = None

    @property
    def available(self) -> bool:
        return bool(self._public_key and self._private_key)

    async def get_condition_prices(
        self,
        product_id: str,
        *,
        preferred_printing: str | None,
    ) -> ConditionMarketPrices | None:
        if not self.available:
            return None
        skus = await self._get_results(f"catalog/products/{product_id}/skus")
        desired = [
            sku
            for sku in skus
            if int(sku.get("languageId", 0) or 0) == 1
            and int(sku.get("conditionId", 0) or 0) in {1, 2, 3}
        ]
        if not desired:
            return None
        printings = await self._get_printings()
        groups: dict[int, list[dict[str, Any]]] = {}
        for sku in desired:
            printing_id = int(sku.get("printingId", sku.get("variantId", 0)) or 0)
            groups.setdefault(printing_id, []).append(sku)
        selected_id = self._select_printing(groups, printings, preferred_printing)
        selected = groups[selected_id]
        sku_ids = [str(int(item["skuId"])) for item in selected if item.get("skuId")]
        if not sku_ids:
            return None
        market_rows = await self._get_results(f"pricing/sku/{','.join(sku_ids)}")
        by_sku = {
            int(item["skuId"]): _numeric(item.get("marketPrice"))
            for item in market_rows
            if item.get("skuId")
        }
        by_condition = {
            int(item["conditionId"]): by_sku.get(int(item["skuId"]))
            for item in selected
            if item.get("conditionId") and item.get("skuId")
        }
        return ConditionMarketPrices(
            near_mint=by_condition.get(1),
            lightly_played=by_condition.get(2),
            moderately_played=by_condition.get(3),
            printing_name=printings.get(selected_id),
        )

    @staticmethod
    def _select_printing(
        groups: dict[int, list[dict[str, Any]]],
        printings: dict[int, str],
        preferred: str | None,
    ) -> int:
        if preferred:
            normalized = normalize_card_name(preferred)
            for printing_id in groups:
                if normalize_card_name(printings.get(printing_id, "")) == normalized:
                    return printing_id
        return max(groups, key=lambda printing_id: len(groups[printing_id]))

    async def _get_printings(self) -> dict[int, str]:
        if self._printings is None:
            rows = await self._get_results("catalog/printings")
            self._printings = {
                int(item["printingId"]): str(item["name"])
                for item in rows
                if item.get("printingId") and item.get("name")
            }
        return self._printings

    async def _get_results(self, path: str) -> list[dict[str, Any]]:
        token = await self._get_token()
        response = await self._client.get(
            f"{self.api_origin}/{self._api_version}/{path}",
            headers={"Accept": "application/json", "Authorization": f"bearer {token}"},
        )
        response.raise_for_status()
        return _results(response.json())

    async def _get_token(self) -> str:
        if self._token and monotonic() < self._token_expires_at - 60:
            return self._token
        async with self._token_lock:
            if self._token and monotonic() < self._token_expires_at - 60:
                return self._token
            response = await self._client.post(
                f"{self.api_origin}/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._public_key,
                    "client_secret": self._private_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not isinstance(token, str):
                raise RuntimeError("TCGplayer did not return a bearer token.")
            expires_in = payload.get("expires_in", 3600)
            lifetime = float(expires_in) if isinstance(expires_in, int | float) else 3600.0
            self._token = token
            self._token_expires_at = monotonic() + max(120.0, lifetime)
            return token

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
