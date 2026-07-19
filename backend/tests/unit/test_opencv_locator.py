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
