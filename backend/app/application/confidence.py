"""Explainable confidence policy for recognition decisions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import CandidateEvidence, RecognitionStatus


@dataclass(frozen=True, slots=True)
class ConfidenceThresholds:
    """Conservative baseline thresholds that must be recalibrated with benchmarks."""

    matched: float = 0.76
    ambiguous: float = 0.48
    minimum_margin: float = 0.06
    minimum_text_for_match: float = 0.52
    minimum_visual_for_match: float = 0.42


class WeightedConfidenceEngine:
    """Combine independent text, image, and OCR-quality evidence."""

    def __init__(self, thresholds: ConfidenceThresholds | None = None) -> None:
        self.thresholds = thresholds or ConfidenceThresholds()

    def score(self, evidence: CandidateEvidence) -> float:
        """Combine real text, visual, localization, and image-quality signals."""
        if evidence.collector_score > 0 and evidence.name_score > 0:
            text_score = (
                0.50 * evidence.collector_score
                + 0.36 * evidence.name_score
                + 0.14 * evidence.suffix_score
            )
        elif evidence.collector_score > 0:
            text_score = 0.90 * evidence.collector_score + 0.10 * evidence.suffix_score
        else:
            text_score = 0.82 * evidence.name_score + 0.18 * evidence.suffix_score
        quality = (
            0.72
            + 0.13 * evidence.ocr_quality
            + 0.10 * evidence.localization_quality
            + 0.05 * evidence.blur_quality
        )
        combined = (0.58 * text_score + 0.42 * evidence.artwork_score) * quality
        return round(max(0.0, min(1.0, combined)), 4)

    def classify(
        self, ranked: Sequence[CandidateEvidence] | Sequence[float]
    ) -> RecognitionStatus:
        """Classify ranked evidence while refusing uncertain close calls."""
        if ranked and isinstance(ranked[0], CandidateEvidence):
            evidence = [item for item in ranked if isinstance(item, CandidateEvidence)]
            scores = [item.confidence for item in evidence]
        else:
            evidence = []
            scores = [item for item in ranked if isinstance(item, float)]
        if not scores or scores[0] < self.thresholds.ambiguous:
            return RecognitionStatus.UNRECOGNIZED
        runner_up = scores[1] if len(scores) > 1 else 0.0
        margin = scores[0] - runner_up
        signals_agree = True
        if evidence:
            top = evidence[0]
            text_score = max(
                0.64 * top.collector_score + 0.36 * top.name_score,
                0.82 * top.name_score + 0.18 * top.suffix_score,
            )
            signals_agree = (
                text_score >= self.thresholds.minimum_text_for_match
                and top.artwork_score >= self.thresholds.minimum_visual_for_match
            )
        if (
            scores[0] >= self.thresholds.matched
            and margin >= self.thresholds.minimum_margin
            and signals_agree
        ):
            return RecognitionStatus.MATCHED
        return RecognitionStatus.AMBIGUOUS
