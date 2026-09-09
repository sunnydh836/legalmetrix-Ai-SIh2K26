import json
import os
import pytest
from app.core.enums import ComplianceStatus, DeclarationType, ImageQualityStatus, ReasonCode
from app.schemas.common import BoundingBox, ImageQualityResult
from app.schemas.compliance import ComplianceFindingBase, ComplianceResult, RuleDefinition
from app.schemas.declaration import DeclarationBase
from app.schemas.ocr import OCRBlockItem, OCRResult
from app.services.rule_service import DeterministicRuleService


def test_ocr_result_contract():
    """Verify OCRResult serialization/deserialization matches the specification contract."""
    ocr_data = {
        "scan_image_id": "img-12345",
        "engine": "paddleocr",
        "engine_version": "2.7.0",
        "blocks": [
            {
                "text": "MRP Rs. 120",
                "confidence": 0.96,
                "bbox": {"x1": 100, "y1": 250, "x2": 330, "y2": 300},
            }
        ],
    }
    result = OCRResult.model_validate(ocr_data)
    assert result.scan_image_id == "img-12345"
    assert result.engine == "paddleocr"
    assert len(result.blocks) == 1
    assert result.blocks[0].text == "MRP Rs. 120"
    assert result.blocks[0].confidence == 0.96
    assert result.blocks[0].bbox.x1 == 100


def test_declaration_contract():
    """Verify Declaration contract."""
    decl_data = {
        "declaration_type": "MRP",
        "raw_text": "MRP ₹120 incl. of all taxes",
        "normalized_value": {"amount": 120.0, "currency": "INR"},
        "confidence": 0.93,
        "source_blocks": ["block-001"],
    }
    decl = DeclarationBase.model_validate(decl_data)
    assert decl.declaration_type == DeclarationType.MRP
    assert decl.confidence == 0.93
    assert decl.normalized_value["amount"] == 120.0


def test_compliance_finding_contract():
    """Verify ComplianceFinding contract."""
    finding_data = {
        "rule_code": "MRP_REQUIRED",
        "rule_version": "1.0",
        "status": "PASS",
        "reason_code": "MRP_PRESENT",
        "message": "MRP declaration detected.",
        "detected_value": "₹120",
        "expected_requirement": "MRP declaration present",
        "confidence": 0.93,
    }
    finding = ComplianceFindingBase.model_validate(finding_data)
    assert finding.status == ComplianceStatus.PASS
    assert finding.reason_code == ReasonCode.MRP_PRESENT


def test_image_quality_contract():
    """Verify ImageQualityResult schema validation."""
    quality_data = {
        "scan_image_id": "img-001",
        "blur_score": 150.5,
        "glare_score": 0.02,
        "resolution": {"width": 1920, "height": 1080},
        "orientation": 0,
        "quality_status": "ACCEPTED",
        "warnings": [],
    }
    res = ImageQualityResult.model_validate(quality_data)
    assert res.quality_status == ImageQualityStatus.ACCEPTED
    assert res.blur_score == 150.5


def test_rule_service_deterministic_behavior():
    """Verify Rule Engine produces deterministic findings with human-review trigger on low confidence."""
    rule_service = DeterministicRuleService()
    
    # 1. Missing declarations -> deterministic FAIL
    res_empty = rule_service.evaluate_compliance(
        scan_session_id="session-test-01",
        declarations=[],
    )
    assert res_empty.overall_status == ComplianceStatus.FAIL
    assert res_empty.failed_count > 0

    # 2. Low confidence declaration -> deterministic REVIEW
    low_conf_decl = DeclarationBase(
        declaration_type=DeclarationType.MRP,
        raw_text="MRP ??0",
        confidence=0.55,  # below 0.80 threshold
    )
    res_low_conf = rule_service.evaluate_compliance(
        scan_session_id="session-test-02",
        declarations=[low_conf_decl],
    )
    # Finding for MRP should be REVIEW
    mrp_finding = next(f for f in res_low_conf.findings if f.rule_code == "LMR_2011_R06_MRP")
    assert mrp_finding.status == ComplianceStatus.REVIEW


def test_fixture_cases_loading():
    """Verify 20 test case fixtures are valid JSON and load correctly."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "product_cases.json")
    assert os.path.exists(fixture_path)
    with open(fixture_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    assert len(cases) == 20
    for case in cases:
        assert "id" in case
        assert "description" in case
        assert "image_condition" in case
        assert "expected_pipeline_behavior" in case
