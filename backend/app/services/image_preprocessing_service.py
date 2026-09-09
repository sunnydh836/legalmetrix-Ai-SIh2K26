import logging
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImagePreprocessingService:
    """
    Modular preprocessing service preparing safe working copies of images for OCR.
    
    IMPORTANT:
    The original evidence image on disk is NEVER modified or overwritten.
    All operations are applied to in-memory working arrays, preserving original
    aspect ratios and coordinate space.
    """

    @staticmethod
    def load_image_bgr(image_path: str) -> np.ndarray:
        """Safely load an image into a BGR numpy array without touching original disk file."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        with open(path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError(f"Failed to decode image from path: {image_path}")
            return img

    @staticmethod
    def enhance_contrast(img_bgr: np.ndarray, clip_limit: float = 2.0, tile_grid_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
        """
        Applies Contrast Limited Adaptive Histogram Equalization (CLAHE) on the L-channel
        in LAB color space. Enhances faint package label text without blowing out highlights.
        """
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        cl = clahe.apply(l_channel)

        enhanced_lab = cv2.merge((cl, a_channel, b_channel))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    @staticmethod
    def gentle_denoise(img_bgr: np.ndarray) -> np.ndarray:
        """
        Gentle bilateral filtering to reduce noise on textured packaging wrappers
        while preserving crisp character edges.
        """
        return cv2.bilateralFilter(img_bgr, d=5, sigmaColor=50, sigmaSpace=50)

    @classmethod
    def prepare_ocr_image(
        cls,
        image_path: str,
        apply_contrast_enhancement: bool = False,
        apply_denoise: bool = False,
    ) -> np.ndarray:
        """
        Returns an in-memory numpy array optimized for OCR inference.
        Default is the clean original image (as PaddleOCR / RapidOCR perform optimal internal normalization).
        """
        img = cls.load_image_bgr(image_path)

        if apply_contrast_enhancement:
            img = cls.enhance_contrast(img)

        if apply_denoise:
            img = cls.gentle_denoise(img)

        return img


def get_image_preprocessing_service() -> ImagePreprocessingService:
    """Dependency provider for image preprocessing service."""
    return ImagePreprocessingService()
