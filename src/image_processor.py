import os
import tempfile
from PIL import Image


def compress_image(
    input_path: str,
    max_width: int = 1200,
    max_height: int = 1600,
    quality: int = 75,
    enabled: bool = True
) -> str:
    """
    Compress and resize image before sending to Groq.
    Returns compressed image path.
    If enabled=False, returns original path.
    """

    if not enabled:
        return input_path

    image = Image.open(input_path)

    image = image.convert("RGB")

    image.thumbnail(
        (max_width, max_height),
        Image.Resampling.LANCZOS
    )

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".jpg"
    )

    compressed_path = temp_file.name
    temp_file.close()

    image.save(
        compressed_path,
        format="JPEG",
        quality=quality,
        optimize=True
    )

    return compressed_path