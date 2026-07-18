"""Deterministic single-pass card localization and perspective correction."""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from app.domain.errors import (
    BlurryImageError,
    CardNotFoundError,
    InvalidImageError,
    MultipleCardsError,
)
from app.domain.models import NormalizedCardImage

_CARD_WIDTH = 744
_CARD_HEIGHT = 1039
ImageArray = NDArray[np.uint8]
PointArray = NDArray[np.float32]


class OpenCvCardLocator:
    """Find a single quadrilateral card and produce standardized OCR regions."""

    def __init__(self, *, minimum_blur_variance: float) -> None:
        self._minimum_blur_variance = minimum_blur_variance

    def normalize(self, payload: bytes) -> NormalizedCardImage:
        """Run one localization and warp pass, then extract fixed regions."""
        encoded = np.frombuffer(payload, dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None:
            raise InvalidImageError("OpenCV could not decode the image.")
        image = cast(ImageArray, decoded)

        image = self._bounded_resize(image)
        quadrilaterals = self._find_card_quadrilaterals(image)
        if len(quadrilaterals) > 1:
            raise MultipleCardsError("Only one card can be scanned at a time.")
        if quadrilaterals:
            card = self._warp(image, quadrilaterals[0])
        elif self._already_card_shaped(image):
            card = cast(
                ImageArray,
                cv2.resize(
                    self._portrait(image),
                    (_CARD_WIDTH, _CARD_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                ),
            )
        else:
            raise CardNotFoundError("Keep all four card edges visible and try again.")

        gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_score < self._minimum_blur_variance:
            raise BlurryImageError("The photo is too blurry to identify safely.")

        top = card[0 : int(_CARD_HEIGHT * 0.18), :]
        bottom = card[int(_CARD_HEIGHT * 0.76) : _CARD_HEIGHT, :]
        artwork = card[int(_CARD_HEIGHT * 0.13) : int(_CARD_HEIGHT * 0.73), :]
        return NormalizedCardImage(
            width=_CARD_WIDTH,
            height=_CARD_HEIGHT,
            card_jpeg=self._encode(card),
            top_region_jpeg=self._encode(top),
            bottom_region_jpeg=self._encode(bottom),
            artwork_region_jpeg=self._encode(artwork),
            blur_score=blur_score,
        )

    @staticmethod
    def _bounded_resize(image: ImageArray) -> ImageArray:
        height, width = image.shape[:2]
        largest = max(width, height)
        if largest <= 2200:
            return image
        scale = 2200 / largest
        return cast(
            ImageArray,
            cv2.resize(
                image,
                (int(width * scale), int(height * scale)),
                interpolation=cv2.INTER_AREA,
            ),
        )

    @staticmethod
    def _find_card_quadrilaterals(image: ImageArray) -> list[PointArray]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 52, 148)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_area = image.shape[0] * image.shape[1]
        candidates: list[tuple[float, PointArray]] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < image_area * 0.14:
                continue
            perimeter = cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
            if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                continue
            points = polygon.reshape(4, 2).astype(np.float32)
            if OpenCvCardLocator._plausible_ratio(points):
                candidates.append((area, points))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [points for _, points in candidates[:2]]

    @staticmethod
    def _plausible_ratio(points: PointArray) -> bool:
        ordered = OpenCvCardLocator._order_points(points)
        top = float(np.linalg.norm(ordered[1] - ordered[0]))
        bottom = float(np.linalg.norm(ordered[2] - ordered[3]))
        left = float(np.linalg.norm(ordered[3] - ordered[0]))
        right = float(np.linalg.norm(ordered[2] - ordered[1]))
        short, long = sorted(((top + bottom) / 2, (left + right) / 2))
        return long > 0 and 0.58 <= short / long <= 0.82

    @staticmethod
    def _already_card_shaped(image: ImageArray) -> bool:
        height, width = image.shape[:2]
        short, long = sorted((width, height))
        return long > 0 and 0.62 <= short / long <= 0.78

    @staticmethod
    def _portrait(image: ImageArray) -> ImageArray:
        if image.shape[1] <= image.shape[0]:
            return image
        return cast(ImageArray, cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE))

    @staticmethod
    def _order_points(points: PointArray) -> PointArray:
        ordered = np.zeros((4, 2), dtype=np.float32)
        coordinate_sum = points.sum(axis=1)
        coordinate_diff = np.diff(points, axis=1).reshape(-1)
        ordered[0] = points[np.argmin(coordinate_sum)]
        ordered[2] = points[np.argmax(coordinate_sum)]
        ordered[1] = points[np.argmin(coordinate_diff)]
        ordered[3] = points[np.argmax(coordinate_diff)]
        return ordered

    @staticmethod
    def _warp(image: ImageArray, points: PointArray) -> ImageArray:
        source = OpenCvCardLocator._order_points(points)
        destination = np.array(
            [
                [0, 0],
                [_CARD_WIDTH - 1, 0],
                [_CARD_WIDTH - 1, _CARD_HEIGHT - 1],
                [0, _CARD_HEIGHT - 1],
            ],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(source, destination)
        return cast(
            ImageArray,
            cv2.warpPerspective(
                image,
                transform,
                (_CARD_WIDTH, _CARD_HEIGHT),
                flags=cv2.INTER_CUBIC,
            ),
        )

    @staticmethod
    def _encode(image: ImageArray) -> bytes:
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise InvalidImageError("The normalized image could not be encoded.")
        return encoded.tobytes()
