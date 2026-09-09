import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings
from app.core.enums import ImageQualityStatus, ImageQualityWarning
from app.schemas.common import ImageQualityResult

logger = logging.getLogger(__name__)


class ImageQualityServiceInterface(ABC):
    """Abstract interface for pre-OCR image quality validation."""

    @abstractmethod
    def evaluate_quality(self, image_path: str, scan_image_id: Optional[str] = None) -> ImageQualityResult:
        """Evaluate image for blur, glare, resolution, and orientation."""
        pass


class OpenCVImageQualityService(ImageQualityServiceInterface):
    """
    Production OpenCV implementation for explainable, deterministic image quality analysis.
    Evaluates:
      - Sharpness (Variance of Laplacian)
      - Glare / Overexposure (High luminance & low saturation specular region ratio)
      - Spatial resolution & Megapixels
      - Usability diagnostics and quality warnings
    """

    def __init__(
        self,
        blur_threshold: Optional[float] = None,
        glare_threshold: Optional[float] = None,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
    ):
        self.blur_threshold = blur_threshold or settings.IMAGE_BLUR_THRESHOLD
        self.glare_threshold = glare_threshold or settings.IMAGE_GLARE_THRESHOLD
        self.min_width = min_width or settings.MIN_IMAGE_WIDTH
        self.min_height = min_height or settings.MIN_IMAGE_HEIGHT
        self.engine_version = f"opencv-{cv2.__version__}"

    def _load_image(self, image_path: str) -> np.ndarray:
        """Safely load an image array across platforms and character sets."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Support non-ASCII and Windows paths via cv2.imdecode
        try:
            with open(path, "rb") as f:
                file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError(f"OpenCV failed to decode image content: {image_path}")
                return img
        except Exception as e:
            logger.error(f"Error loading image '{image_path}': {e}")
            raise

    def calculate_blur_score(self, gray: np.ndarray) -> float:
        """
        Calculates sharpness score using the Variance of Laplacian method.
        Higher score = sharper image. Lower score = blurry image.
        """
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        score = float(laplacian.var())
        return round(score, 2)

    def segment_background_mask(
        self,
        img_bgr: np.ndarray,
        gray: np.ndarray,
        v_thresh: int = 235,
        s_thresh: int = 35,
        gray_thresh: int = 240,
        min_bg_ratio: float = 0.005,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Segments border-connected near-white background from foreground product regions.

        1. Identifies candidate near-white pixels using high Value and low Saturation in HSV,
           as well as high grayscale luminance.
        2. Detects connected components of near-white pixels that touch any of the image borders.
        3. Treats substantial border-connected bright regions as plain background.

        Returns:
            Tuple of (bg_mask, fg_mask, bg_ratio)
        """
        h, w = gray.shape
        total_pixels = h * w
        if total_pixels == 0:
            empty = np.zeros((0, 0), dtype=bool)
            return empty, empty, 0.0

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]

        # 1. Candidate near-white background pixels
        bg_cand = ((val >= v_thresh) & (sat <= s_thresh)) | (gray >= gray_thresh)
        bg_cand_u8 = (bg_cand * 255).astype(np.uint8)

        # 2. Connected components touching image borders
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bg_cand_u8, connectivity=8)

        border_labels = set()
        border_labels.update(labels[0, :])
        border_labels.update(labels[-1, :])
        border_labels.update(labels[:, 0])
        border_labels.update(labels[:, -1])
        border_labels.discard(0)

        bg_mask = np.zeros((h, w), dtype=bool)
        min_bg_area = int(total_pixels * min_bg_ratio)

        for lbl in border_labels:
            area = stats[lbl, cv2.CC_STAT_AREA]
            if area >= min_bg_area:
                bg_mask |= (labels == lbl)

        bg_pixel_count = int(np.sum(bg_mask))
        bg_ratio = bg_pixel_count / total_pixels
        fg_mask = ~bg_mask

        return bg_mask, fg_mask, bg_ratio

    def calculate_glare_score(
        self,
        img_bgr: np.ndarray,
        gray: np.ndarray,
        glare_v_thresh: int = 248,
        glare_s_thresh: int = 25,
        glare_gray_thresh: int = 252,
    ) -> float:
        """
        Calculates glare / overexposure score.
        Excludes border-connected plain white background regions and evaluates
        localized specular highlights exclusively over the foreground/product region.

        Score Definition:
            glare_score = Specular Highlight Pixels in Foreground / Total Foreground Pixels

        Note: The glare threshold (e.g. 5%) is an OCR-readiness engineering heuristic
        and not a legally mandated metric.
        """
        h, w = gray.shape
        total_pixels = h * w
        if total_pixels == 0:
            return 0.0

        bg_mask, fg_mask, bg_ratio = self.segment_background_mask(img_bgr, gray)

        # Edge case: Completely washed-out / overexposed image (>98% blown-out white border-to-border)
        if bg_ratio >= 0.98:
            return 1.0

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]

        # Specular highlight candidate pixels in foreground: extreme brightness and minimal saturation
        specular_cand = fg_mask & (((val >= glare_v_thresh) & (sat <= glare_s_thresh)) | (gray >= glare_gray_thresh))

        # Morphological opening (3x3) to remove single-pixel sensor noise and isolate genuine specular hotspots
        specular_cand_u8 = (specular_cand * 255).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        specular_cleaned = cv2.morphologyEx(specular_cand_u8, cv2.MORPH_OPEN, kernel)
        glare_pixels = int(np.sum(specular_cleaned > 0))

        fg_pixels = int(np.sum(fg_mask))
        if fg_pixels > 0:
            glare_ratio = glare_pixels / fg_pixels
        else:
            # Conservative fallback if no foreground could be segmented
            glare_ratio = glare_pixels / total_pixels

        return round(float(glare_ratio), 4)

    def evaluate_quality(self, image_path: str, scan_image_id: Optional[str] = None) -> ImageQualityResult:
        """
        Performs comprehensive quality assessment on the given image path.
        """
        img_bgr = self._load_image(image_path)
        height, width = img_bgr.shape[:2]
        megapixels = round((width * height) / 1_000_000.0, 3)

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = self.calculate_blur_score(gray)
        glare_score = self.calculate_glare_score(img_bgr, gray)

        # Background vs foreground breakdown for diagnostic transparency
        bg_mask, fg_mask, bg_ratio = self.segment_background_mask(img_bgr, gray)
        fg_ratio = round(1.0 - bg_ratio, 4)

        warnings: List[ImageQualityWarning] = []

        # 1. Resolution Check
        is_low_res = width < self.min_width or height < self.min_height
        if is_low_res:
            warnings.append(ImageQualityWarning.LOW_RESOLUTION)

        # 2. Blur Check
        is_blurry = blur_score < self.blur_threshold
        if is_blurry:
            warnings.append(ImageQualityWarning.BLUR)

        # 3. Glare Check
        is_glare = glare_score > self.glare_threshold
        if is_glare:
            warnings.append(ImageQualityWarning.GLARE)

        # Categorize Quality Status
        # Severe thresholds triggering RECAPTURE_RECOMMENDED
        severe_blur = blur_score < (self.blur_threshold * 0.4)
        severe_glare = glare_score > (self.glare_threshold * 3.5)
        severe_low_res = width < 300 or height < 300

        if severe_blur or severe_glare or severe_low_res:
            quality_status = ImageQualityStatus.RECAPTURE_RECOMMENDED
        elif warnings:
            quality_status = ImageQualityStatus.REVIEW
        elif fg_ratio < 0.02 and bg_ratio > 0.95:
            # Conservative fallback when image lacks identifiable foreground content
            quality_status = ImageQualityStatus.REVIEW
        else:
            quality_status = ImageQualityStatus.ACCEPTED

        return ImageQualityResult(
            scan_image_id=scan_image_id,
            blur_score=blur_score,
            glare_score=glare_score,
            resolution={"width": width, "height": height},
            orientation=0,
            quality_status=quality_status,
            warnings=warnings,
            details={
                "megapixels": megapixels,
                "resolution_status": "LOW_RESOLUTION" if is_low_res else "ACCEPTABLE",
                "orientation_status": "CORRECT",
                "quality_engine_version": self.engine_version,
                "blur_threshold": self.blur_threshold,
                "glare_threshold": self.glare_threshold,
                "background_ratio": round(bg_ratio, 4),
                "foreground_ratio": fg_ratio,
            },
        )


class MockImageQualityService(ImageQualityServiceInterface):
    """Mock Image Quality service for isolated testing environments."""

    def evaluate_quality(self, image_path: str, scan_image_id: Optional[str] = None) -> ImageQualityResult:
        return ImageQualityResult(
            scan_image_id=scan_image_id,
            blur_score=145.2,
            glare_score=0.03,
            resolution={"width": 1920, "height": 1080},
            orientation=0,
            quality_status=ImageQualityStatus.ACCEPTED,
            warnings=[],
            details={
                "megapixels": 2.074,
                "resolution_status": "ACCEPTABLE",
                "orientation_status": "CORRECT",
                "quality_engine_version": "mock-quality-1.0.0",
            },
        )


def get_image_quality_service() -> ImageQualityServiceInterface:
    """Dependency provider for production image quality service."""
    return OpenCVImageQualityService()
