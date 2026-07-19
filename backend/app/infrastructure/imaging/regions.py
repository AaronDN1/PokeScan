"""Shared normalized card-region extraction used by scans and catalog assets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from app.domain.errors import InvalidImageError

ImageArray = NDArray[np.uint8]
CropBox = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class RegionCrops:
    """Relative left, top, right, bottom crop coordinates."""

    name: CropBox = (0.035, 0.025, 0.78, 0.155)
    collector: CropBox = (0.0, 0.88, 1.0, 0.995)
    artwork: CropBox = (0.055, 0.135, 0.945, 0.675)


def decode_image(payload: bytes) -> ImageArray:
    """Decode image bytes through OpenCV or raise a safe domain error."""
    decoded = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise InvalidImageError("OpenCV could not decode the image.")
    return cast(ImageArray, decoded)


def encode_jpeg(image: ImageArray) -> bytes:
    """Encode a deterministic high-quality JPEG for downstream adapters."""
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise InvalidImageError("The normalized image could not be encoded.")
    return encoded.tobytes()


def crop_relative(image: ImageArray, crop: CropBox) -> ImageArray:
    """Extract a validated relative crop from an image."""
    height, width = image.shape[:2]
    left, top, right, bottom = crop
    x1, x2 = max(0, int(width * left)), min(width, int(width * right))
    y1, y2 = max(0, int(height * top)), min(height, int(height * bottom))
    if x2 <= x1 or y2 <= y1:
        raise InvalidImageError("A configured recognition crop is empty.")
    return cast(ImageArray, image[y1:y2, x1:x2])


def crop_regions(
    image: ImageArray, crops: RegionCrops
) -> tuple[ImageArray, ImageArray, ImageArray]:
    """Extract the name, collector-number, and artwork regions consistently."""
    return (
        crop_relative(image, crops.name),
        crop_relative(image, crops.collector),
        crop_relative(image, crops.artwork),
    )


def rotate_card(image: ImageArray, degrees: int) -> ImageArray:
    """Return a cached-friendly right-angle rotation without another warp."""
    normalized = degrees % 360
    if normalized == 0:
        return image
    if normalized == 90:
        return cast(ImageArray, cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE))
    if normalized == 180:
        return cast(ImageArray, cv2.rotate(image, cv2.ROTATE_180))
    if normalized == 270:
        return cast(ImageArray, cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE))
    raise ValueError("Only right-angle rotations are supported.")
