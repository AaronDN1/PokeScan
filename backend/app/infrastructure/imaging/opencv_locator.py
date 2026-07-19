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
ContourArray = NDArray[np.int32]


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
        lab = cast(ImageArray, cv2.cvtColor(image, cv2.COLOR_BGR2LAB))
        # A darker luminance pass suppresses JPEG-amplified background grain while
        # retaining the long card border. It is especially useful for phone-sized
        # compressed photos where the ordinary grayscale contour can join the frame.
        dark_gray = cv2.convertScaleAbs(gray, alpha=0.70, beta=-8)
        edge_channels = (gray, dark_gray, lab[:, :, 1], lab[:, :, 2])
        edges = np.zeros_like(gray)
        for channel in edge_channels:
            blurred = cv2.GaussianBlur(channel, (5, 5), 0)
            channel_edges = cv2.Canny(blurred, 24, 112)
            edges = cv2.bitwise_or(edges, channel_edges)
        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            np.ones((9, 9), np.uint8),
            iterations=3,
        )
        foreground = OpenCvCardLocator._foreground_mask(lab)
        contours: list[ContourArray] = []
        for contour_source in (edges, foreground):
            source_contours, _ = cv2.findContours(
                contour_source,
                cv2.RETR_LIST,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            contours.extend(cast(list[ContourArray], source_contours))
        image_area = image.shape[0] * image.shape[1]
        candidates: list[tuple[float, bool, PointArray]] = []
        edge_contour_count = len(
            cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]
        )
        for contour_index, contour in enumerate(contours):
            is_foreground_fallback = contour_index >= edge_contour_count
            area = float(cv2.contourArea(contour))
            if area < image_area * 0.08:
                continue
            hull = cv2.convexHull(contour)
            perimeter = cv2.arcLength(hull, True)
            for epsilon in (0.018, 0.025, 0.04, 0.06):
                polygon = cv2.approxPolyDP(hull, epsilon * perimeter, True)
                if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                    continue
                points = polygon.reshape(4, 2).astype(np.float32)
                if OpenCvCardLocator._touches_too_many_frame_sides(points, image):
                    continue
                if OpenCvCardLocator._plausible_ratio(points):
                    polygon_area = float(cv2.contourArea(points))
                    candidates.append((polygon_area, is_foreground_fallback, points))
                    break
        # Compression and wood-grain backgrounds can join one card corner to the
        # frame, producing a slightly larger but badly skewed edge contour. Rank
        # by geometric stability and frame independence as well as raw area, and
        # retain the independent foreground-mask candidates for comparison.
        candidates.sort(
            key=lambda item: item[0]
            * OpenCvCardLocator._candidate_quality(item[2], image),
            reverse=True,
        )
        selected: list[PointArray] = []
        for _area, _is_fallback, candidate_points in candidates:
            if any(
                OpenCvCardLocator._same_subject(candidate_points, existing)
                for existing in selected
            ):
                continue
            selected.append(candidate_points)
            if len(selected) == 2:
                break
        return selected

    @staticmethod
    def _foreground_mask(lab: ImageArray) -> ImageArray:
        """Estimate a dominant centered subject from the photo's corner colors."""
        height, width = lab.shape[:2]
        patch_height = max(8, int(height * 0.06))
        patch_width = max(8, int(width * 0.06))
        corner_pixels = np.concatenate(
            (
                lab[:patch_height, :patch_width].reshape(-1, 3),
                lab[:patch_height, -patch_width:].reshape(-1, 3),
                lab[-patch_height:, :patch_width].reshape(-1, 3),
                lab[-patch_height:, -patch_width:].reshape(-1, 3),
            )
        )
        background = np.median(corner_pixels, axis=0).astype(np.float32)
        distance = np.linalg.norm(lab.astype(np.float32) - background, axis=2)
        distance_u8 = np.clip(distance, 0, 255).astype(np.uint8)
        threshold, mask = cv2.threshold(
            distance_u8,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        if threshold < 8:
            _, mask = cv2.threshold(distance_u8, 8, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((15, 15), np.uint8),
            iterations=2,
        )
        return cast(
            ImageArray,
            cv2.morphologyEx(
                mask,
                cv2.MORPH_OPEN,
                np.ones((5, 5), np.uint8),
                iterations=1,
            ),
        )

    @staticmethod
    def _touches_too_many_frame_sides(points: PointArray, image: ImageArray) -> bool:
        return OpenCvCardLocator._frame_touch_count(points, image) >= 3

    @staticmethod
    def _frame_touch_count(points: PointArray, image: ImageArray) -> int:
        height, width = image.shape[:2]
        margin = max(3.0, min(width, height) * 0.006)
        touched_sides = {
            side
            for side, touched in (
                ("left", bool(np.any(points[:, 0] <= margin))),
                ("right", bool(np.any(points[:, 0] >= width - 1 - margin))),
                ("top", bool(np.any(points[:, 1] <= margin))),
                ("bottom", bool(np.any(points[:, 1] >= height - 1 - margin))),
            )
            if touched
        }
        # Morphological closing can expand a real card border into one or two
        # frame edges. Three or four touched sides is instead usually the image
        # boundary itself, which must never be treated as a detected card.
        return len(touched_sides)

    @staticmethod
    def _candidate_quality(points: PointArray, image: ImageArray) -> float:
        ordered = OpenCvCardLocator._order_points(points)
        top = float(np.linalg.norm(ordered[1] - ordered[0]))
        bottom = float(np.linalg.norm(ordered[2] - ordered[3]))
        left = float(np.linalg.norm(ordered[3] - ordered[0]))
        right = float(np.linalg.norm(ordered[2] - ordered[1]))
        width_balance = min(top, bottom) / max(top, bottom, 1.0)
        height_balance = min(left, right) / max(left, right, 1.0)
        frame_penalty = 0.62 ** OpenCvCardLocator._frame_touch_count(points, image)
        return width_balance * height_balance * frame_penalty

    @staticmethod
    def _same_subject(left: PointArray, right: PointArray) -> bool:
        if OpenCvCardLocator._bounding_iou(left, right) >= 0.72:
            return True
        lx, ly, lw, lh = cv2.boundingRect(left)
        rx, ry, rw, rh = cv2.boundingRect(right)
        intersection_width = max(0, min(lx + lw, rx + rw) - max(lx, rx))
        intersection_height = max(0, min(ly + lh, ry + rh) - max(ly, ry))
        intersection = float(intersection_width * intersection_height)
        smaller = float(min(lw * lh, rw * rh))
        return smaller > 0 and intersection / smaller >= 0.82

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
