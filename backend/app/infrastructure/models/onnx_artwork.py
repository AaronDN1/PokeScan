"""Candidate-only artwork embedding verification."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray
from PIL import Image

from app.domain.models import ArtworkEvidence, Card

FloatArray = NDArray[np.float32]


class OnnxArtworkMatcher:
    """Compare one scan embedding with precomputed catalog embeddings."""

    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._session: ort.InferenceSession | None = None

    def score(self, artwork_jpeg: bytes, card: Card) -> float:
        """Return zero when an artifact is missing so text alone cannot overclaim."""
        if not card.visual_embedding or not self._model_path.is_file():
            return 0.0
        observed = self._embed(artwork_jpeg)
        return self._cosine_score(observed, card.visual_embedding)

    def score_many(
        self, artwork_jpeg: bytes, cards: Sequence[Card]
    ) -> dict[str, ArtworkEvidence]:
        """Run the custom embedding model once and compare bounded candidates."""
        if not self._model_path.is_file():
            return {card.id: ArtworkEvidence() for card in cards}
        observed = self._embed(artwork_jpeg)
        return {
            card.id: ArtworkEvidence(
                embedding_score=self._cosine_score(observed, card.visual_embedding),
                combined_score=self._cosine_score(observed, card.visual_embedding),
            )
            for card in cards
        }

    def _embed(self, artwork_jpeg: bytes) -> FloatArray:
        if self._session is None:
            self._session = ort.InferenceSession(
                str(self._model_path), providers=["CPUExecutionProvider"]
            )
        input_name = self._session.get_inputs()[0].name
        output = np.asarray(
            self._session.run(None, {input_name: self._preprocess(artwork_jpeg)})[0]
        )
        return np.asarray(output.reshape(-1), dtype=np.float32)

    @staticmethod
    def _cosine_score(
        observed: FloatArray, expected_values: tuple[float, ...] | None
    ) -> float:
        if not expected_values:
            return 0.0
        expected = np.asarray(expected_values, dtype=np.float32)
        if observed.size != expected.size:
            return 0.0
        denominator = float(np.linalg.norm(observed) * np.linalg.norm(expected))
        if denominator == 0:
            return 0.0
        cosine = float(np.dot(observed, expected) / denominator)
        return max(0.0, min(1.0, (cosine + 1.0) / 2.0))

    @staticmethod
    def _preprocess(artwork_jpeg: bytes) -> FloatArray:
        with Image.open(BytesIO(artwork_jpeg)) as image:
            rgb = image.convert("RGB").resize((224, 224))
            array = np.asarray(rgb, dtype=np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (array - mean) / std
        return np.asarray(np.transpose(normalized, (2, 0, 1))[None, :, :, :], dtype=np.float32)
