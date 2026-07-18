from pathlib import Path

import cv2
import numpy as np

from app.domain.models import Card
from app.infrastructure.imaging.regions import encode_jpeg
from app.infrastructure.models.composite_artwork import (
    CompositeArtworkMatcher,
    MobileNetV2Embedder,
    extract_visual_features,
)


def test_composite_artwork_scores_are_bounded_without_a_pretrained_model() -> None:
    image = np.zeros((420, 600, 3), dtype=np.uint8)
    cv2.rectangle(image, (40, 40), (560, 380), (40, 180, 240), -1)
    cv2.circle(image, (300, 210), 110, (230, 220, 30), -1)
    payload = encode_jpeg(image)
    features = extract_visual_features(payload, MobileNetV2Embedder(Path("missing.onnx")))
    card = Card(
        id="tcgdex:en:test:test-1",
        name="Pikachu",
        normalized_name="pikachu",
        collector_number="1",
        normalized_collector_number="1",
        printed_total="1",
        source="tcgdex",
        source_card_id="test-1",
        set_id="test",
        set_name="Test",
        rarity=None,
        language="en",
        image_url="https://example.com/card.webp",
        perceptual_hash=features.perceptual_hash,
        orb_descriptors=features.orb_descriptors,
    )
    result = CompositeArtworkMatcher(Path("missing.onnx")).score_many(payload, [card])[card.id]
    assert 0.0 <= result.perceptual_hash_score <= 1.0
    assert 0.0 <= result.orb_score <= 1.0
    assert 0.0 <= result.combined_score <= 1.0
    assert result.combined_score > 0.75
