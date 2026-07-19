"""Ports implemented by infrastructure adapters.

The application layer depends only on these protocols. OCR, embeddings, data
stores, and pricing providers can therefore be replaced independently.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.models import (
    ArtworkEvidence,
    Card,
    NormalizedCardImage,
    OcrReading,
    OrientationResult,
    Price,
)


class ImageValidator(Protocol):
    """Validate an untrusted upload before expensive processing."""

    def validate(self, payload: bytes, declared_mime: str) -> bytes:
        """Return a safe canonical image payload or raise a domain error."""
        ...


class CardLocator(Protocol):
    """Locate, orient, and perspective-correct exactly one card."""

    def normalize(self, payload: bytes) -> NormalizedCardImage:
        """Return a single normalized card with specialized regions."""
        ...


class OcrEngine(Protocol):
    """Read card name and collector number from their dedicated regions."""

    def read_name(self, region_jpeg: bytes) -> OcrReading:
        """Read only the upper name region."""
        ...

    def read_collector_number(self, region_jpeg: bytes) -> OcrReading:
        """Read only the lower collector-number region."""
        ...


class OrientationResolver(Protocol):
    """Choose the upright normalized card while reusing OCR observations."""

    def resolve(self, image: NormalizedCardImage) -> OrientationResult:
        """Evaluate supported rotations and return one selected orientation."""
        ...


class CardRepository(Protocol):
    """Search the local catalog without scanning every reference image."""

    async def search(
        self,
        *,
        normalized_name: str | None,
        collector_number: str | None,
        name_alternatives: tuple[str, ...] = (),
        collector_alternatives: tuple[str, ...] = (),
        limit: int,
    ) -> Sequence[Card]:
        """Return a small candidate set using indexed text fields."""
        ...

    async def count(self) -> int:
        """Return the number of imported language-specific card printings."""
        ...

    async def get(self, card_id: str) -> Card | None:
        """Return one catalog card by internal identifier."""
        ...

    async def get_many(self, card_ids: Sequence[str]) -> Sequence[Card]:
        """Return a bounded ordered card sequence by stable internal IDs."""
        ...


class VisualCandidateFinder(Protocol):
    """Shortlist catalog cards from one full-card visual query."""

    async def search(self, card_jpeg: bytes, *, limit: int) -> Sequence[Card]:
        """Return a bounded global visual shortlist without ORB-scanning the catalog."""
        ...


class ArtworkMatcher(Protocol):
    """Compare a scan embedding with stored candidate embeddings."""

    def score(self, artwork_jpeg: bytes, card: Card) -> float:
        """Return cosine-derived similarity in the closed interval [0, 1]."""
        ...

    def score_many(
        self, artwork_jpeg: bytes, cards: Sequence[Card]
    ) -> dict[str, ArtworkEvidence]:
        """Compute scan features once and score a bounded candidate sequence."""
        ...


class PriceProvider(Protocol):
    """Provide cached pricing without making recognition depend on a marketplace."""

    async def get_price(self, card: Card) -> Price:
        """Return the freshest locally available price, including a null value."""
        ...


class FeedbackRepository(Protocol):
    """Persist explicit user feedback without retaining the uploaded image."""

    async def record(
        self,
        *,
        recognition_id: str,
        predicted_card_id: str | None,
        correct_card_id: str | None,
        is_correct: bool,
    ) -> None:
        """Store one feedback event containing identifiers only."""
        ...
