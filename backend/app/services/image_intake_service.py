import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
FORMAT_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_DIMENSION = 3500


@dataclass
class ProcessedImage:
    file_bytes: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    file_size: int
    sha256: str


class ImageIntakeService:
    """
    Day 3 Image Intake Pipeline:
    - Safely opens image using Pillow (rejects corrupted/malformed files)
    - Validates allowed image formats (JPEG, PNG, WEBP)
    - Normalizes EXIF orientation
    - Safe non-destructive downscaling for extremely oversized photos (> 3500px)
    - Preserves high sharpness for Day 4 OCR
    - Computes SHA-256 hash for deduplication
    """

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        """Compute SHA-256 hexadecimal digest of raw bytes."""
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def process_image(cls, raw_bytes: bytes, original_filename: Optional[str] = None) -> ProcessedImage:
        """
        Validate, normalize, and process uploaded image bytes.
        Raises ValueError with clear message if image is invalid, corrupted, or unsupported.
        """
        if not raw_bytes or len(raw_bytes) == 0:
            raise ValueError("Uploaded file is empty.")

        try:
            pil_image = Image.open(io.BytesIO(raw_bytes))
            # Verify basic integrity
            image_format = pil_image.format
        except Exception as e:
            logger.warning(f"Failed to decode image: {e}")
            raise ValueError("Malformed or unreadable image file.")

        if not image_format or image_format.upper() not in ALLOWED_FORMATS:
            raise ValueError(
                f"Unsupported image format: '{image_format or 'UNKNOWN'}'. Allowed formats: JPEG, PNG, WEBP."
            )

        fmt_upper = image_format.upper()
        mime_type = ALLOWED_FORMATS[fmt_upper]
        extension = FORMAT_EXTENSIONS[fmt_upper]

        # Normalize EXIF orientation
        try:
            transposed_image = ImageOps.exif_transpose(pil_image)
            if transposed_image is not None:
                pil_image = transposed_image
        except Exception as e:
            logger.warning(f"EXIF orientation normalization warning: {e}")

        # Dimension checks & safe downscaling if extremely large
        orig_width, orig_height = pil_image.size
        target_width, target_height = orig_width, orig_height

        max_edge = max(orig_width, orig_height)
        needs_resize = max_edge > MAX_DIMENSION

        if needs_resize:
            scale_ratio = MAX_DIMENSION / float(max_edge)
            target_width = int(orig_width * scale_ratio)
            target_height = int(orig_height * scale_ratio)
            pil_image = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            logger.info(f"Safely resized oversized image from ({orig_width}, {orig_height}) to ({target_width}, {target_height})")

        # Color mode handling for saving
        if fmt_upper == "JPEG":
            if pil_image.mode in ("RGBA", "LA", "P"):
                # Convert RGBA to RGB with white background for JPEG
                background = Image.new("RGB", pil_image.size, (255, 255, 255))
                if pil_image.mode == "RGBA":
                    background.paste(pil_image, mask=pil_image.split()[3])
                else:
                    background.paste(pil_image.convert("RGB"))
                pil_image = background
            elif pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

        # Re-save processed bytes
        output_buffer = io.BytesIO()
        save_kwargs = {}
        if fmt_upper == "JPEG":
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
            pil_image.save(output_buffer, format="JPEG", **save_kwargs)
        elif fmt_upper == "PNG":
            save_kwargs["optimize"] = True
            pil_image.save(output_buffer, format="PNG", **save_kwargs)
        elif fmt_upper == "WEBP":
            save_kwargs["quality"] = 90
            pil_image.save(output_buffer, format="WEBP", **save_kwargs)
        else:
            pil_image.save(output_buffer, format=fmt_upper)

        processed_bytes = output_buffer.getvalue()
        final_width, final_height = pil_image.size
        final_size = len(processed_bytes)
        sha256_hash = cls.calculate_sha256(processed_bytes)

        return ProcessedImage(
            file_bytes=processed_bytes,
            mime_type=mime_type,
            extension=extension,
            width=final_width,
            height=final_height,
            file_size=final_size,
            sha256=sha256_hash,
        )
