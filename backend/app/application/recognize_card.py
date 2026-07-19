"""The end-to-end single-card recognition use case."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Sequence
from dataclasses import replace
from time import perf_counter
from uuid import uuid4

import structlog

from app.application.confidence import WeightedConfidenceEngine
from app.application.normalization import (
    collector_number_alternatives,
    collector_similarity,
    name_alternatives,
    name_similarity,
    normalize_card_name,
    normalize_collector_number,
    suffix_similarity,
)
from app.domain.models import (
    ArtworkEvidence,
    CandidateEvidence,
    Card,
    OrientationResult,
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
    OrientationResolver,
    PriceProvider,
    VisualCandidateFinder,
)

logger = structlog.get_logger()


class RecognizeCard:
    """Coordinate one bounded recognition pass across replaceable ports."""

    def __init__(
        self,
        *,
        validator: ImageValidator,
        locator: CardLocator,
        orientation: OrientationResolver,
        cards: CardRepository,
        visual_candidates: VisualCandidateFinder,
        artwork: ArtworkMatcher,
        prices: PriceProvider,
        confidence: WeightedConfidenceEngine,
        candidate_limit: int = 8,
    ) -> None:
        self._validator = validator
        self._locator = locator
        self._orientation = orientation
        self._cards = cards
        self._visual_candidates = visual_candidates
        self._artwork = artwork
        self._prices = prices
        self._confidence = confidence
        self._candidate_limit = candidate_limit

    async def execute(
        self,
        *,
        payload: bytes,
        declared_mime: str,
        include_diagnostics: bool = False,
    ) -> RecognitionResult:
        """Identify one card while keeping candidates and price reads bounded."""
        total_started = perf_counter()
        timings: dict[str, float] = {}

        started = perf_counter()
        safe_payload = self._validator.validate(payload, declared_mime)
        timings["validation"] = self._elapsed(started)

        started = perf_counter()
        localized = self._locator.normalize(safe_payload)
        timings["localization_and_warp"] = self._elapsed(started)
        timings["localization"] = localized.localization_ms
        timings["perspective_correction"] = localized.perspective_correction_ms

        started = perf_counter()
        orientation = self._orientation.resolve(localized)
        timings["orientation"] = self._elapsed(started)
        timings["name_ocr"] = orientation.name_ocr_ms
        timings["collector_ocr"] = orientation.collector_ocr_ms

        name_reading = orientation.name
        number_reading = orientation.collector_number
        normalized_name = normalize_card_name(name_reading.text) or None
        collector_number = normalize_collector_number(number_reading.text)
        possible_names = name_alternatives(name_reading.text)
        possible_numbers = collector_number_alternatives(number_reading.text)

        started = perf_counter()
        text_candidates, visual_candidates = await asyncio.gather(
            self._cards.search(
                normalized_name=normalized_name,
                collector_number=collector_number,
                name_alternatives=possible_names,
                collector_alternatives=possible_numbers,
                limit=self._candidate_limit,
            ),
            self._visual_candidates.search(
                orientation.image.card_jpeg,
                limit=self._candidate_limit,
            ),
        )
        candidates = self._merge_candidates(text_candidates, visual_candidates)
        timings["candidate_retrieval"] = self._elapsed(started)

        started = perf_counter()
        visual_scores = self._artwork.score_many(
            orientation.image.card_jpeg, candidates
        )
        timings["artwork_matching"] = self._elapsed(started)

        ocr_quality = max(
            0.0,
            min(1.0, (name_reading.confidence + number_reading.confidence) / 2),
        )
        blur_quality = max(0.0, min(1.0, orientation.image.blur_score / 180.0))
        ranked: list[CandidateEvidence] = []
        for card in candidates:
            visual = visual_scores.get(card.id, ArtworkEvidence())
            collector_score = max(
                (
                    collector_similarity(item, card.normalized_collector_number)
                    for item in possible_numbers
                    or ((collector_number,) if collector_number else ())
                ),
                default=0.0,
            )
            observed_names = possible_names or ((normalized_name,) if normalized_name else ())
            name_score = max(
                (name_similarity(item, card.normalized_name) for item in observed_names),
                default=0.0,
            )
            suffix_score = max(
                (suffix_similarity(item, card.normalized_name) for item in observed_names),
                default=0.0,
            )
            evidence = CandidateEvidence(
                card=card,
                collector_score=collector_score,
                name_score=name_score,
                artwork_score=visual.combined_score,
                ocr_quality=ocr_quality,
                suffix_score=suffix_score,
                localization_quality=orientation.image.localization_score,
                blur_quality=blur_quality,
                perceptual_hash_score=visual.perceptual_hash_score,
                orb_score=visual.orb_score,
                embedding_score=visual.embedding_score,
            )
            ranked.append(replace(evidence, confidence=self._confidence.score(evidence)))

        ranked.sort(key=lambda item: item.confidence, reverse=True)
        status = self._confidence.classify(ranked)

        started = perf_counter()
        priced_items = [
            PricedCandidate(evidence=item, price=await self._prices.get_price(item.card))
            for item in ranked[:3]
        ]
        timings["price_lookup"] = self._elapsed(started)
        priced = tuple(priced_items)
        selected = priced[0] if status is not RecognitionStatus.UNRECOGNIZED and priced else None
        processing_ms = round((perf_counter() - total_started) * 1000, 2)
        timings["total"] = processing_ms
        diagnostics = (
            self._diagnostics(
                orientation=orientation,
                normalized_name=normalized_name,
                collector_number=collector_number,
                ranked=ranked,
                timings=timings,
            )
            if include_diagnostics
            else None
        )
        logger.info(
            "recognition_timing",
            status=status.value,
            candidate_count=len(ranked),
            normalized_name=normalized_name,
            normalized_collector_number=collector_number,
            **{f"{key}_ms": value for key, value in timings.items()},
        )
        return RecognitionResult(
            recognition_id=str(uuid4()),
            status=status,
            confidence=ranked[0].confidence if ranked else 0.0,
            card=selected.evidence.card if selected else None,
            price=selected.price if selected else Price(amount=None),
            candidates=priced,
            processing_ms=processing_ms,
            message=self._message_for(status),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _elapsed(started: float) -> float:
        return round((perf_counter() - started) * 1000, 2)

    def _merge_candidates(
        self,
        text_candidates: Sequence[Card],
        visual_candidates: Sequence[Card],
    ) -> list[Card]:
        """Interleave independent retrieval paths so neither can crowd out the other."""
        text_items = list(text_candidates)
        visual_items = list(visual_candidates)
        merged: list[Card] = []
        seen: set[str] = set()
        for index in range(max(len(text_items), len(visual_items))):
            for source in (text_items, visual_items):
                if index >= len(source):
                    continue
                card = source[index]
                card_id = card.id
                if card_id in seen:
                    continue
                seen.add(card_id)
                merged.append(card)
                if len(merged) >= self._candidate_limit:
                    return merged
        return merged

    @staticmethod
    def _diagnostics(
        *,
        orientation: OrientationResult,
        normalized_name: str | None,
        collector_number: str | None,
        ranked: list[CandidateEvidence],
        timings: dict[str, float],
    ) -> dict[str, object]:
        image = orientation.image
        return {
            "original_size": [image.original_width, image.original_height],
            "detected_polygon": image.detected_polygon,
            "normalized_size": [image.width, image.height],
            "rotation_degrees": image.rotation_degrees,
            "raw_name_ocr": orientation.name.text,
            "normalized_name": normalized_name,
            "name_ocr_confidence": orientation.name.confidence,
            "raw_collector_ocr": orientation.collector_number.text,
            "normalized_collector_number": collector_number,
            "collector_ocr_confidence": orientation.collector_number.confidence,
            "images": {
                "normalized_card_jpeg": base64.b64encode(image.card_jpeg).decode("ascii"),
                "name_crop_jpeg": base64.b64encode(image.top_region_jpeg).decode("ascii"),
                "collector_crop_jpeg": base64.b64encode(image.bottom_region_jpeg).decode("ascii"),
            },
            "candidates": [
                {
                    "card_id": item.card.id,
                    "name_score": item.name_score,
                    "collector_score": item.collector_score,
                    "suffix_score": item.suffix_score,
                    "phash_score": item.perceptual_hash_score,
                    "orb_score": item.orb_score,
                    "embedding_score": item.embedding_score,
                    "final_confidence": item.confidence,
                }
                for item in ranked
            ],
            "timings_ms": timings,
        }

    @staticmethod
    def _message_for(status: RecognitionStatus) -> str | None:
        if status is RecognitionStatus.AMBIGUOUS:
            return "This is the most likely printing; a few alternatives remained close."
        if status is RecognitionStatus.UNRECOGNIZED:
            return (
                "We could not identify this card confidently. "
                "Try even light and keep every edge visible."
            )
        return None
