"""
image_processor.py

Prepares uploaded MCQ/laptop-screen photos before sending them to Groq Vision.

Pipeline:
    original image
    -> v7 bright inner laptop-screen crop
    -> safe resize/compression
    -> saved JPEG file for Groq

Dependencies:
    pip install opencv-python pillow numpy
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

from PIL import Image

from src.screen_cropper import crop_laptop_screen, CropConfig
from src.image_compressor import (
    compress_for_groq,
    save_jpeg_for_groq,
    CompressionConfig,
)


@dataclass
class GroqImagePrepConfig:
    """Safe defaults based on your validation results."""

    crop_enabled: bool = True
    compression_enabled: bool = True

    # v7 crop defaults
    brightness_threshold: int = 170
    max_saturation: int = 110
    safety_expand_ratio: float = 0.03

    # Safe production compression defaults
    # W700/Q40 was too aggressive on larger validation.
    target_width: int = 900
    jpeg_quality: int = 50

    debug: bool = False


@dataclass
class GroqImagePrepResult:
    input_path: str
    output_path: str
    success: bool
    reason: str
    meta: Dict[str, Any]


def prepare_image_for_groq(
    input_path: str,
    config: Optional[GroqImagePrepConfig] = None,
) -> GroqImagePrepResult:
    """
    Crop + compress one image and return the processed image path.

    This is the function your Streamlit UI should call before extract_mcq_with_groq().
    """

    config = config or GroqImagePrepConfig()

    original_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0

    with Image.open(input_path) as img:
        working_image = img.convert("RGB")
        original_dimensions = working_image.size

    crop_success = False
    crop_reason = "crop_disabled"
    crop_meta: Dict[str, Any] = {}

    if config.crop_enabled:
        crop_result = crop_laptop_screen(
            input_path,
            CropConfig(
                brightness_threshold=config.brightness_threshold,
                max_saturation=config.max_saturation,
                safety_expand_ratio=config.safety_expand_ratio,
                debug=config.debug,
            ),
        )
        working_image = crop_result.image.convert("RGB")
        crop_success = crop_result.success
        crop_reason = crop_result.reason
        crop_meta = crop_result.meta or {}

    compression_reason = "compression_disabled"
    compression_meta: Dict[str, Any] = {}

    if config.compression_enabled:
        compression_cfg = CompressionConfig(
            target_width=config.target_width,
            jpeg_quality=config.jpeg_quality,
        )
        compression_result = compress_for_groq(working_image, compression_cfg)
        working_image = compression_result.image.convert("RGB")
        compression_reason = compression_result.reason
        compression_meta = compression_result.meta

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="_groq_ready.jpg")
    output_path = temp_file.name
    temp_file.close()

    save_meta = save_jpeg_for_groq(
        working_image,
        output_path,
        CompressionConfig(
            target_width=config.target_width,
            jpeg_quality=config.jpeg_quality,
        ),
    )

    final_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

    return GroqImagePrepResult(
        input_path=input_path,
        output_path=output_path,
        success=True,
        reason=f"crop={crop_reason}; compression={compression_reason}",
        meta={
            "original_dimensions": original_dimensions,
            "original_size_kb": round(original_size / 1024, 2),
            "final_dimensions": working_image.size,
            "final_size_kb": round(final_size / 1024, 2),
            "crop_enabled": config.crop_enabled,
            "crop_success": crop_success,
            "crop_reason": crop_reason,
            "crop_meta": crop_meta,
            "compression_enabled": config.compression_enabled,
            "compression_reason": compression_reason,
            "compression_meta": compression_meta,
            "target_width": config.target_width,
            "jpeg_quality": config.jpeg_quality,
            "output_path": output_path,
            **save_meta,
        },
    )


# Backward-compatible function kept because your existing ui.py imports compress_image.
def compress_image(
    input_path: str,
    max_width: int = 900,
    max_height: int = 1600,  # kept only for compatibility; aspect ratio uses width
    quality: int = 50,
    enabled: bool = True,
) -> str:
    """
    Legacy wrapper. Prefer prepare_image_for_groq().
    """

    if not enabled:
        return input_path

    result = prepare_image_for_groq(
        input_path,
        GroqImagePrepConfig(
            crop_enabled=True,
            compression_enabled=True,
            target_width=max_width,
            jpeg_quality=quality,
        ),
    )
    return result.output_path
