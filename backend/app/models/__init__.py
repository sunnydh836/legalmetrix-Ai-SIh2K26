"""ORM models for LegalMetrix AI."""
from app.core.database import Base
from app.models.base import TimestampMixin, JSONType
from app.models.user import User
from app.models.product import Product
from app.models.scan_session import ScanSession
from app.models.scan_image import ScanImage
from app.models.image_quality import ImageQualityMetric
from app.models.ocr_block import OCRBlock
from app.models.declaration import Declaration, declaration_ocr_blocks
from app.models.compliance_rule import ComplianceRule
from app.models.compliance_finding import ComplianceFinding
from app.models.report import Report
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "TimestampMixin",
    "JSONType",
    "User",
    "Product",
    "ScanSession",
    "ScanImage",
    "ImageQualityMetric",
    "OCRBlock",
    "Declaration",
    "declaration_ocr_blocks",
    "ComplianceRule",
    "ComplianceFinding",
    "Report",
    "AuditLog",
]
