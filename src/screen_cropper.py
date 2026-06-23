"""
screen_cropper.py

Dynamic laptop-screen cropper for angled MCQ/exam photos.

Goal:
- Find the bright white laptop/exam screen area.
- Perspective-correct it.
- Keep the actual white question screen safe.
- Do NOT remove proctor section or question text.

Dependencies:
    pip install opencv-python pillow numpy
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import cv2
import numpy as np
from PIL import Image


@dataclass
class CropConfig:
    brightness_threshold: int = 170
    max_saturation: int = 110
    min_area_ratio: float = 0.08
    safety_expand_ratio: float = 0.03
    morph_kernel_ratio: float = 0.018
    debug: bool = False


@dataclass
class CropResult:
    image: Image.Image
    success: bool
    reason: str
    debug_image: Optional[Image.Image] = None
    mask_image: Optional[Image.Image] = None
    meta: Optional[Dict[str, Any]] = None


def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.astype("float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect = np.zeros((4, 2), dtype="float32")
    rect[0] = pts[np.argmin(s)]      # top-left
    rect[2] = pts[np.argmax(s)]      # bottom-right
    rect[1] = pts[np.argmin(diff)]   # top-right
    rect[3] = pts[np.argmax(diff)]   # bottom-left
    return rect


def _expand_quad(quad: np.ndarray, expand_ratio: float, w: int, h: int) -> np.ndarray:
    center = quad.mean(axis=0)
    expanded = center + (quad - center) * (1.0 + expand_ratio)
    expanded[:, 0] = np.clip(expanded[:, 0], 0, w - 1)
    expanded[:, 1] = np.clip(expanded[:, 1], 0, h - 1)
    return expanded.astype("float32")


def _four_point_warp(image_bgr: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    tl, tr, br, bl = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    max_width = max(max_width, 100)
    max_height = max(max_height, 100)

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image_bgr, matrix, (max_width, max_height))


def _find_best_bright_screen_quad(image_bgr: np.ndarray, config: CropConfig) -> Tuple[Optional[np.ndarray], np.ndarray, str]:
    h, w = image_bgr.shape[:2]
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]

    # Bright + low/medium saturation usually represents the white exam screen.
    mask = ((v >= config.brightness_threshold) & (s <= config.max_saturation)).astype(np.uint8) * 255

    # Remove tiny holes/text and connect screen parts.
    k = max(7, int(min(h, w) * config.morph_kernel_ratio))
    if k % 2 == 0:
        k += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, mask, "No bright screen contour found"

    min_area = config.min_area_ratio * w * h
    candidates = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        hull = cv2.convexHull(cnt)
        peri = cv2.arcLength(hull, True)
        approx = cv2.approxPolyDP(hull, 0.025 * peri, True)

        if len(approx) == 4:
            quad = approx.reshape(4, 2).astype("float32")
        else:
            rect = cv2.minAreaRect(hull)
            quad = cv2.boxPoints(rect).astype("float32")

        x, y, bw, bh = cv2.boundingRect(quad.astype(np.int32))
        aspect = bw / max(bh, 1)
        if aspect < 0.8 or aspect > 3.8:
            continue

        # Prefer large bright screen-like area near the center, not small lamps/white boxes.
        cx, cy = x + bw / 2, y + bh / 2
        center_penalty = abs(cx - w / 2) / w + abs(cy - h / 2) / h
        score = area * (1.0 - min(center_penalty, 0.75))
        candidates.append((score, area, quad))

    if not candidates:
        # Fallback: largest bright bbox, still safer than returning a wrong tight crop.
        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area < min_area:
            return None, mask, "Bright region too small"
        rect = cv2.minAreaRect(cv2.convexHull(cnt))
        quad = cv2.boxPoints(rect).astype("float32")
        return quad, mask, "Fallback minAreaRect used"

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][2], mask, "OK"


def crop_laptop_screen(image: Image.Image | str, config: Optional[CropConfig] = None) -> CropResult:
    """
    Crop and deskew the bright laptop/exam screen area.

    Args:
        image: PIL image or image path.
        config: CropConfig.

    Returns:
        CropResult with cropped PIL image. If detection fails, returns original image with success=False.
    """
    config = config or CropConfig()

    if isinstance(image, str):
        pil = Image.open(image).convert("RGB")
    else:
        pil = image.convert("RGB")

    rgb = np.array(pil)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]

    quad, mask, reason = _find_best_bright_screen_quad(bgr, config)
    debug_pil = None
    mask_pil = Image.fromarray(mask).convert("RGB") if config.debug else None

    if quad is None:
        return CropResult(
            image=pil,
            success=False,
            reason=reason,
            debug_image=None,
            mask_image=mask_pil,
            meta={"original_size": (w, h)},
        )

    expanded_quad = _expand_quad(quad, config.safety_expand_ratio, w, h)
    warped = _four_point_warp(bgr, expanded_quad)

    if config.debug:
        dbg = bgr.copy()
        cv2.polylines(dbg, [quad.astype(np.int32)], True, (0, 0, 255), 5)
        cv2.polylines(dbg, [expanded_quad.astype(np.int32)], True, (0, 255, 0), 5)
        debug_pil = Image.fromarray(cv2.cvtColor(dbg, cv2.COLOR_BGR2RGB))

    out = Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
    return CropResult(
        image=out,
        success=True,
        reason=reason,
        debug_image=debug_pil,
        mask_image=mask_pil,
        meta={
            "original_size": (w, h),
            "cropped_size": out.size,
            "quad": expanded_quad.tolist(),
            "brightness_threshold": config.brightness_threshold,
            "max_saturation": config.max_saturation,
            "safety_expand_ratio": config.safety_expand_ratio,
        },
    )


def crop_laptop_screen_file(
    input_path: str,
    output_path: str,
    config: Optional[CropConfig] = None,
) -> CropResult:
    result = crop_laptop_screen(input_path, config)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    result.image.save(output_path)
    return result
