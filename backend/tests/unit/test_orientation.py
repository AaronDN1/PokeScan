import cv2
import numpy as np

from app.domain.models import NormalizedCardImage, OcrReading
from app.infrastructure.imaging.orientation import OcrOrientationResolver


def test_orientation_prefers_a_card_title_over_flavor_text() -> None:
    title_score = OcrOrientationResolver._score(
        OcrReading("Pikachu", 0.91),
        OcrReading("", 0.0),
        portrait=True,
    )
    sentence_score = OcrOrientationResolver._score(
        OcrReading("Several of these Pokémon gather their electricity", 0.97),
        OcrReading("", 0.0),
        portrait=True,
    )

    assert title_score > sentence_score


class _CountingOcr:
    def __init__(self, names: list[OcrReading]) -> None:
        self.names = names
        self.name_calls = 0
        self.collector_calls = 0

    def read_name(self, _region_jpeg: bytes) -> OcrReading:
        reading = self.names[min(self.name_calls, len(self.names) - 1)]
        self.name_calls += 1
        return reading

    def read_collector_number(self, _region_jpeg: bytes) -> OcrReading:
        self.collector_calls += 1
        return OcrReading("25/198", 0.91)


def _normalized_image() -> NormalizedCardImage:
    image = np.full((1039, 744, 3), 220, dtype=np.uint8)
    cv2.putText(image, "CARD", (100, 160), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 5)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    payload = encoded.tobytes()
    return NormalizedCardImage(744, 1039, payload, payload, payload, payload, 100.0)


def test_orientation_uses_two_ocr_calls_for_an_upright_card() -> None:
    ocr = _CountingOcr([OcrReading("Pikachu", 0.96)])

    result = OcrOrientationResolver(ocr).resolve(_normalized_image())

    assert result.image.rotation_degrees == 0
    assert ocr.name_calls == 1
    assert ocr.collector_calls == 1


def test_orientation_checks_upside_down_only_when_the_first_title_is_implausible() -> None:
    ocr = _CountingOcr(
        [
            OcrReading("Several of these Pokemon gather their electricity", 0.98),
            OcrReading("Pikachu", 0.94),
        ]
    )

    result = OcrOrientationResolver(ocr).resolve(_normalized_image())

    assert result.image.rotation_degrees == 180
    assert ocr.name_calls == 2
    assert ocr.collector_calls == 1
