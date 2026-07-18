"""Candidate-only pHash, ORB, and pretrained MobileNetV2 visual verification."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

from app.domain.models import ArtworkEvidence, Card
from app.infrastructure.imaging.regions import decode_image

ImageArray = NDArray[np.uint8]
FloatArray = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class VisualFeatures:
    """Reusable static or per-request features for one normalized visual crop."""

    perceptual_hash: str
    orb_descriptors: bytes | None
    embedding: tuple[float, ...] | None


class MobileNetV2Embedder:
    """Process-scoped ONNX feature extractor with the classifier head removed."""

    backend_name = "mobilenetv2_imagenet_onnx"

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._session: ort.InferenceSession | None = None

    @property
    def available(self) -> bool:
        return self.model_path.is_file()

    def embed(self, image: ImageArray) -> tuple[float, ...] | None:
        """Return a normalized feature vector, or none when setup is incomplete."""
        if not self.available:
            return None
        if self._session is None:
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        input_name = self._session.get_inputs()[0].name
        output = np.asarray(
            self._session.run(None, {input_name: self._preprocess(image)})[0],
            dtype=np.float32,
        ).reshape(-1)
        norm = float(np.linalg.norm(output))
        if norm <= 0:
            return None
        normalized = output / norm
        return tuple(float(value) for value in normalized)

    @staticmethod
    def _preprocess(image: ImageArray) -> FloatArray:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        array = np.asarray(resized, dtype=np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (array - mean) / std
        return np.asarray(np.transpose(normalized, (2, 0, 1))[None, ...], dtype=np.float32)


def perceptual_hash(image: ImageArray) -> str:
    """Return a deterministic 64-bit DCT perceptual hash."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    coefficients = np.asarray(cv2.dct(resized)[:8, :8], dtype=np.float32)
    values = np.asarray(coefficients.flatten(), dtype=np.float32)
    median = float(np.median(values[1:]))
    bits = np.asarray(values > median, dtype=np.bool_).reshape(-1)
    encoded = 0
    for bit in bits:
        encoded = (encoded << 1) | int(bit)
    return f"{encoded:016x}"


def orb_descriptors(image: ImageArray) -> bytes | None:
    """Calculate bounded ORB descriptors for candidate-only matching."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.ORB_create(  # type: ignore[attr-defined]
        nfeatures=700, scaleFactor=1.2, nlevels=8
    )
    _keypoints, descriptors = detector.detectAndCompute(gray, None)
    if descriptors is None or not descriptors.size:
        return None
    return np.asarray(descriptors, dtype=np.uint8).tobytes()


def extract_visual_features(payload: bytes, embedder: MobileNetV2Embedder) -> VisualFeatures:
    """Compute each scan feature exactly once."""
    image = decode_image(payload)
    return VisualFeatures(
        perceptual_hash=perceptual_hash(image),
        orb_descriptors=orb_descriptors(image),
        embedding=embedder.embed(image),
    )


class CompositeArtworkMatcher:
    """Combine static candidate pHash, ORB, and pretrained embedding evidence."""

    backend_name = "composite_phash_orb_mobilenetv2"

    def __init__(self, model_path: Path) -> None:
        self.embedder = MobileNetV2Embedder(model_path)

    @property
    def available(self) -> bool:
        return self.embedder.available

    def score(self, artwork_jpeg: bytes, card: Card) -> float:
        """Retain the original single-candidate interface for replaceability."""
        return self.score_many(artwork_jpeg, [card]).get(card.id, ArtworkEvidence()).combined_score

    def score_many(
        self, artwork_jpeg: bytes, cards: Sequence[Card]
    ) -> dict[str, ArtworkEvidence]:
        """Compute scan features once, then compare only with supplied candidates."""
        observed = extract_visual_features(artwork_jpeg, self.embedder)
        return {card.id: self._score_features(observed, card) for card in cards}

    @staticmethod
    def _score_features(observed: VisualFeatures, card: Card) -> ArtworkEvidence:
        components: list[tuple[float, float]] = []
        hash_score = 0.0
        if card.perceptual_hash:
            try:
                distance = (
                    int(observed.perceptual_hash, 16) ^ int(card.perceptual_hash, 16)
                ).bit_count()
                hash_score = max(0.0, min(1.0, 1.0 - distance / 64))
                components.append((0.28, hash_score))
            except ValueError:
                hash_score = 0.0

        orb_score = CompositeArtworkMatcher._orb_score(
            observed.orb_descriptors, card.orb_descriptors
        )
        if observed.orb_descriptors and card.orb_descriptors:
            components.append((0.37, orb_score))

        embedding_score = CompositeArtworkMatcher._embedding_score(
            observed.embedding, card.visual_embedding
        )
        if observed.embedding and card.visual_embedding:
            components.append((0.35, embedding_score))

        weight_total = sum(weight for weight, _score in components)
        combined = (
            sum(weight * score for weight, score in components) / weight_total
            if weight_total
            else 0.0
        )
        return ArtworkEvidence(
            perceptual_hash_score=round(hash_score, 4),
            orb_score=round(orb_score, 4),
            embedding_score=round(embedding_score, 4),
            combined_score=round(max(0.0, min(1.0, combined)), 4),
        )

    @staticmethod
    def _orb_score(observed: bytes | None, expected: bytes | None) -> float:
        if not observed or not expected or len(observed) % 32 or len(expected) % 32:
            return 0.0
        left = np.frombuffer(observed, dtype=np.uint8).reshape(-1, 32)
        right = np.frombuffer(expected, dtype=np.uint8).reshape(-1, 32)
        if len(left) < 2 or len(right) < 2:
            return 0.0
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        try:
            pairs = matcher.knnMatch(left, right, k=2)
        except cv2.error:
            return 0.0
        good = sum(
            1
            for pair in pairs
            if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
        )
        denominator = max(12.0, min(len(left), len(right)) * 0.18)
        return max(0.0, min(1.0, good / denominator))

    @staticmethod
    def _embedding_score(
        observed: tuple[float, ...] | None, expected: tuple[float, ...] | None
    ) -> float:
        if not observed or not expected or len(observed) != len(expected):
            return 0.0
        left = np.asarray(observed, dtype=np.float32)
        right = np.asarray(expected, dtype=np.float32)
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator <= 0:
            return 0.0
        cosine = float(np.dot(left, right) / denominator)
        return max(0.0, min(1.0, (cosine + 1.0) / 2.0))
