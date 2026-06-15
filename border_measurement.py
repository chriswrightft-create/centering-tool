from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np
from pages.line_mark_constants import INNER_FRAME_DETECTION


@dataclass(frozen=True)
class BorderRatios:
    left_px: int
    right_px: int
    top_px: int
    bottom_px: int
    left_right_ratio: Tuple[float, float]
    top_bottom_ratio: Tuple[float, float]
    in_45_55_range: bool


@dataclass(frozen=True)
class BorderAnalysisDebug:
    warped_card_image: np.ndarray
    inner_left_x: int
    inner_right_x: int
    inner_top_y: int
    inner_bottom_y: int


def _ratio_pair(first_value: int, second_value: int) -> Tuple[float, float]:
    total = max(first_value + second_value, 1)
    first_percent = round((first_value / total) * 100, 2)
    return first_percent, round(100 - first_percent, 2)


def _smooth(values: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(values.reshape(1, -1), (1, 9), 0).reshape(-1)


def _edge_transition_index(values: np.ndarray, start_idx: int, end_idx: int, from_end: bool = False) -> int:
    bounded_start = max(start_idx, 0)
    bounded_end = min(end_idx, len(values) - 1)
    if bounded_end <= bounded_start:
        return bounded_start

    region = values[bounded_start : bounded_end + 1]
    if from_end:
        region = region[::-1]
    baseline_window = max(3, len(region) // 5)
    baseline = float(np.median(region[:baseline_window]))
    peak = float(np.max(region))
    threshold = baseline + max((peak - baseline) * 0.3, 1.2)

    for offset, value in enumerate(region):
        if value >= threshold:
            if from_end:
                return bounded_end - offset
            return bounded_start + offset

    fallback = int(np.argmax(region))
    if from_end:
        return bounded_end - fallback
    return bounded_start + fallback


def _color_transition_index(
    values: np.ndarray, threshold: float, start_idx: int, end_idx: int, from_end: bool = False
) -> int:
    bounded_start = max(start_idx, 0)
    bounded_end = min(end_idx, len(values) - 1)
    if bounded_end <= bounded_start:
        return bounded_start

    segment = values[bounded_start : bounded_end + 1]
    traversed = segment[::-1] if from_end else segment
    run_length = 0
    for idx, value in enumerate(traversed):
        if value >= threshold:
            run_length += 1
            if run_length >= 4:
                pos = idx - 3
                if from_end:
                    return bounded_end - pos
                return bounded_start + pos
        else:
            run_length = 0
    return bounded_start if not from_end else bounded_end


def _detect_inner_frame(card_image: np.ndarray) -> Tuple[int, int, int, int]:
    height, width = card_image.shape[:2]
    grayscale = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(grayscale, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(grayscale, cv2.CV_32F, 0, 1, ksize=3)
    profile_x = _smooth(np.mean(np.abs(grad_x), axis=0))
    profile_y = _smooth(np.mean(np.abs(grad_y), axis=1))

    sample = max(3, min(width, height) // 35)
    left_ref = card_image[:, :sample, :].mean(axis=(0, 1))
    right_ref = card_image[:, -sample:, :].mean(axis=(0, 1))
    top_ref = card_image[:sample, :, :].mean(axis=(0, 1))
    bottom_ref = card_image[-sample:, :, :].mean(axis=(0, 1))
    col_mean = card_image.mean(axis=0)
    row_mean = card_image.mean(axis=1)
    left_dist = np.linalg.norm(col_mean - left_ref, axis=1)
    right_dist = np.linalg.norm(col_mean - right_ref, axis=1)
    top_dist = np.linalg.norm(row_mean - top_ref, axis=1)
    bottom_dist = np.linalg.norm(row_mean - bottom_ref, axis=1)

    left_window = (
        int(width * INNER_FRAME_DETECTION.left_window_start_ratio),
        int(width * INNER_FRAME_DETECTION.left_window_end_ratio),
    )
    right_window = (
        int(width * INNER_FRAME_DETECTION.right_window_start_ratio),
        int(width * INNER_FRAME_DETECTION.right_window_end_ratio),
    )
    top_window = (
        int(height * INNER_FRAME_DETECTION.top_window_start_ratio),
        int(height * INNER_FRAME_DETECTION.top_window_end_ratio),
    )
    bottom_window = (
        int(height * INNER_FRAME_DETECTION.bottom_window_start_ratio),
        int(height * INNER_FRAME_DETECTION.bottom_window_end_ratio),
    )

    color_threshold = INNER_FRAME_DETECTION.color_threshold
    left_by_color = _color_transition_index(left_dist, color_threshold, left_window[0], left_window[1])
    right_by_color = _color_transition_index(
        right_dist,
        color_threshold,
        right_window[0],
        right_window[1],
        from_end=True,
    )
    top_by_color = _color_transition_index(top_dist, color_threshold, top_window[0], top_window[1])
    bottom_by_color = _color_transition_index(
        bottom_dist,
        color_threshold,
        bottom_window[0],
        bottom_window[1],
        from_end=True,
    )

    left_by_grad = _edge_transition_index(profile_x, left_window[0], left_window[1])
    right_by_grad = _edge_transition_index(profile_x, right_window[0], right_window[1], from_end=True)
    top_by_grad = _edge_transition_index(profile_y, top_window[0], top_window[1])
    bottom_by_grad = _edge_transition_index(profile_y, bottom_window[0], bottom_window[1], from_end=True)

    inner_left = int(round((left_by_color * 0.65) + (left_by_grad * 0.35)))
    inner_right = int(round((right_by_color * 0.65) + (right_by_grad * 0.35)))
    inner_top = int(round((top_by_color * 0.65) + (top_by_grad * 0.35)))
    inner_bottom = int(round((bottom_by_color * 0.65) + (bottom_by_grad * 0.35)))

    inner_left = max(1, min(inner_left, int(width * 0.20)))
    inner_right = min(width - 2, max(inner_right, int(width * 0.80)))
    inner_top = max(1, min(inner_top, int(height * 0.20)))
    inner_bottom = min(height - 2, max(inner_bottom, int(height * 0.80)))

    if inner_right <= inner_left + 10:
        inner_left = int(width * 0.08)
        inner_right = int(width * 0.92)
    if inner_bottom <= inner_top + 10:
        inner_top = int(height * 0.08)
        inner_bottom = int(height * 0.92)
    return inner_left, inner_right, inner_top, inner_bottom


def analyze_borders(card_image: np.ndarray) -> Tuple[BorderRatios, BorderAnalysisDebug]:
    height, width = card_image.shape[:2]
    inner_left, inner_right, inner_top, inner_bottom = _detect_inner_frame(card_image)

    result = calculate_ratios_from_bounds(width, height, inner_left, inner_right, inner_top, inner_bottom)
    debug = BorderAnalysisDebug(
        warped_card_image=card_image,
        inner_left_x=inner_left,
        inner_right_x=inner_right,
        inner_top_y=inner_top,
        inner_bottom_y=inner_bottom,
    )
    return result, debug


def calculate_ratios_from_bounds(
    image_width: int,
    image_height: int,
    inner_left: int,
    inner_right: int,
    inner_top: int,
    inner_bottom: int,
) -> BorderRatios:
    left_px = max(inner_left, 1)
    right_px = max((image_width - 1) - inner_right, 1)
    top_px = max(inner_top, 1)
    bottom_px = max((image_height - 1) - inner_bottom, 1)
    left_right_ratio = _ratio_pair(left_px, right_px)
    top_bottom_ratio = _ratio_pair(top_px, bottom_px)
    in_window = 45 <= left_right_ratio[0] <= 55 and 45 <= top_bottom_ratio[0] <= 55
    return BorderRatios(
        left_px=left_px,
        right_px=right_px,
        top_px=top_px,
        bottom_px=bottom_px,
        left_right_ratio=left_right_ratio,
        top_bottom_ratio=top_bottom_ratio,
        in_45_55_range=in_window,
    )


def create_visualization(debug: BorderAnalysisDebug, inner_border_bgr: Tuple[int, int, int] = (255, 0, 255)) -> np.ndarray:
    visualized = debug.warped_card_image.copy()
    image_height, image_width = visualized.shape[:2]

    cv2.rectangle(
        visualized,
        (debug.inner_left_x, debug.inner_top_y),
        (debug.inner_right_x, debug.inner_bottom_y),
        inner_border_bgr,
        1,
    )
    return cv2.cvtColor(visualized, cv2.COLOR_BGR2RGB)
