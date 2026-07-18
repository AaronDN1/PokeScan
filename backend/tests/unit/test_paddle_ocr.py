from types import SimpleNamespace

import cv2
import numpy as np

from app.infrastructure.models.paddle_ocr import PaddleOcrEngine


def _jpeg() -> bytes:
    ok, encoded = cv2.imencode(".jpg", np.full((80, 400, 3), 255, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


def _engine(texts: list[str], scores: list[float]) -> PaddleOcrEngine:
    engine = object.__new__(PaddleOcrEngine)
    engine._engine = lambda _image: SimpleNamespace(txts=texts, scores=scores)
    return engine


def test_name_reader_rejects_labels_and_preserves_real_confidence() -> None:
    reading = _engine(["Basic Pokémon", "Pikachu ex"], [0.99, 0.93]).read_name(_jpeg())
    assert reading.text == "Pikachu ex"
    assert reading.confidence == 0.93


def test_collector_reader_rejects_arbitrary_text_ending_in_a_digit() -> None:
    invalid = _engine(["Pokemon 8"], [0.98]).read_collector_number(_jpeg())
    valid = _engine(["GG44/GG70"], [0.91]).read_collector_number(_jpeg())
    assert invalid.text == ""
    assert invalid.confidence == 0.0
    assert valid.text == "GG44/GG70"
    assert valid.confidence == 0.91
