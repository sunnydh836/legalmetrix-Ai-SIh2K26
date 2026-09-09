from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import ImageQualityStatus, ImageQualityWarning


class BoundingBox(BaseModel):
    """Normalized or pixel coordinates of a detected text region."""
    x1: int = Field(..., description="Top-left X coordinate")
    y1: int = Field(..., description="Top-left Y coordinate")
    x2: int = Field(..., description="Bottom-right X coordinate")
    y2: int = Field(..., description="Bottom-right Y coordinate")


class ImageQualityResult(BaseModel):
    """Result of image quality evaluation before OCR."""
    scan_image_id: Optional[str] = None
    blur_score: float = Field(..., description="Laplacian variance or equivalent sharpness score")
    glare_score: float = Field(..., description="Fraction of overexposed/specular reflection pixels [0.0 - 1.0]")
    resolution: Dict[str, int] = Field(..., description="Image dimensions: {'width': int, 'height': int}")
    orientation: int = Field(0, description="Estimated rotation angle in degrees (0, 90, 180, 270)")
    quality_status: ImageQualityStatus = Field(..., description="ACCEPTED, RECAPTURE_RECOMMENDED, or REVIEW")
    warnings: List[ImageQualityWarning] = Field(default_factory=list, description="List of quality warnings detected")
    details: Optional[Dict[str, Any]] = None


class ApiResponse(BaseModel):
    """Standard unified API response wrapper."""
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None
