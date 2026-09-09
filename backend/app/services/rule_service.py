from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.core.constants import (
    DEFAULT_CONFIDENCE_THRESHOLD_PASS,
    DEFAULT_CONFIDENCE_THRESHOLD_REVIEW,
    DEFAULT_RULE_SET_VERSION,
)
from app.core.enums import ComplianceStatus, DeclarationType, ReasonCode, RuleSeverity, RuleType
from app.schemas.compliance import (
    ComplianceFindingBase,
    ComplianceFindingResponse,
    ComplianceResult,
    RuleDefinition,
)
from app.schemas.declaration import DeclarationBase


class RuleServiceInterface(ABC):
    """Abstract interface for the deterministic Legal Metrology compliance rule engine."""

    @abstractmethod
    def evaluate_compliance(
        self,
        scan_session_id: str,
        declarations: List[DeclarationBase],
        product_metadata: Optional[Dict[str, Any]] = None,
        rule_set_version: str = DEFAULT_RULE_SET_VERSION,
    ) -> ComplianceResult:
        """Evaluate compliance against active, versioned rules deterministically."""
        pass


class DeterministicRuleService(RuleServiceInterface):
    """
    Deterministic rule engine implementing versioned checks without black-box AI logic.
    Decisions are purely rule-based, auditable, and support human review thresholds.
    """

    def evaluate_compliance(
        self,
        scan_session_id: str,
        declarations: List[DeclarationBase],
        product_metadata: Optional[Dict[str, Any]] = None,
        rule_set_version: str = DEFAULT_RULE_SET_VERSION,
    ) -> ComplianceResult:
        findings: List[ComplianceFindingResponse] = []
        product_metadata = product_metadata or {}

        # Index declarations by type for fast lookup
        decl_by_type: Dict[DeclarationType, List[DeclarationBase]] = {}
        for decl in declarations:
            decl_by_type.setdefault(decl.declaration_type, []).append(decl)

        # Baseline rule definitions (Mock representation of Legal Metrology Rule checks)
        sample_rules = [
            {
                "rule_code": "LMR_2011_R06_MRP",
                "name": "Mandatory Maximum Retail Price Declaration",
                "target": DeclarationType.MRP,
                "type": RuleType.PRESENCE,
                "min_confidence": 0.80,
                "on_missing": ComplianceStatus.FAIL,
                "on_low_confidence": ComplianceStatus.REVIEW,
                "reason_pass": ReasonCode.MRP_PRESENT,
                "reason_fail": ReasonCode.MRP_MISSING,
                "reason_review": ReasonCode.MRP_LOW_CONFIDENCE,
                "expected": "MRP Rs. XX.XX inclusive of all taxes",
            },
            {
                "rule_code": "LMR_2011_R06_NET_QTY",
                "name": "Mandatory Net Quantity Declaration",
                "target": DeclarationType.NET_QUANTITY,
                "type": RuleType.PRESENCE,
                "min_confidence": 0.80,
                "on_missing": ComplianceStatus.FAIL,
                "on_low_confidence": ComplianceStatus.REVIEW,
                "reason_pass": ReasonCode.NET_QUANTITY_PRESENT,
                "reason_fail": ReasonCode.NET_QUANTITY_MISSING,
                "reason_review": ReasonCode.NET_QUANTITY_LOW_CONFIDENCE,
                "expected": "Net weight or volume in standard metric units (g, kg, ml, l)",
            },
            {
                "rule_code": "LMR_2011_R06_MANUFACTURER",
                "name": "Manufacturer Name and Address Declaration",
                "target": DeclarationType.MANUFACTURER,
                "type": RuleType.PRESENCE,
                "min_confidence": 0.75,
                "on_missing": ComplianceStatus.FAIL,
                "on_low_confidence": ComplianceStatus.REVIEW,
                "reason_pass": ReasonCode.MANUFACTURER_PRESENT,
                "reason_fail": ReasonCode.MANUFACTURER_MISSING,
                "reason_review": ReasonCode.MANUAL_REVIEW_TRIGGERED,
                "expected": "Name and complete address of the manufacturer/packer",
            },
            {
                "rule_code": "LMR_2011_R06_CONSUMER_CARE",
                "name": "Consumer Care Contact Details",
                "target": DeclarationType.CONSUMER_CARE_PHONE,
                "type": RuleType.PRESENCE,
                "min_confidence": 0.75,
                "on_missing": ComplianceStatus.FAIL,
                "on_low_confidence": ComplianceStatus.REVIEW,
                "reason_pass": ReasonCode.CONSUMER_CARE_COMPLETE,
                "reason_fail": ReasonCode.CONSUMER_CARE_INCOMPLETE,
                "reason_review": ReasonCode.MANUAL_REVIEW_TRIGGERED,
                "expected": "Valid consumer care phone number or email address",
            },
        ]

        import uuid
        from datetime import datetime, timezone

        for rule in sample_rules:
            target = rule["target"]
            matched_decls = decl_by_type.get(target, [])

            if not matched_decls:
                findings.append(
                    ComplianceFindingResponse(
                        id=str(uuid.uuid4()),
                        scan_session_id=scan_session_id,
                        rule_code=rule["rule_code"],
                        rule_version=rule_set_version,
                        status=rule["on_missing"],
                        reason_code=rule["reason_fail"],
                        message=f"Missing required declaration: {rule['name']}",
                        detected_value=None,
                        expected_requirement={"description": rule["expected"]},
                        confidence=1.0,
                        evidence_reference=None,
                        created_at=datetime.now(timezone.utc),
                    )
                )
            else:
                top_decl = max(matched_decls, key=lambda d: d.confidence)
                if top_decl.confidence < rule["min_confidence"]:
                    findings.append(
                        ComplianceFindingResponse(
                            id=str(uuid.uuid4()),
                            scan_session_id=scan_session_id,
                            rule_code=rule["rule_code"],
                            rule_version=rule_set_version,
                            status=rule["on_low_confidence"],
                            reason_code=rule["reason_review"],
                            message=f"Declaration extracted with low confidence ({top_decl.confidence:.2f}). Human review required.",
                            detected_value={"raw_text": top_decl.raw_text, "normalized": top_decl.normalized_value},
                            expected_requirement={"description": rule["expected"]},
                            confidence=top_decl.confidence,
                            evidence_reference={"source_ocr_block_id": top_decl.source_ocr_block_id},
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                else:
                    findings.append(
                        ComplianceFindingResponse(
                            id=str(uuid.uuid4()),
                            scan_session_id=scan_session_id,
                            rule_code=rule["rule_code"],
                            rule_version=rule_set_version,
                            status=ComplianceStatus.PASS,
                            reason_code=rule["reason_pass"],
                            message=f"Valid declaration detected: {top_decl.raw_text}",
                            detected_value={"raw_text": top_decl.raw_text, "normalized": top_decl.normalized_value},
                            expected_requirement={"description": rule["expected"]},
                            confidence=top_decl.confidence,
                            evidence_reference={"source_ocr_block_id": top_decl.source_ocr_block_id},
                            created_at=datetime.now(timezone.utc),
                        )
                    )

        # Compute aggregate status
        passed = sum(1 for f in findings if f.status == ComplianceStatus.PASS)
        failed = sum(1 for f in findings if f.status == ComplianceStatus.FAIL)
        review = sum(1 for f in findings if f.status == ComplianceStatus.REVIEW)
        na = sum(1 for f in findings if f.status == ComplianceStatus.NOT_APPLICABLE)

        overall = ComplianceStatus.PASS
        if failed > 0:
            overall = ComplianceStatus.FAIL
        elif review > 0:
            overall = ComplianceStatus.REVIEW

        return ComplianceResult(
            scan_session_id=scan_session_id,
            rule_set_version=rule_set_version,
            overall_status=overall,
            total_rules_evaluated=len(findings),
            passed_count=passed,
            failed_count=failed,
            review_count=review,
            not_applicable_count=na,
            findings=findings,
        )


def get_rule_service() -> RuleServiceInterface:
    """Dependency provider for compliance rule service."""
    return DeterministicRuleService()
