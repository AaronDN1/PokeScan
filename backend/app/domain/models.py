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
    normalized_collector_number: str
    printed_total: str | None
    source: str
    source_card_id: str
    set_id: str
    set_name: str
    rarity: str | None
    language: str
    image_url: str
    marketplace_url: str | None = None
    reference_asset: str | None = None
    perceptual_hash: str | None = None
    orb_descriptors: bytes | None = None
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
    rotation_degrees: int = 0
    localization_score: float = 1.0
    detected_polygon: tuple[tuple[float, float], ...] = ()
    original_width: int = 0
    original_height: int = 0
    localization_ms: float = 0.0
    perspective_correction_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class OcrReading:
    """OCR text with a model confidence in the closed interval [0, 1]."""

    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class OrientationResult:
    """The selected card orientation and OCR outputs reused downstream."""

    image: NormalizedCardImage
    name: OcrReading
    collector_number: OcrReading
    score: float
    name_ocr_ms: float = 0.0
    collector_ocr_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class ArtworkEvidence:
    """Bounded visual signals for one catalog candidate."""

    perceptual_hash_score: float = 0.0
    orb_score: float = 0.0
    embedding_score: float = 0.0
    combined_score: float = 0.0


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """Independent evidence used to rank a catalog candidate."""

    card: Card
    collector_score: float
    name_score: float
    artwork_score: float
    ocr_quality: float
    suffix_score: float = 0.0
    localization_quality: float = 1.0
    blur_quality: float = 1.0
    perceptual_hash_score: float = 0.0
    orb_score: float = 0.0
    embedding_score: float = 0.0
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
    diagnostics: dict[str, object] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
