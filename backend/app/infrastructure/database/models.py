"""Normalized relational schema for cards and cached prices."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative schema base."""


class CardRecord(Base):
    """One language-specific printing in the internal card catalog."""

    __tablename__ = "cards"
    __table_args__ = (
        Index("ix_cards_number_name", "collector_number", "normalized_name"),
        Index("ix_cards_marketplace_id", "marketplace_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    collector_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    printed_total: Mapped[str | None] = mapped_column(String(32))
    set_name: Mapped[str] = mapped_column(String(180), nullable=False)
    rarity: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="English")
    reference_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    marketplace_id: Mapped[str] = mapped_column(String(80), nullable=False)
    marketplace_url: Mapped[str] = mapped_column(Text, nullable=False)
    visual_embedding: Mapped[bytes | None] = mapped_column(LargeBinary)


class PriceRecord(Base):
    """Latest successfully cached marketplace price for one card."""

    __tablename__ = "card_prices"

    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    source: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedbackRecord(Base):
    """User-confirmed recognition feedback; no upload bytes are retained."""

    __tablename__ = "recognition_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recognition_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    predicted_card_id: Mapped[str | None] = mapped_column(String(64))
    correct_card_id: Mapped[str | None] = mapped_column(String(64))
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
