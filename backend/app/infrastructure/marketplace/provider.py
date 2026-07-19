"""Resilient marketplace enrichment with local caching and no scan dependency."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models import Card, Price
from app.infrastructure.database.models import PriceRecord, TcgPlayerQuoteRecord
from app.infrastructure.marketplace.tcgplayer import (
    PokemonTcgMarketplaceResolver,
    TcgPlayerConditionClient,
)


class CachedMarketplacePriceProvider:
    """Resolve and refresh exact-product prices while preserving cached fallbacks."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        resolver: PokemonTcgMarketplaceResolver,
        tcgplayer: TcgPlayerConditionClient,
        *,
        cache_hours: int = 12,
    ) -> None:
        self._sessions = sessions
        self._resolver = resolver
        self._tcgplayer = tcgplayer
        self._max_age = timedelta(hours=max(1, cache_hours))
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def official_condition_pricing_available(self) -> bool:
        """Report whether approved TCGplayer credentials were configured."""
        return self._tcgplayer.available

    async def get_price(self, card: Card) -> Price:
        """Return a fresh quote when possible and never make recognition fail."""
        quote, legacy = await self._load(card.id)
        if quote is not None and self._is_fresh(quote.refreshed_at):
            return self._to_domain(quote)

        lock = self._locks.setdefault(card.id, asyncio.Lock())
        async with lock:
            quote, legacy = await self._load(card.id)
            if quote is not None and self._is_fresh(quote.refreshed_at):
                return self._to_domain(quote)
            try:
                mapping = await self._resolver.resolve(card)
                conditions = (
                    await self._tcgplayer.get_condition_prices(
                        mapping.product_id,
                        preferred_printing=mapping.printing_hint,
                    )
                    if mapping.product_id and self._tcgplayer.available
                    else None
                )
                now = datetime.now(UTC)
                record = TcgPlayerQuoteRecord(
                    card_id=card.id,
                    product_id=mapping.product_id,
                    product_url=mapping.product_url,
                    printing_name=(
                        conditions.printing_name
                        if conditions and conditions.printing_name
                        else mapping.printing_hint
                    ),
                    market_price=mapping.market_price,
                    near_mint=conditions.near_mint if conditions else None,
                    lightly_played=conditions.lightly_played if conditions else None,
                    moderately_played=(conditions.moderately_played if conditions else None),
                    currency="USD",
                    source=("tcgplayer_api" if conditions else "pokemon_tcg_api"),
                    source_updated_at=(now if conditions else mapping.source_updated_at),
                    refreshed_at=now,
                )
                async with self._sessions() as session:
                    await session.merge(record)
                    await session.commit()
                return self._to_domain(record)
            except Exception:
                if quote is not None:
                    return self._to_domain(quote)
                if legacy is not None:
                    return self._legacy_to_domain(legacy)
                return Price(amount=None)

    async def _load(
        self,
        card_id: str,
    ) -> tuple[TcgPlayerQuoteRecord | None, PriceRecord | None]:
        async with self._sessions() as session:
            return (
                await session.get(TcgPlayerQuoteRecord, card_id),
                await session.get(PriceRecord, card_id),
            )

    def _is_fresh(self, refreshed_at: datetime) -> bool:
        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - refreshed_at <= self._max_age

    @staticmethod
    def _to_domain(record: TcgPlayerQuoteRecord) -> Price:
        updated_at = record.source_updated_at or record.refreshed_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return Price(
            amount=record.near_mint if record.near_mint is not None else record.market_price,
            currency=record.currency,
            source=record.source,
            updated_at=updated_at,
            near_mint=record.near_mint,
            lightly_played=record.lightly_played,
            moderately_played=record.moderately_played,
            product_id=record.product_id,
            marketplace_url=record.product_url,
            printing_name=record.printing_name,
        )

    @staticmethod
    def _legacy_to_domain(record: PriceRecord) -> Price:
        updated_at = record.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return Price(
            amount=record.amount,
            currency=record.currency,
            source=record.source,
            updated_at=updated_at,
        )

    async def close(self) -> None:
        await self._resolver.close()
        await self._tcgplayer.close()
