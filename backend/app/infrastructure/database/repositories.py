"""Database adapters for catalog search, cached pricing, and feedback."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.application.normalization import collector_similarity, name_similarity, suffix_similarity
from app.domain.models import Card, Price
from app.infrastructure.database.models import CardRecord, FeedbackRecord, PriceRecord


class SqlAlchemyCardRepository:
    """Retrieve a bounded candidate list through indexed catalog fields."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def search(
        self,
        *,
        normalized_name: str | None,
        collector_number: str | None,
        name_alternatives: tuple[str, ...] = (),
        collector_alternatives: tuple[str, ...] = (),
        limit: int,
    ) -> list[Card]:
        """Search by collector number or normalized name without image scans."""
        names = tuple(dict.fromkeys(item for item in (normalized_name, *name_alternatives) if item))
        numbers = tuple(
            dict.fromkeys(item for item in (collector_number, *collector_alternatives) if item)
        )
        clauses: list[ColumnElement[bool]] = []
        if numbers:
            clauses.append(CardRecord.normalized_collector_number.in_(numbers))
        if names:
            clauses.append(CardRecord.normalized_name.in_(names))
            searchable_tokens = sorted(
                {
                    token
                    for name in names
                    for token in name.split()
                    if len(token) >= 3 and token not in {"vmax", "vstar", "union"}
                },
                key=len,
                reverse=True,
            )[:3]
            clauses.extend(
                CardRecord.normalized_name.contains(token) for token in searchable_tokens
            )
        if not clauses:
            return []
        pool_limit = min(96, max(32, limit * 8))
        statement = select(CardRecord).where(or_(*clauses)).limit(pool_limit)
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        cards = [self._to_domain(record) for record in records]

        def relevance(card: Card) -> tuple[float, float, float]:
            collector_score = max(
                (collector_similarity(item, card.normalized_collector_number) for item in numbers),
                default=0.0,
            )
            name_score = max(
                (name_similarity(item, card.normalized_name) for item in names), default=0.0
            )
            suffix_score = max(
                (suffix_similarity(item, card.normalized_name) for item in names), default=0.0
            )
            return (
                0.52 * collector_score + 0.38 * name_score + 0.10 * suffix_score,
                collector_score,
                name_score,
            )

        cards.sort(key=relevance, reverse=True)
        return cards[:limit]

    async def get(self, card_id: str) -> Card | None:
        """Return one internal card without exposing ORM objects."""
        async with self._sessions() as session:
            record = await session.get(CardRecord, card_id)
        return self._to_domain(record) if record else None

    async def count(self) -> int:
        """Return the current local catalog size."""
        async with self._sessions() as session:
            return int(await session.scalar(select(func.count(CardRecord.id))) or 0)

    @staticmethod
    def _to_domain(record: CardRecord) -> Card:
        embedding = None
        if record.visual_embedding:
            embedding = tuple(
                float(value) for value in np.frombuffer(record.visual_embedding, dtype=np.float32)
            )
        return Card(
            id=record.id,
            name=record.name,
            normalized_name=record.normalized_name,
            collector_number=record.collector_number,
            normalized_collector_number=record.normalized_collector_number,
            printed_total=record.printed_total,
            source=record.source,
            source_card_id=record.source_card_id,
            set_id=record.set_id,
            set_name=record.set_name,
            rarity=record.rarity,
            language=record.language,
            image_url=record.reference_image_url,
            marketplace_url=record.marketplace_url,
            reference_asset=record.reference_asset,
            perceptual_hash=record.perceptual_hash,
            orb_descriptors=record.orb_descriptors,
            visual_embedding=embedding,
        )


class SqlAlchemyPriceProvider:
    """Read cached prices so recognition remains independent of marketplace uptime."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_price(self, card: Card) -> Price:
        """Return a null price when the cache has not been populated yet."""
        async with self._sessions() as session:
            record = await session.get(PriceRecord, card.id)
        if not record:
            return Price(amount=None)
        updated_at = record.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return Price(
            amount=record.amount,
            currency=record.currency,
            source=record.source,
            updated_at=updated_at,
        )


class SqlAlchemyFeedbackRepository:
    """Persist feedback identifiers while deliberately excluding image data."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def record(
        self,
        *,
        recognition_id: str,
        predicted_card_id: str | None,
        correct_card_id: str | None,
        is_correct: bool,
    ) -> None:
        """Commit one user feedback event."""
        item = FeedbackRecord(
            recognition_id=recognition_id,
            predicted_card_id=predicted_card_id,
            correct_card_id=correct_card_id,
            is_correct=is_correct,
            created_at=datetime.now(UTC),
        )
        async with self._sessions() as session:
            session.add(item)
            await session.commit()
