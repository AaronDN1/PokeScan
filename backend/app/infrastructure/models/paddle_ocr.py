"""CPU OCR adapter using pretrained PaddleOCR models through RapidOCR."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from app.application.normalization import normalize_card_name, normalize_collector_number
from app.domain.errors import RecognitionUnavailableError
from app.domain.models import OcrReading

ImageArray = NDArray[np.uint8]


class PaddleOcrEngine:
    """Run PP-OCRv6 once-initialized ONNX models on small card text crops."""

    backend_name = "paddle_ppocrv6_rapidocr"

    def __init__(self, *, model_type: str = "tiny", allow_download: bool = False) -> None:
        try:
            import rapidocr
            from rapidocr import ModelType, RapidOCR

            selected_name = "tiny" if model_type.casefold() == "tiny" else "small"
            model_dir = Path(rapidocr.__file__).resolve().parent / "models"
            required = (
                model_dir / f"PP-OCRv6_det_{selected_name}.onnx",
                model_dir / f"PP-OCRv6_rec_{selected_name}.onnx",
            )
            if not allow_download and not all(path.is_file() for path in required):
                raise RecognitionUnavailableError(
                    "Pretrained OCR assets are not initialized. Run bootstrap_dev.py."
                )
            selected_model = (
                ModelType.TINY if selected_name == "tiny" else ModelType.SMALL
            )
            self._engine: Any = RapidOCR(
                params={
                    "Det.model_type": selected_model,
                    "Rec.model_type": selected_model,
                }
            )
        except Exception as error:
            raise RecognitionUnavailableError(
                "The pretrained OCR backend could not be initialized. Run bootstrap_dev.py."
            ) from error

    def read_name(self, region_jpeg: bytes) -> OcrReading:
        """Read and choose the most name-like line from the upper card crop."""
        texts, scores = self._read(region_jpeg, grayscale=False)
        if not texts:
            return OcrReading(text="", confidence=0.0)
        ranked: list[tuple[float, str, float]] = []
        for text, confidence in zip(texts, scores, strict=True):
            normalized = normalize_card_name(text)
            letters = sum(character.isalpha() for character in normalized)
            non_names = {
                "hp",
                "basic",
                "basic pokemon",
                "basic pokémon",
                "stage 1",
                "stage 2",
            }
            if letters < 2 or normalized in non_names:
                continue
            digit_penalty = sum(character.isdigit() for character in normalized) * 0.035
            plausibility = min(0.22, letters * 0.018)
            ranked.append((confidence + plausibility - digit_penalty, text, confidence))
        if not ranked:
            return OcrReading(text=" ".join(texts), confidence=float(max(scores)))
        _, text, confidence = max(ranked, key=lambda item: item[0])
        return OcrReading(text=text.strip(), confidence=self._bounded(confidence))

    def read_collector_number(self, region_jpeg: bytes) -> OcrReading:
        """Read and choose the most collector-number-like line from the lower crop."""
        texts, scores = self._read(region_jpeg, grayscale=True)
        ranked: list[tuple[float, str, float]] = []
        for text, confidence in zip(texts, scores, strict=True):
            compact = re.sub(r"[\s|]+", "", text).upper()
            prefix = r"(?:TG|GG|SV|RC|SWSH|SM|XY|BW|DP|H)?"
            if not re.fullmatch(rf"{prefix}\d{{1,4}}(?:/{prefix}\d{{1,4}})?", compact):
                continue
            normalized = normalize_collector_number(text)
            if normalized is None:
                continue
            formatting_bonus = 0.18 if "/" in text or "|" in text else 0.08
            ranked.append((confidence + formatting_bonus, text, confidence))
        if not ranked:
            return OcrReading(text="", confidence=0.0)
        _, text, confidence = max(ranked, key=lambda item: item[0])
        return OcrReading(text=text.strip(), confidence=self._bounded(confidence))

    def _read(
        self, region_jpeg: bytes, *, grayscale: bool
    ) -> tuple[tuple[str, ...], tuple[float, ...]]:
        encoded = np.frombuffer(region_jpeg, dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None:
            return (), ()
        image = np.asarray(decoded, dtype=np.uint8)
        prepared = self._prepare(image, grayscale=grayscale)
        try:
            result = self._engine(prepared)
        except Exception as error:
            raise RecognitionUnavailableError("The pretrained OCR backend failed.") from error
        raw_texts: Sequence[str] | None = getattr(result, "txts", None)
        raw_scores: Sequence[float] | None = getattr(result, "scores", None)
        if not raw_texts or not raw_scores:
            return (), ()
        size = min(len(raw_texts), len(raw_scores))
        texts = tuple(str(item).strip() for item in raw_texts[:size] if str(item).strip())
        if len(texts) != size:
            pairs = [
                (str(text).strip(), float(score))
                for text, score in zip(raw_texts[:size], raw_scores[:size], strict=True)
                if str(text).strip()
            ]
            return tuple(item[0] for item in pairs), tuple(self._bounded(item[1]) for item in pairs)
        return texts, tuple(self._bounded(float(item)) for item in raw_scores[:size])

    @staticmethod
    def _prepare(image: ImageArray, *, grayscale: bool) -> ImageArray:
        height, width = image.shape[:2]
        scale = max(1.0, min(3.0, 96 / max(height, 1)))
        if scale > 1.0:
            image = np.asarray(
                cv2.resize(
                    image,
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    interpolation=cv2.INTER_CUBIC,
                ),
                dtype=np.uint8,
            )
        if grayscale:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            image = np.asarray(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), dtype=np.uint8)
        return image

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, value))
