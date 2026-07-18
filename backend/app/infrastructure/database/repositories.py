"""Database adapters for catalog search, cached pricing, and feedback."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
        limit: int,
    ) -> list[Card]:
        """Search by collector number or normalized name without image scans."""
        clauses = []
        if collector_number:
            clauses.append(CardRecord.collector_number == collector_number)
        if normalized_name:
            clauses.append(CardRecord.normalized_name.contains(normalized_name))
        if not clauses:
            return []
        statement = select(CardRecord).where(or_(*clauses)).limit(limit)
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        return [self._to_domain(record) for record in records]

    async def get(self, card_id: str) -> Card | None:
        """Return one internal card without exposing ORM objects."""
        async with self._sessions() as session:
            record = await session.get(CardRecord, card_id)
        return self._to_domain(record) if record else None

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
            printed_total=record.printed_total,
            set_name=record.set_name,
            rarity=record.rarity,
            language=record.language,
            image_url=record.reference_image_url,
            marketplace_url=record.marketplace_url,
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
