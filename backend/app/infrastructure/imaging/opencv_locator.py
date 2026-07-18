"""Deterministic single-pass card localization and perspective correction."""

from __future__ import annotations

from time import perf_counter
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from app.domain.errors import (
    BlurryImageError,
    CardNotFoundError,
    MultipleCardsError,
)
from app.domain.models import NormalizedCardImage
from app.infrastructure.imaging.regions import (
    RegionCrops,
    crop_relative,
    decode_image,
    encode_jpeg,
)

_CARD_WIDTH = 744
_CARD_HEIGHT = 1039
ImageArray = NDArray[np.uint8]
PointArray = NDArray[np.float32]


class OpenCvCardLocator:
    """Find a single quadrilateral card and produce standardized OCR regions."""

    def __init__(
        self, *, minimum_blur_variance: float, crops: RegionCrops | None = None
    ) -> None:
        self._minimum_blur_variance = minimum_blur_variance
        self._crops = crops or RegionCrops()

    def normalize(self, payload: bytes) -> NormalizedCardImage:
        """Run one localization and warp pass, then extract fixed regions."""
        original = decode_image(payload)
        original_height, original_width = original.shape[:2]
        image = self._bounded_resize(original)
        localization_started = perf_counter()
        quadrilaterals = self._find_card_quadrilaterals(image)
        if len(quadrilaterals) > 1:
            raise MultipleCardsError("Only one card can be scanned at a time.")
        if quadrilaterals:
            selected_polygon = quadrilaterals[0]
            localization_ms = round((perf_counter() - localization_started) * 1000, 2)
            warp_started = perf_counter()
            card = self._warp(image, selected_polygon)
            perspective_correction_ms = round((perf_counter() - warp_started) * 1000, 2)
            image_area = float(image.shape[0] * image.shape[1])
            area_ratio = float(cv2.contourArea(selected_polygon)) / max(image_area, 1.0)
            localization_score = max(0.35, min(1.0, area_ratio / 0.58))
        elif self._already_card_shaped(image):
            localization_ms = round((perf_counter() - localization_started) * 1000, 2)
            warp_started = perf_counter()
            card = cast(
                ImageArray,
                cv2.resize(
                    self._portrait(image),
                    (_CARD_WIDTH, _CARD_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                ),
            )
            perspective_correction_ms = round((perf_counter() - warp_started) * 1000, 2)
            selected_polygon = np.array(
                [
                    [0, 0],
                    [image.shape[1], 0],
                    [image.shape[1], image.shape[0]],
                    [0, image.shape[0]],
                ],
                dtype=np.float32,
            )
            localization_score = 0.92
        else:
            raise CardNotFoundError("Keep all four card edges visible and try again.")

        gray = cv2.cvtColor(card, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_score < self._minimum_blur_variance:
            raise BlurryImageError("The photo is too blurry to identify safely.")

        top = crop_relative(card, self._crops.name)
        bottom = crop_relative(card, self._crops.collector)
        artwork = crop_relative(card, self._crops.artwork)
        scale_x = original_width / image.shape[1]
        scale_y = original_height / image.shape[0]
        polygon = tuple(
            (round(float(point[0] * scale_x), 2), round(float(point[1] * scale_y), 2))
            for point in selected_polygon
        )
        return NormalizedCardImage(
            width=_CARD_WIDTH,
            height=_CARD_HEIGHT,
            card_jpeg=encode_jpeg(card),
            top_region_jpeg=encode_jpeg(top),
            bottom_region_jpeg=encode_jpeg(bottom),
            artwork_region_jpeg=encode_jpeg(artwork),
            blur_score=blur_score,
            localization_score=localization_score,
            detected_polygon=polygon,
            original_width=original_width,
            original_height=original_height,
            localization_ms=localization_ms,
            perspective_correction_ms=perspective_correction_ms,
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
        edges = cv2.Canny(blurred, 30, 108)
        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            np.ones((9, 9), np.uint8),
            iterations=3,
        )
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
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
            height, width = image.shape[:2]
            touches_frame = any(
                point[0] <= 2
                or point[1] <= 2
                or point[0] >= width - 3
                or point[1] >= height - 3
                for point in points
            )
            if touches_frame:
                continue
            if OpenCvCardLocator._plausible_ratio(points):
                candidates.append((area, points))
        candidates.sort(key=lambda item: item[0], reverse=True)
        selected: list[PointArray] = []
        for _area, candidate_points in candidates:
            if any(
                OpenCvCardLocator._bounding_iou(candidate_points, existing) >= 0.72
                for existing in selected
            ):
                continue
            selected.append(candidate_points)
            if len(selected) == 2:
                break
        return selected

    @staticmethod
    def _bounding_iou(left: PointArray, right: PointArray) -> float:
        lx, ly, lw, lh = cv2.boundingRect(left)
        rx, ry, rw, rh = cv2.boundingRect(right)
        intersection_width = max(0, min(lx + lw, rx + rw) - max(lx, rx))
        intersection_height = max(0, min(ly + lh, ry + rh) - max(ly, ry))
        intersection = float(intersection_width * intersection_height)
        union = float(lw * lh + rw * rh) - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _plausible_ratio(points: PointArray) -> bool:
        ordered = OpenCvCardLocator._order_points(points)
        top = float(np.linalg.norm(ordered[1] - ordered[0]))
        bottom = float(np.linalg.norm(ordered[2] - ordered[3]))
        left = float(np.linalg.norm(ordered[3] - ordered[0]))
        right = float(np.linalg.norm(ordered[2] - ordered[1]))
        short, long = sorted(((top + bottom) / 2, (left + right) / 2))
        return long > 0 and 0.55 <= short / long <= 0.92

    @staticmethod
    def _already_card_shaped(image: ImageArray) -> bool:
        height, width = image.shape[:2]
        short, long = sorted((width, height))
        return long > 0 and 0.62 <= short / long <= 0.74

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
        source_width = (
            float(np.linalg.norm(source[1] - source[0]))
            + float(np.linalg.norm(source[2] - source[3]))
        ) / 2
        source_height = (
            float(np.linalg.norm(source[3] - source[0]))
            + float(np.linalg.norm(source[2] - source[1]))
        ) / 2
        landscape = source_width > source_height
        target_width, target_height = (
            (_CARD_HEIGHT, _CARD_WIDTH) if landscape else (_CARD_WIDTH, _CARD_HEIGHT)
        )
        destination = np.array(
            [
                [0, 0],
                [target_width - 1, 0],
                [target_width - 1, target_height - 1],
                [0, target_height - 1],
            ],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(source, destination)
        warped = cast(
            ImageArray,
            cv2.warpPerspective(
                image,
                transform,
                (target_width, target_height),
                flags=cv2.INTER_CUBIC,
            ),
        )
        if landscape:
            return cast(ImageArray, cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE))
        return warped
