"""The end-to-end single-card recognition use case."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from uuid import uuid4

from app.application.confidence import WeightedConfidenceEngine
from app.application.normalization import (
    collector_similarity,
    name_similarity,
    normalize_card_name,
    normalize_collector_number,
)
from app.domain.models import (
    CandidateEvidence,
    Price,
    PricedCandidate,
    RecognitionResult,
    RecognitionStatus,
)
from app.domain.ports import (
    ArtworkMatcher,
    CardLocator,
    CardRepository,
    ImageValidator,
    OcrEngine,
    PriceProvider,
)


class RecognizeCard:
    """Coordinate one deterministic recognition pass across replaceable ports."""

    def __init__(
        self,
        *,
        validator: ImageValidator,
        locator: CardLocator,
        ocr: OcrEngine,
        cards: CardRepository,
        artwork: ArtworkMatcher,
        prices: PriceProvider,
        confidence: WeightedConfidenceEngine,
        candidate_limit: int = 8,
    ) -> None:
        self._validator = validator
        self._locator = locator
        self._ocr = ocr
        self._cards = cards
        self._artwork = artwork
        self._prices = prices
        self._confidence = confidence
        self._candidate_limit = candidate_limit

    async def execute(self, *, payload: bytes, declared_mime: str) -> RecognitionResult:
        """Identify one card while keeping pricing and candidates bounded."""
        started = perf_counter()
        safe_payload = self._validator.validate(payload, declared_mime)
        normalized_image = self._locator.normalize(safe_payload)

        name_reading = self._ocr.read_name(normalized_image.top_region_jpeg)
        number_reading = self._ocr.read_collector_number(normalized_image.bottom_region_jpeg)
        normalized_name = normalize_card_name(name_reading.text) or None
        collector_number = normalize_collector_number(number_reading.text)

        candidates = await self._cards.search(
            normalized_name=normalized_name,
            collector_number=collector_number,
            limit=self._candidate_limit,
        )
        ocr_quality = max(0.0, min(1.0, (name_reading.confidence + number_reading.confidence) / 2))

        ranked: list[CandidateEvidence] = []
        for card in candidates:
            evidence = CandidateEvidence(
                card=card,
                collector_score=collector_similarity(collector_number, card.collector_number),
                name_score=name_similarity(normalized_name, card.normalized_name),
                artwork_score=self._artwork.score(normalized_image.artwork_region_jpeg, card),
                ocr_quality=ocr_quality,
            )
            ranked.append(replace(evidence, confidence=self._confidence.score(evidence)))

        ranked.sort(key=lambda item: item.confidence, reverse=True)
        status = self._confidence.classify([item.confidence for item in ranked])
        priced_items: list[PricedCandidate] = []
        for item in ranked[:3]:
            priced_items.append(
                PricedCandidate(evidence=item, price=await self._prices.get_price(item.card))
            )
        priced = tuple(priced_items)
        selected = priced[0] if status is RecognitionStatus.MATCHED and priced else None
        message = self._message_for(status)

        return RecognitionResult(
            recognition_id=str(uuid4()),
            status=status,
            confidence=ranked[0].confidence if ranked else 0.0,
            card=selected.evidence.card if selected else None,
            price=selected.price if selected else Price(amount=None),
            candidates=priced,
            processing_ms=round((perf_counter() - started) * 1000, 2),
            message=message,
        )

    @staticmethod
    def _message_for(status: RecognitionStatus) -> str | None:
        if status is RecognitionStatus.AMBIGUOUS:
            return "We found close matches, but the evidence is not strong enough to choose safely."
        if status is RecognitionStatus.UNRECOGNIZED:
            return (
                "We could not identify this card confidently. "
                "Try even light and keep every edge visible."
            )
        return None
