from app.application.confidence import ConfidenceThresholds, WeightedConfidenceEngine
from app.domain.models import CandidateEvidence, Card, RecognitionStatus


def _card() -> Card:
    return Card(
        id="test",
        name="Pikachu ex",
        normalized_name="pikachu ex",
        collector_number="57",
        printed_total="182",
        set_name="Test Set",
        rarity="Double Rare",
        language="English",
        image_url="https://example.com/card.webp",
        marketplace_url="https://example.com/marketplace",
    )


def test_requires_independent_artwork_evidence_for_high_confidence() -> None:
    engine = WeightedConfidenceEngine()
    text_only = CandidateEvidence(_card(), 1.0, 1.0, 0.0, 1.0)
    verified = CandidateEvidence(_card(), 1.0, 1.0, 0.95, 1.0)
    assert engine.score(text_only) < engine.thresholds.matched
    assert engine.score(verified) >= engine.thresholds.matched


def test_refuses_close_high_scoring_candidates() -> None:
    engine = WeightedConfidenceEngine(
        ConfidenceThresholds(matched=0.8, ambiguous=0.55, minimum_margin=0.08)
    )
    assert engine.classify([0.9, 0.86]) is RecognitionStatus.AMBIGUOUS
    assert engine.classify([0.9, 0.7]) is RecognitionStatus.MATCHED
    assert engine.classify([0.4]) is RecognitionStatus.UNRECOGNIZED
