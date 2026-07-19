"""Explainable confidence policy for recognition decisions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import CandidateEvidence, RecognitionStatus


@dataclass(frozen=True, slots=True)
class ConfidenceThresholds:
    """Conservative baseline thresholds that must be recalibrated with benchmarks."""

    matched: float = 0.72
    ambiguous: float = 0.34
    minimum_margin: float = 0.045
    minimum_text_for_match: float = 0.35
    minimum_visual_for_match: float = 0.44
    strong_visual_for_match: float = 0.82
    strong_visual_margin: float = 0.08
    minimum_orb_for_visual_match: float = 0.35
    minimum_embedding_for_visual_match: float = 0.82


class WeightedConfidenceEngine:
    """Combine independent text, image, and OCR-quality evidence."""

    def __init__(self, thresholds: ConfidenceThresholds | None = None) -> None:
        self.thresholds = thresholds or ConfidenceThresholds()

    def score(self, evidence: CandidateEvidence) -> float:
        """Combine real text, visual, localization, and image-quality signals."""
        text_score = self._text_score(evidence)
        if text_score < 0.20:
            quality = (
                0.82
                + 0.12 * evidence.localization_quality
                + 0.06 * evidence.blur_quality
            )
            combined = 0.04 * text_score + 0.96 * evidence.artwork_score
        elif text_score < 0.55:
            quality = (
                0.76
                + 0.08 * evidence.ocr_quality
                + 0.11 * evidence.localization_quality
                + 0.05 * evidence.blur_quality
            )
            combined = 0.40 * text_score + 0.60 * evidence.artwork_score
        else:
            quality = (
                0.72
                + 0.13 * evidence.ocr_quality
                + 0.10 * evidence.localization_quality
                + 0.05 * evidence.blur_quality
            )
            combined = 0.58 * text_score + 0.42 * evidence.artwork_score
        return round(max(0.0, min(1.0, combined * quality)), 4)

    @staticmethod
    def _text_score(evidence: CandidateEvidence) -> float:
        if evidence.collector_score > 0 and evidence.name_score > 0:
            return (
                0.50 * evidence.collector_score
                + 0.36 * evidence.name_score
                + 0.14 * evidence.suffix_score
            )
        if evidence.collector_score > 0:
            return 0.90 * evidence.collector_score + 0.10 * evidence.suffix_score
        return 0.82 * evidence.name_score + 0.18 * evidence.suffix_score

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
        strong_visual = False
        if evidence:
            top = evidence[0]
            text_score = self._text_score(top)
            signals_agree = (
                text_score >= self.thresholds.minimum_text_for_match
                and top.artwork_score >= self.thresholds.minimum_visual_for_match
            )
            runner_visual = evidence[1].artwork_score if len(evidence) > 1 else 0.0
            strong_visual = (
                top.artwork_score >= self.thresholds.strong_visual_for_match
                and top.artwork_score - runner_visual
                >= self.thresholds.strong_visual_margin
                and top.orb_score >= self.thresholds.minimum_orb_for_visual_match
                and top.embedding_score
                >= self.thresholds.minimum_embedding_for_visual_match
            )
        if strong_visual and margin >= self.thresholds.minimum_margin:
            return RecognitionStatus.MATCHED
        if (
            scores[0] >= self.thresholds.matched
            and margin >= self.thresholds.minimum_margin
            and signals_agree
        ):
            return RecognitionStatus.MATCHED
        return RecognitionStatus.AMBIGUOUS
