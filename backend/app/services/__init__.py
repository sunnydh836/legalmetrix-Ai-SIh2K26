"""Service abstractions and dependency providers."""
from app.services.image_quality_service import (
    ImageQualityServiceInterface,
    MockImageQualityService,
    get_image_quality_service,
)
from app.services.ocr_service import (
    OCRServiceInterface,
    MockOCRService,
    get_ocr_service,
)
from app.services.declaration_service import (
    DeclarationServiceInterface,
    MockDeclarationService,
    get_declaration_service,
)
from app.services.rule_service import (
    RuleServiceInterface,
    DeterministicRuleService,
    get_rule_service,
)

__all__ = [
    "ImageQualityServiceInterface",
    "MockImageQualityService",
    "get_image_quality_service",
    "OCRServiceInterface",
    "MockOCRService",
    "get_ocr_service",
    "DeclarationServiceInterface",
    "MockDeclarationService",
    "get_declaration_service",
    "RuleServiceInterface",
    "DeterministicRuleService",
    "get_rule_service",
]
