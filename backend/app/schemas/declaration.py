from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import ConfidenceLevel, DeclarationType, ResolutionStatus, ReviewStatus


class DeclarationBase(BaseModel):
    declaration_type: DeclarationType = Field(..., description="Classification from central declaration taxonomy")
    raw_text: str = Field(..., description="Raw text as extracted from label")
    raw_value: Optional[str] = Field(None, description="Extracted substring value")
    normalized_value: Optional[Dict[str, Any]] = Field(None, description="Structured parsed value (amount, unit, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score [0.0 - 1.0]")
    confidence_level: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM, description="Confidence categorization")
    resolution_status: ResolutionStatus = Field(default=ResolutionStatus.NOT_DETECTED, description="System resolution status")
    resolution_reason: Optional[str] = Field(None, description="Reason for the current resolution status")
    canonical_value: Optional[Dict[str, Any]] = Field(None, description="Final canonical structured value")
    candidate_details: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed list of all candidates and their confidence profiles")
    source_ocr_block_id: Optional[str] = Field(None, description="Foreign key to source OCR block if single block")
    source_blocks: Optional[List[str]] = Field(default_factory=list, description="IDs of all contributing OCR blocks")
    bounding_box: Optional[Dict[str, int]] = Field(None, description="Union bounding box {bbox_x1, bbox_y1, bbox_x2, bbox_y2}")
    confidence_breakdown: Optional[Dict[str, Any]] = Field(None, description="Transparent sub-score components")
    has_conflict: bool = Field(default=False, description="Flag indicating conflicting candidates across panels")
    conflict_details: Optional[Dict[str, Any]] = Field(None, description="Details of conflicting values across image panels")
    image_id: Optional[str] = Field(None, description="Associated scan image ID")


class DeclarationCreate(DeclarationBase):
    scan_session_id: str


class DeclarationReviewUpdate(BaseModel):
    review_status: ReviewStatus = Field(default=ReviewStatus.CONFIRMED, description="Updated review state (CONFIRMED, CORRECTED, REJECTED)")
    reviewed_value: Optional[Dict[str, Any]] = Field(None, description="Corrected/verified value by reviewer")
    review_notes: Optional[str] = Field(None, description="Optional reviewer remarks")


class DeclarationResponse(DeclarationBase):
    id: str
    scan_session_id: str
    image_id: Optional[str] = None
    machine_extracted_value: Optional[Dict[str, Any]] = None
    reviewed: bool = False
    reviewed_value: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    extractor_version: str = "1.0.0"
    evidence_preview_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ScanDeclarationsResponse(BaseModel):
    scan_id: str
    total_declarations: int
    unreviewed_count: int
    confirmed_count: int
    corrected_count: int
    rejected_count: int
    declarations: List[DeclarationResponse]
    extractor_version: str = "1.0.0"
    extraction_duration_ms: Optional[int] = None


class BenchmarkEvaluationResponse(BaseModel):
    status: str
    labeled_packages_count: int
    threshold_required: int = 50
    message: str
    overall: Optional[Dict[str, float]] = None
    per_declaration_metrics: Optional[Dict[str, Any]] = None
