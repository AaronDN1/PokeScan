"""Explainable confidence policy for recognition decisions."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import CandidateEvidence, RecognitionStatus


@dataclass(frozen=True, slots=True)
class ConfidenceThresholds:
    """Thresholds tuned against a versioned benchmark dataset."""

    matched: float = 0.82
    ambiguous: float = 0.56
    minimum_margin: float = 0.08


class WeightedConfidenceEngine:
    """Combine independent text, image, and OCR-quality evidence."""

    def __init__(self, thresholds: ConfidenceThresholds | None = None) -> None:
        self.thresholds = thresholds or ConfidenceThresholds()

    def score(self, evidence: CandidateEvidence) -> float:
        """Calculate a bounded score with artwork as an independent verifier."""
        text_score = 0.58 * evidence.collector_score + 0.42 * evidence.name_score
        ocr_adjustment = 0.85 + (0.15 * evidence.ocr_quality)
        combined = (0.62 * text_score + 0.38 * evidence.artwork_score) * ocr_adjustment
        return round(max(0.0, min(1.0, combined)), 4)

    def classify(self, scores: list[float]) -> RecognitionStatus:
        """Classify ranked scores while refusing uncertain close calls."""
        if not scores or scores[0] < self.thresholds.ambiguous:
            return RecognitionStatus.UNRECOGNIZED
        runner_up = scores[1] if len(scores) > 1 else 0.0
        margin = scores[0] - runner_up
        if scores[0] >= self.thresholds.matched and margin >= self.thresholds.minimum_margin:
            return RecognitionStatus.MATCHED
        return RecognitionStatus.AMBIGUOUS
