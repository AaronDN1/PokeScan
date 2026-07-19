"""OCR-guided right-angle orientation selection for normalized cards."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter

from app.application.normalization import normalize_card_name, normalize_collector_number
from app.domain.models import NormalizedCardImage, OcrReading, OrientationResult
from app.domain.ports import OcrEngine
from app.infrastructure.imaging.regions import (
    RegionCrops,
    crop_relative,
    decode_image,
    encode_jpeg,
    rotate_card,
)


@dataclass(slots=True)
class _RotationObservation:
    degrees: int
    card_jpeg: bytes
    name_crop: bytes
    collector_crop: bytes
    artwork_crop: bytes
    name: OcrReading
    portrait: bool
    collector: OcrReading = OcrReading("", 0.0)
    score: float = 0.0


class OcrOrientationResolver:
    """Evaluate four rotations using only the two targeted OCR regions."""

    def __init__(self, ocr: OcrEngine, crops: RegionCrops | None = None) -> None:
        self._ocr = ocr
        self._crops = crops or RegionCrops()

    def resolve(self, image: NormalizedCardImage) -> OrientationResult:
        """Select the most text-plausible rotation and reuse its OCR results."""
        card = decode_image(image.card_jpeg)
        observations: list[_RotationObservation] = []
        name_ocr_ms = 0.0
        collector_ocr_ms = 0.0
        for degrees in (0, 90, 180, 270):
            rotated = rotate_card(card, degrees)
            name_crop = encode_jpeg(crop_relative(rotated, self._crops.name))
            collector_crop = encode_jpeg(crop_relative(rotated, self._crops.collector))
            artwork_crop = encode_jpeg(crop_relative(rotated, self._crops.artwork))
            started = perf_counter()
            name = self._ocr.read_name(name_crop)
            name_ocr_ms += (perf_counter() - started) * 1000
            observations.append(
                _RotationObservation(
                    degrees=degrees,
                    card_jpeg=encode_jpeg(rotated),
                    name_crop=name_crop,
                    collector_crop=collector_crop,
                    artwork_crop=artwork_crop,
                    name=name,
                    portrait=rotated.shape[0] >= rotated.shape[1],
                )
            )

        likely = sorted(
            observations,
            key=lambda item: self._score(
                item.name, OcrReading("", 0.0), portrait=item.portrait
            ),
            reverse=True,
        )[:2]
        for observation in likely:
            started = perf_counter()
            observation.collector = self._ocr.read_collector_number(
                observation.collector_crop
            )
            collector_ocr_ms += (perf_counter() - started) * 1000
        for observation in observations:
            observation.score = self._score(
                observation.name,
                observation.collector,
                portrait=observation.portrait,
            )

        selected = max(observations, key=lambda item: item.score)
        selected_card = decode_image(selected.card_jpeg)
        oriented = replace(
            image,
            width=selected_card.shape[1],
            height=selected_card.shape[0],
            card_jpeg=selected.card_jpeg,
            top_region_jpeg=selected.name_crop,
            bottom_region_jpeg=selected.collector_crop,
            artwork_region_jpeg=selected.artwork_crop,
            rotation_degrees=selected.degrees,
        )
        return OrientationResult(
            image=oriented,
            name=selected.name,
            collector_number=selected.collector,
            score=round(selected.score, 4),
            name_ocr_ms=round(name_ocr_ms, 2),
            collector_ocr_ms=round(collector_ocr_ms, 2),
        )

    @staticmethod
    def _score(name: OcrReading, collector: OcrReading, *, portrait: bool) -> float:
        normalized_name = normalize_card_name(name.text)
        letters = sum(character.isalpha() for character in normalized_name)
        words = len(normalized_name.split())
        excess_length = max(0, len(normalized_name) - 30)
        excess_words = max(0, words - 4)
        title_shape = max(0.05, 1.0 - excess_length / 30 - excess_words * 0.2)
        name_plausibility = (
            min(1.0, letters / 4) * title_shape if normalized_name else 0.0
        )
        collector_plausibility = 1.0 if normalize_collector_number(collector.text) else 0.0
        score = (
            0.42 * name.confidence * name_plausibility
            + 0.48 * collector.confidence * collector_plausibility
            + (0.10 if portrait else 0.0)
        )
        return max(0.0, min(1.0, score))
