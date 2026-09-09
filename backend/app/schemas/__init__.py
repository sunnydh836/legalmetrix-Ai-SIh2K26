"""Pydantic schemas and domain contracts."""
from app.schemas.common import (
    ApiResponse,
    BoundingBox,
    ImageQualityResult,
)
from app.schemas.ocr import (
    OCRBlockCreate,
    OCRBlockItem,
    OCRBlockResponse,
    OCRResult,
)
from app.schemas.declaration import (
    DeclarationBase,
    DeclarationCreate,
    DeclarationResponse,
    DeclarationReviewUpdate,
)
from app.schemas.compliance import (
    ComplianceFindingBase,
    ComplianceFindingCreate,
    ComplianceFindingResponse,
    ComplianceResult,
    ComplianceRuleBase,
    ComplianceRuleCreate,
    ComplianceRuleResponse,
    RuleCondition,
    RuleDefinition,
)
from app.schemas.scan import (
    ScanImageBase,
    ScanImageCreate,
    ScanImageResponse,
    ScanSessionBase,
    ScanSessionCreate,
    ScanSessionResponse,
)
from app.schemas.report import (
    ReportCreate,
    ReportResponse,
)
from app.schemas.auth import (
    LoginRequest,
    TokenPayload,
    TokenResponse,
    UserBase,
    UserCreate,
    UserPublic,
)

__all__ = [
    "ApiResponse",
    "BoundingBox",
    "ImageQualityResult",
    "OCRBlockCreate",
    "OCRBlockItem",
    "OCRBlockResponse",
    "OCRResult",
    "DeclarationBase",
    "DeclarationCreate",
    "DeclarationResponse",
    "DeclarationReviewUpdate",
    "ComplianceFindingBase",
    "ComplianceFindingCreate",
    "ComplianceFindingResponse",
    "ComplianceResult",
    "ComplianceRuleBase",
    "ComplianceRuleCreate",
    "ComplianceRuleResponse",
    "RuleCondition",
    "RuleDefinition",
    "ScanImageBase",
    "ScanImageCreate",
    "ScanImageResponse",
    "ScanSessionBase",
    "ScanSessionCreate",
    "ScanSessionResponse",
    "ReportCreate",
    "ReportResponse",
    "LoginRequest",
    "TokenPayload",
    "TokenResponse",
    "UserBase",
    "UserCreate",
    "UserPublic",
]
