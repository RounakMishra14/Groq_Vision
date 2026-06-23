"""
safe_image_compressor.py

Safe post-crop resize + JPEG compression for Groq Vision MCQ extraction.

Recommended production default after v7 crop:
    width=900, quality=50

This is safer than W700/Q40, which failed on larger validation.

Dependencies:
    pip install pillow
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from PIL import Image, ImageOps


@dataclass
class CompressionConfig:
    target_width: int = 900
    jpeg_quality: int = 50
    min_width_no_resize: int = 900
    upscale: bool = False
    background: str = "white"
    optimize: bool = True
    progressive: bool = True


@dataclass
class CompressionResult:
    image: Image.Image
    success: bool
    reason: str
    meta: Dict[str, Any]


def compress_for_groq(
    image: Image.Image | str,
    config: Optional[CompressionConfig] = None,
) -> CompressionResult:
    """
    Resize safely and prepare RGB image for JPEG saving.

    Args:
        image: PIL image or file path.
        config: CompressionConfig.

    Returns:
        CompressionResult containing compressed-size image in memory.
    """
    config = config or CompressionConfig()

    if isinstance(image, str):
        pil = Image.open(image)
    else:
        pil = image

    pil = ImageOps.exif_transpose(pil).convert("RGB")
    original_w, original_h = pil.size

    should_resize = original_w > config.target_width or (config.upscale and original_w < config.target_width)

    if should_resize:
        new_w = config.target_width
        new_h = max(1, int(original_h * (new_w / original_w)))
        pil = pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        reason = "resized"
    else:
        reason = "kept_original_size"

    return CompressionResult(
        image=pil,
        success=True,
        reason=reason,
        meta={
            "original_size": (original_w, original_h),
            "final_size": pil.size,
            "target_width": config.target_width,
            "jpeg_quality": config.jpeg_quality,
            "upscale": config.upscale,
        },
    )


def save_jpeg_for_groq(
    image: Image.Image,
    output_path: str,
    config: Optional[CompressionConfig] = None,
) -> Dict[str, Any]:
    config = config or CompressionConfig()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    image.convert("RGB").save(
        output_path,
        format="JPEG",
        quality=config.jpeg_quality,
        optimize=config.optimize,
        progressive=config.progressive,
    )
    return {
        "output_path": output_path,
        "size_bytes": os.path.getsize(output_path),
        "size_kb": round(os.path.getsize(output_path) / 1024, 2),
        "jpeg_quality": config.jpeg_quality,
        "image_size": image.size,
    }


def compress_file_for_groq(
    input_path: str,
    output_path: str,
    config: Optional[CompressionConfig] = None,
) -> Dict[str, Any]:
    config = config or CompressionConfig()
    result = compress_for_groq(input_path, config)
    save_meta = save_jpeg_for_groq(result.image, output_path, config)
    return {**result.meta, **save_meta, "reason": result.reason}
