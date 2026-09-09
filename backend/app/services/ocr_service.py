import logging
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from app.schemas.common import BoundingBox
from app.schemas.ocr import OCRBlockItem, OCRResult
from app.services.image_preprocessing_service import ImagePreprocessingService

logger = logging.getLogger(__name__)


class OCRServiceInterface(ABC):
    """Abstract interface for Optical Character Recognition engines."""

    @abstractmethod
    def process_image(self, image_path: str, scan_image_id: Optional[str] = None) -> OCRResult:
        """Extract text blocks with geometric bounding boxes from an image."""
        pass


class PaddleOCRService(OCRServiceInterface):
    """
    Production local OCR engine using RapidOCR / PaddleOCR ONNX Runtime backend.
    
    Guarantees:
      - 100% offline and local execution (no external cloud API)
      - Extracts text, confidence [0.0 - 1.0], polygon geometry and bounding boxes
      - Coordinate space maps 1:1 to the original evidence image
      - Deterministic reading order sorting
      - Measures processing duration in milliseconds
    """

    _engine_instance = None

    def __init__(self):
        self.engine_name = "paddleocr-rapidocr"
        self.version = "1.2.3"

    @classmethod
    def _get_engine(cls):
        """Lazy-initialize singleton OCR engine instance to avoid redundant model reloads."""
        if cls._engine_instance is None:
            try:
                from rapidocr_onnxruntime import RapidOCR

                logger.info("Initializing RapidOCR ONNX Runtime engine...")
                cls._engine_instance = RapidOCR()
                logger.info("RapidOCR engine initialized successfully.")
            except ImportError as e:
                logger.error(f"RapidOCR is not installed: {e}")
                raise RuntimeError(
                    "RapidOCR engine not found. Ensure rapidocr-onnxruntime is installed."
                )
        return cls._engine_instance

    @staticmethod
    def _sort_reading_order(blocks: List[OCRBlockItem]) -> List[OCRBlockItem]:
        """
        Sort detected OCR text blocks in natural human reading order:
        Top-to-bottom, then left-to-right.
        Uses adaptive vertical band grouping based on average block height.
        """
        if not blocks:
            return []

        avg_height = sum(b.bbox.y2 - b.bbox.y1 for b in blocks) / len(blocks)
        band_tolerance = max(10, avg_height * 0.5)

        # Sort primarily by vertical coordinate rounded to band, then horizontal X
        def sort_key(b: OCRBlockItem):
            band = int(b.bbox.y1 / band_tolerance)
            return (band, b.bbox.x1)

        sorted_blocks = sorted(blocks, key=sort_key)
        for idx, block in enumerate(sorted_blocks):
            block.block_order = idx

        return sorted_blocks

    def process_image(self, image_path: str, scan_image_id: Optional[str] = None) -> OCRResult:
        """
        Run local OCR on the stored image and return structured evidence blocks.
        """
        start_time = time.perf_counter()

        # Load safe working copy in memory
        img = ImagePreprocessingService.prepare_ocr_image(image_path)
        orig_h, orig_w = img.shape[:2]

        # Adaptive OCR scaling: upscale small working copy in-memory for fine-print readability
        max_edge = max(orig_h, orig_w)
        scale_factor = 1.0
        if max_edge < 1800:
            scale_factor = min(2.5, 1800.0 / float(max_edge))

        if scale_factor > 1.05:
            scaled_w = int(orig_w * scale_factor)
            scaled_h = int(orig_h * scale_factor)
            ocr_input = cv2.resize(img, (scaled_w, scaled_h), interpolation=cv2.INTER_CUBIC)
        else:
            ocr_input = img

        engine = self._get_engine()
        raw_result, _elapse = engine(ocr_input)

        blocks: List[OCRBlockItem] = []

        if raw_result:
            for item in raw_result:
                # RapidOCR format: [polygon, text, confidence]
                # polygon: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                if len(item) < 3:
                    continue

                poly_coords = item[0]
                text = str(item[1]).strip()
                raw_conf = item[2]

                if not text:
                    continue

                # Clean and parse confidence
                try:
                    conf = float(raw_conf)
                except (ValueError, TypeError):
                    conf = 0.5
                conf = max(0.0, min(1.0, round(conf, 4)))

                # Map coordinates 1:1 back to original image coordinate space
                polygon: List[List[float]] = []
                for pt in poly_coords:
                    pt_x = float(pt[0]) / scale_factor
                    pt_y = float(pt[1]) / scale_factor
                    x = max(0.0, min(float(orig_w), pt_x))
                    y = max(0.0, min(float(orig_h), pt_y))
                    polygon.append([round(x, 1), round(y, 1)])

                # Compute rectangular bounding box from polygon
                min_x = int(min(p[0] for p in polygon))
                min_y = int(min(p[1] for p in polygon))
                max_x = int(max(p[0] for p in polygon))
                max_y = int(max(p[1] for p in polygon))

                bbox = BoundingBox(
                    x1=min_x,
                    y1=min_y,
                    x2=max_x,
                    y2=max_y,
                )

                blocks.append(
                    OCRBlockItem(
                        text=text,
                        confidence=conf,
                        bbox=bbox,
                        polygon=polygon,
                        block_order=0,
                    )
                )

        # Sort into reading order
        ordered_blocks = self._sort_reading_order(blocks)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"OCR completed for image '{scan_image_id}' in {elapsed_ms}ms. "
            f"Extracted {len(ordered_blocks)} text blocks."
        )

        return OCRResult(
            scan_image_id=scan_image_id,
            engine=self.engine_name,
            engine_version=self.version,
            processing_duration_ms=elapsed_ms,
            blocks=ordered_blocks,
        )


class MockOCRService(OCRServiceInterface):
    """Mock OCR implementation for testing and development environments."""

    def __init__(self, engine_name: str = "mock-paddleocr", version: str = "2.7.0"):
        self.engine_name = engine_name
        self.version = version

    def process_image(self, image_path: str, scan_image_id: Optional[str] = None) -> OCRResult:
        sample_blocks = [
            OCRBlockItem(
                text="MRP Rs. 120.00 (Incl. of all taxes)",
                confidence=0.96,
                bbox=BoundingBox(x1=100, y1=250, x2=450, y2=290),
                polygon=[[100.0, 250.0], [450.0, 250.0], [450.0, 290.0], [100.0, 290.0]],
                block_order=0,
            ),
            OCRBlockItem(
                text="Net Quantity: 500 g",
                confidence=0.94,
                bbox=BoundingBox(x1=100, y1=310, x2=320, y2=345),
                polygon=[[100.0, 310.0], [320.0, 310.0], [320.0, 345.0], [100.0, 345.0]],
                block_order=1,
            ),
            OCRBlockItem(
                text="Mfg Date: 01/2026",
                confidence=0.91,
                bbox=BoundingBox(x1=100, y1=360, x2=280, y2=395),
                polygon=[[100.0, 360.0], [280.0, 360.0], [280.0, 395.0], [100.0, 395.0]],
                block_order=2,
            ),
            OCRBlockItem(
                text="Customer Care: 1800-111-222 | care@example.com",
                confidence=0.89,
                bbox=BoundingBox(x1=100, y1=410, x2=550, y2=445),
                polygon=[[100.0, 410.0], [550.0, 410.0], [550.0, 445.0], [100.0, 445.0]],
                block_order=3,
            ),
        ]
        return OCRResult(
            scan_image_id=scan_image_id,
            engine=self.engine_name,
            engine_version=self.version,
            processing_duration_ms=45,
            blocks=sample_blocks,
        )


def get_ocr_service() -> OCRServiceInterface:
    """Dependency provider for production OCR service."""
    return PaddleOCRService()
