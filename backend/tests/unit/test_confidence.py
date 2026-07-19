from dataclasses import replace

from app.application.confidence import ConfidenceThresholds, WeightedConfidenceEngine
from app.domain.models import CandidateEvidence, Card, RecognitionStatus


def _card() -> Card:
    return Card(
        id="test",
        name="Pikachu ex",
        normalized_name="pikachu ex",
        collector_number="57",
        normalized_collector_number="57",
        printed_total="182",
        source="tcgdex",
        source_card_id="sv-test-057",
        set_id="sv-test",
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


def test_accepts_a_clear_full_card_visual_winner_when_ocr_is_missing() -> None:
    engine = WeightedConfidenceEngine()
    top = CandidateEvidence(
        _card(),
        collector_score=0.0,
        name_score=0.0,
        artwork_score=0.91,
        ocr_quality=0.0,
        perceptual_hash_score=0.9,
        orb_score=0.72,
        embedding_score=0.93,
    )
    runner_up = replace(
        top,
        card=replace(_card(), id="runner-up"),
        artwork_score=0.71,
        orb_score=0.24,
        embedding_score=0.82,
    )
    ranked = [
        replace(top, confidence=engine.score(top)),
        replace(runner_up, confidence=engine.score(runner_up)),
    ]

    assert engine.classify(ranked) is RecognitionStatus.MATCHED


def test_clear_visual_winner_can_override_unrelated_ocr_noise() -> None:
    engine = WeightedConfidenceEngine()
    top = CandidateEvidence(
        _card(),
        collector_score=0.0,
        name_score=0.18,
        suffix_score=1.0,
        artwork_score=0.97,
        ocr_quality=0.58,
        localization_quality=0.8,
        blur_quality=0.2,
        perceptual_hash_score=0.97,
        orb_score=1.0,
        embedding_score=0.96,
    )
    runner_up = replace(
        top,
        card=replace(_card(), id="runner-up"),
        artwork_score=0.72,
        orb_score=0.16,
        embedding_score=0.86,
    )
    ranked = [
        replace(top, confidence=engine.score(top)),
        replace(runner_up, confidence=engine.score(runner_up)),
    ]

    assert ranked[0].confidence < engine.thresholds.matched
    assert engine.classify(ranked) is RecognitionStatus.MATCHED
