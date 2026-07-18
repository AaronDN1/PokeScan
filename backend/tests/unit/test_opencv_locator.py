import cv2
import numpy as np

from app.infrastructure.imaging.opencv_locator import OpenCvCardLocator


def test_normalizes_an_already_cropped_card_image() -> None:
    image = np.zeros((1039, 744, 3), dtype=np.uint8)
    image[:] = (36, 42, 54)
    cv2.rectangle(image, (30, 30), (713, 1008), (220, 220, 220), 4)
    cv2.putText(image, "CARD", (170, 220), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    normalized = OpenCvCardLocator(minimum_blur_variance=1).normalize(encoded.tobytes())

    assert normalized.width == 744
    assert normalized.height == 1039
    assert normalized.top_region_jpeg.startswith(b"\xff\xd8")
    assert normalized.bottom_region_jpeg.startswith(b"\xff\xd8")
