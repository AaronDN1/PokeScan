import cv2
import numpy as np
import pytest

from app.domain.errors import CardNotFoundError
from app.infrastructure.imaging.opencv_locator import OpenCvCardLocator


def _encode(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_normalizes_an_already_cropped_card_image() -> None:
    image = np.zeros((1039, 744, 3), dtype=np.uint8)
    image[:] = (36, 42, 54)
    cv2.rectangle(image, (30, 30), (713, 1008), (220, 220, 220), 4)
    cv2.putText(image, "CARD", (170, 220), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 8)
    normalized = OpenCvCardLocator(minimum_blur_variance=1).normalize(_encode(image))

    assert normalized.width == 744
    assert normalized.height == 1039
    assert normalized.top_region_jpeg.startswith(b"\xff\xd8")
    assert normalized.bottom_region_jpeg.startswith(b"\xff\xd8")
    assert normalized.detected_polygon == (
        (0.0, 0.0),
        (744.0, 0.0),
        (744.0, 1039.0),
        (0.0, 1039.0),
    )


def test_localizes_a_compressed_card_on_a_low_contrast_textured_surface() -> None:
    rng = np.random.default_rng(67)
    height, width = 640, 480
    y, x = np.indices((height, width))
    leather = np.empty((height, width, 3), dtype=np.float32)
    leather[:, :, 0] = 64 + (x * 0.025) + (y * 0.018)
    leather[:, :, 1] = 83 + (x * 0.035) + (y * 0.025)
    leather[:, :, 2] = 105 + (x * 0.045) + (y * 0.030)
    leather += rng.normal(0, 5.0, leather.shape)
    image = np.clip(leather, 0, 255).astype(np.uint8)

    card = np.full((440, 300, 3), (92, 170, 191), dtype=np.uint8)
    cv2.rectangle(card, (8, 8), (291, 431), (118, 187, 205), 5)
    cv2.rectangle(card, (20, 42), (279, 215), (125, 142, 145), -1)
    cv2.rectangle(card, (25, 50), (274, 205), (80, 111, 128), 3)
    cv2.putText(
        card,
        "MIENFOO",
        (24, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (30, 31, 34),
        2,
    )
    cv2.putText(
        card,
        "TRIPLE SMASH",
        (40, 285),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (42, 45, 48),
        2,
    )
    cv2.line(card, (22, 350), (276, 350), (66, 76, 82), 2)

    expected = np.asarray(
        [[108, 120], [407, 128], [397, 572], [71, 552]],
        dtype=np.float32,
    )
    source = np.asarray(
        [[0, 0], [299, 0], [299, 439], [0, 439]],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source, expected)
    warped_card = cv2.warpPerspective(card, transform, (width, height))
    warped_mask = cv2.warpPerspective(
        np.full(card.shape[:2], 255, dtype=np.uint8),
        transform,
        (width, height),
    )
    image[warped_mask > 0] = warped_card[warped_mask > 0]

    # A nearby background seam and low JPEG quality mimic the soft, partly merged
    # border that caused the real phone photo to be rejected.
    cv2.line(image, (0, 625), (75, 548), (103, 137, 151), 6)
    ok, compressed = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 58])
    assert ok

    normalized = OpenCvCardLocator(minimum_blur_variance=1).normalize(
        compressed.tobytes()
    )

    detected = np.asarray(normalized.detected_polygon, dtype=np.float32)
    assert normalized.width == 744
    assert normalized.height == 1039
    assert np.max(np.linalg.norm(detected - expected, axis=1)) < 24
    assert normalized.localization_score >= 0.65


def test_normalizes_a_clear_card_whose_detected_border_is_close_to_the_frame() -> None:
    image = np.full((1400, 1200, 3), (28, 34, 42), dtype=np.uint8)
    cv2.rectangle(image, (102, 2), (1097, 1397), (218, 218, 218), -1)
    cv2.rectangle(image, (102, 2), (1097, 1397), (242, 242, 242), 5)
    cv2.rectangle(image, (165, 210), (1035, 800), (70, 120, 190), -1)
    cv2.putText(
        image,
        "PIKACHU",
        (175, 145),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.2,
        (20, 20, 20),
        6,
    )

    normalized = OpenCvCardLocator(minimum_blur_variance=1).normalize(_encode(image))

    assert normalized.width == 744
    assert normalized.height == 1039
    assert normalized.localization_score >= 0.8


def test_still_rejects_an_image_without_a_card_shaped_subject() -> None:
    image = np.full((800, 1400, 3), (40, 40, 40), dtype=np.uint8)
    cv2.circle(image, (700, 400), 260, (220, 220, 220), -1)

    with pytest.raises(CardNotFoundError):
        OpenCvCardLocator(minimum_blur_variance=1).normalize(_encode(image))


def test_candidate_quality_penalizes_a_corner_joined_to_the_image_frame() -> None:
    image = np.zeros((825, 1100, 3), dtype=np.uint8)
    stable = np.asarray(
        [[754, 117], [796, 657], [306, 660], [323, 121]],
        dtype=np.float32,
    )
    frame_joined = np.asarray(
        [[740, 0], [797, 654], [307, 659], [325, 120]],
        dtype=np.float32,
    )

    assert OpenCvCardLocator._candidate_quality(
        stable, image
    ) > OpenCvCardLocator._candidate_quality(frame_joined, image)
