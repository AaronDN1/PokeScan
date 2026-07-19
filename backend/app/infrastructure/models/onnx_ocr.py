"""Small CTC OCR adapter for specialized card regions."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray
from PIL import Image

from app.domain.errors import RecognitionUnavailableError
from app.domain.models import OcrReading

_NAME_CHARSET = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.'-é♀♂"
_NUMBER_CHARSET = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"
FloatArray = NDArray[np.float32]


class _CtcRecognizer:
    def __init__(self, path: Path, charset: str) -> None:
        self._path = path
        self._charset = charset
        self._session: ort.InferenceSession | None = None

    def read(self, region_jpeg: bytes) -> OcrReading:
        if not self._path.is_file():
            raise RecognitionUnavailableError(
                "The local OCR model is not installed. See backend/models/README.md."
            )
        if self._session is None:
            self._session = ort.InferenceSession(
                str(self._path), providers=["CPUExecutionProvider"]
            )
        input_name = self._session.get_inputs()[0].name
        logits = np.asarray(self._session.run(None, {input_name: self._preprocess(region_jpeg)})[0])
        if logits.ndim != 3:
            raise RecognitionUnavailableError("The OCR model returned an unsupported tensor shape.")
        if logits.shape[0] != 1 and logits.shape[1] == 1:
            logits = np.transpose(logits, (1, 0, 2))
        probabilities = self._softmax(logits[0])
        indices = probabilities.argmax(axis=-1)
        confidence_values = probabilities.max(axis=-1)
        output: list[str] = []
        accepted_confidences: list[float] = []
        previous = -1
        for index, confidence in zip(indices.tolist(), confidence_values.tolist(), strict=True):
            if index != 0 and index != previous and index < len(self._charset):
                output.append(self._charset[index])
                accepted_confidences.append(confidence)
            previous = index
        confidence = float(np.mean(accepted_confidences)) if accepted_confidences else 0.0
        return OcrReading(text="".join(output).strip(), confidence=confidence)

    @staticmethod
    def _preprocess(region_jpeg: bytes) -> FloatArray:
        with Image.open(BytesIO(region_jpeg)) as image:
            gray = image.convert("L")
            target_height, target_width = 48, 320
            scale = min(target_width / gray.width, target_height / gray.height)
            resized = gray.resize(
                (max(1, int(gray.width * scale)), max(1, int(gray.height * scale)))
            )
            canvas = Image.new("L", (target_width, target_height), color=255)
            canvas.paste(resized, (0, (target_height - resized.height) // 2))
            array = np.asarray(canvas, dtype=np.float32) / 127.5 - 1.0
            return np.asarray(array[None, None, :, :], dtype=np.float32)

    @staticmethod
    def _softmax(values: FloatArray) -> FloatArray:
        shifted = values - values.max(axis=-1, keepdims=True)
        exp = np.exp(shifted)
        return np.asarray(exp / exp.sum(axis=-1, keepdims=True), dtype=np.float32)


class OnnxCtcOcrEngine:
    """Use separate replaceable ONNX models for names and collector numbers."""

    def __init__(self, *, name_model_path: Path, number_model_path: Path) -> None:
        self._name = _CtcRecognizer(name_model_path, _NAME_CHARSET)
        self._number = _CtcRecognizer(number_model_path, _NUMBER_CHARSET)

    def read_name(self, region_jpeg: bytes) -> OcrReading:
        """Read the specialized top card region."""
        return self._name.read(region_jpeg)

    def read_collector_number(self, region_jpeg: bytes) -> OcrReading:
        """Read the specialized bottom card region."""
        return self._number.read(region_jpeg)
