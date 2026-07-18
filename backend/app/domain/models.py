"""Immutable data structures shared across the recognition domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class RecognitionStatus(StrEnum):
    """A recognition outcome that is safe for the client to render."""

    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNRECOGNIZED = "unrecognized"


@dataclass(frozen=True, slots=True)
class Price:
    """A cached marketplace price."""

    amount: float | None
    currency: str = "USD"
    source: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Card:
    """A normalized Pokémon card catalog entry."""

    id: str
    name: str
    normalized_name: str
    collector_number: str
    printed_total: str | None
    set_name: str
    rarity: str | None
    language: str
    image_url: str
    marketplace_url: str
    visual_embedding: tuple[float, ...] | None = None


@dataclass(frozen=True, slots=True)
class NormalizedCardImage:
    """One perspective-corrected card and the only regions used downstream."""

    width: int
    height: int
    card_jpeg: bytes
    top_region_jpeg: bytes
    bottom_region_jpeg: bytes
    artwork_region_jpeg: bytes
    blur_score: float


@dataclass(frozen=True, slots=True)
class OcrReading:
    """OCR text with a model confidence in the closed interval [0, 1]."""

    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """Independent evidence used to rank a catalog candidate."""

    card: Card
    collector_score: float
    name_score: float
    artwork_score: float
    ocr_quality: float
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class PricedCandidate:
    """A ranked candidate enriched with a non-blocking cached price."""

    evidence: CandidateEvidence
    price: Price = field(default_factory=lambda: Price(amount=None))


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """The complete application-layer recognition response."""

    recognition_id: str
    status: RecognitionStatus
    confidence: float
    card: Card | None
    price: Price
    candidates: tuple[PricedCandidate, ...]
    processing_ms: float
    message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
