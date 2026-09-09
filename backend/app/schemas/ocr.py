from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import BoundingBox


class OCRBlockItem(BaseModel):
    """Single OCR detected text segment with bounding box, polygon, and confidence score."""
    text: str = Field(..., description="Recognized text string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="OCR recognition confidence [0.0 - 1.0]")
    bbox: BoundingBox = Field(..., description="Derived rectangular bounding box coordinates")
    polygon: Optional[List[List[float]]] = Field(
        default=None,
        description="4-vertex polygon coordinate list [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]",
    )
    block_order: int = Field(default=0, description="Reading order index (0-indexed)")


class OCRResult(BaseModel):
    """Standardized output contract from OCR engines (PaddleOCR, RapidOCR, etc.)."""
    scan_image_id: Optional[str] = Field(None, description="Associated scan image ID")
    engine: str = Field(default="paddleocr", description="OCR engine identifier")
    engine_version: Optional[str] = Field(default="rapidocr-1.2.3", description="OCR engine model/library version")
    processing_duration_ms: Optional[int] = Field(None, description="Processing duration in milliseconds")
    blocks: List[OCRBlockItem] = Field(default_factory=list, description="List of recognized text blocks in reading order")


class OCRBlockCreate(BaseModel):
    scan_image_id: str
    text: str
    confidence: float
    bbox_x1: int
    bbox_y1: int
    bbox_x2: int
    bbox_y2: int
    polygon: Optional[List[List[float]]] = None
    block_order: int = 0
    ocr_engine: str = "paddleocr"
    ocr_engine_version: Optional[str] = None


class OCRBlockResponse(BaseModel):
    id: str
    scan_image_id: str
    text: str
    confidence: float
    bbox_x1: int
    bbox_y1: int
    bbox_x2: int
    bbox_y2: int
    polygon: Optional[List[List[float]]] = None
    block_order: int = 0
    ocr_engine: str = "paddleocr"
    ocr_engine_version: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScanImageQualityResponse(BaseModel):
    id: str
    scan_image_id: str
    blur_score: float
    glare_score: float
    width: int
    height: int
    megapixels: float
    resolution_status: str
    orientation_status: str
    quality_status: str
    warnings: List[str]
    quality_engine_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageOCRDetailResponse(BaseModel):
    image_id: str
    image_type: str
    original_filename: Optional[str] = None
    preview_url: str
    processing_status: str
    ocr_processing_duration_ms: Optional[int] = None
    quality: Optional[ScanImageQualityResponse] = None
    ocr_blocks: List[OCRBlockResponse] = Field(default_factory=list)


class ScanOCRResponse(BaseModel):
    scan_id: str
    scan_code: str
    status: str
    images: List[ImageOCRDetailResponse] = Field(default_factory=list)


class ProcessScanResponse(BaseModel):
    scan_id: str
    scan_code: str
    status: str
    message: str
    images_processed: int
    images: List[ImageOCRDetailResponse] = Field(default_factory=list)
