"""Typed public API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Card, Price, PricedCandidate, RecognitionResult


class PriceResponse(BaseModel):
    """A cached price that may be unavailable without failing recognition."""

    amount: float | None
    currency: str
    source: str | None
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, price: Price) -> PriceResponse:
        """Map a domain price to its wire representation."""
        return (
            cls(**price.__dict__)
            if hasattr(price, "__dict__")
            else cls(
                amount=price.amount,
                currency=price.currency,
                source=price.source,
                updated_at=price.updated_at,
            )
        )


class CardResponse(BaseModel):
    """Card details immediately useful to the scan result screen."""

    id: str
    name: str
    set_name: str
    collector_number: str
    printed_total: str | None
    rarity: str | None
    language: str
    image_url: str
    marketplace_url: str
    price: PriceResponse

    @classmethod
    def from_domain(cls, card: Card, price: Price) -> CardResponse:
        """Map a catalog card and cached price to the public contract."""
        return cls(
            id=card.id,
            name=card.name,
            set_name=card.set_name,
            collector_number=card.collector_number,
            printed_total=card.printed_total,
            rarity=card.rarity,
            language=card.language,
            image_url=card.image_url,
            marketplace_url=card.marketplace_url,
            price=PriceResponse.from_domain(price),
        )


class CandidateResponse(BaseModel):
    """A safe low-confidence alternative."""

    card: CardResponse
    confidence: float = Field(ge=0, le=1)

    @classmethod
    def from_domain(cls, candidate: PricedCandidate) -> CandidateResponse:
        """Map ranked evidence without exposing internal component scores."""
        return cls(
            card=CardResponse.from_domain(candidate.evidence.card, candidate.price),
            confidence=candidate.evidence.confidence,
        )


class RecognitionResponse(BaseModel):
    """The versioned recognition response consumed by the PWA."""

    model_config = ConfigDict(use_enum_values=True)

    recognition_id: str
    status: str
    card: CardResponse | None
    confidence: float = Field(ge=0, le=1)
    candidates: list[CandidateResponse]
    processing_ms: float = Field(ge=0)
    message: str | None

    @classmethod
    def from_domain(cls, result: RecognitionResult) -> RecognitionResponse:
        """Map the complete domain outcome to a stable response schema."""
        return cls(
            recognition_id=result.recognition_id,
            status=result.status.value,
            card=CardResponse.from_domain(result.card, result.price) if result.card else None,
            confidence=result.confidence,
            candidates=[CandidateResponse.from_domain(item) for item in result.candidates],
            processing_ms=result.processing_ms,
            message=result.message,
        )


class FeedbackRequest(BaseModel):
    """Explicit correction feedback containing no image data."""

    recognition_id: str = Field(min_length=36, max_length=36)
    predicted_card_id: str | None = Field(default=None, max_length=64)
    correct_card_id: str | None = Field(default=None, max_length=64)
    is_correct: bool


class HealthResponse(BaseModel):
    """Operational readiness without leaking credentials or filesystem paths."""

    status: str
    version: str
    database: str
    models: str
