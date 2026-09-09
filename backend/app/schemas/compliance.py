from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import ComplianceStatus, DeclarationType, ReasonCode, RuleSeverity, RuleType


class RuleCondition(BaseModel):
    """Conditional prerequisite or assertion inside a compliance rule."""
    field: Optional[str] = None
    operator: str = Field("eq", description="Comparison operator: eq, neq, in, regex, gte, lte, exists")
    value: Optional[Any] = None


class RuleDefinition(BaseModel):
    """Declarative JSON structure representing compliance logic for the rule engine."""
    type: RuleType = Field(RuleType.PRESENCE, description="Rule evaluation type")
    target: DeclarationType = Field(..., description="Target declaration type being evaluated")
    conditions: List[RuleCondition] = Field(default_factory=list, description="Conditions for rule applicability or validation")
    on_missing: ComplianceStatus = Field(ComplianceStatus.FAIL, description="Status when target declaration is missing")
    on_low_confidence: ComplianceStatus = Field(ComplianceStatus.REVIEW, description="Status when extraction confidence is below threshold")
    min_confidence: float = Field(0.70, ge=0.0, le=1.0, description="Minimum confidence required for automatic decision")
    expected_format: Optional[str] = Field(None, description="Expected regex or format specifier")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom rule parameters")


class ComplianceRuleBase(BaseModel):
    rule_code: str = Field(..., max_length=64, description="Unique alphanumeric identifier for rule e.g. 'RULE_LMR_2011_06_MRP'")
    name: str = Field(..., max_length=255, description="Human-readable rule name")
    description: Optional[str] = Field(None, description="Detailed explanation of legal requirement")
    declaration_type: Optional[DeclarationType] = Field(None, description="Target declaration from taxonomy")
    rule_version: str = Field("1.0", max_length=32, description="Semantic or year-based version string")
    severity: RuleSeverity = Field(RuleSeverity.HIGH, description="Violation severity level")
    is_active: bool = Field(True, description="Whether rule is currently active")
    rule_definition: Dict[str, Any] = Field(..., description="JSON definition executed by deterministic rule engine")
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


class ComplianceRuleCreate(ComplianceRuleBase):
    pass


class ComplianceRuleResponse(ComplianceRuleBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceFindingBase(BaseModel):
    rule_code: str
    rule_version: str
    status: ComplianceStatus
    reason_code: ReasonCode
    message: str
    detected_value: Optional[Any] = None
    expected_requirement: Optional[Any] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    evidence_reference: Optional[Dict[str, Any]] = None


class ComplianceFindingCreate(ComplianceFindingBase):
    scan_session_id: str
    rule_id: Optional[str] = None


class ComplianceFindingResponse(ComplianceFindingBase):
    id: str
    scan_session_id: str
    rule_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceResult(BaseModel):
    """Aggregate compliance evaluation result for a scan session."""
    scan_session_id: str
    rule_set_version: str
    overall_status: ComplianceStatus = Field(..., description="Aggregated status: PASS, FAIL, or REVIEW")
    total_rules_evaluated: int
    passed_count: int
    failed_count: int
    review_count: int
    not_applicable_count: int
    findings: List[ComplianceFindingResponse]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
