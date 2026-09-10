import pytest
from app.core.enums import DeclarationType, ResolutionStatus, ConfidenceLevel
from app.services.declaration_extraction.extractor import ExtractedCandidate
from app.services.declaration_extraction.resolver import resolve_declaration


def test_high_ocr_confidence_wrong_semantic_candidate():
    # Case: High OCR confidence but semantics are not strong, should be NEEDS_REVIEW
    candidate = ExtractedCandidate(
        declaration_type=DeclarationType.COMMODITY_NAME,
        raw_text="NOT A COMMODITY",
        raw_value="NOT A COMMODITY",
        normalized_value={"name": "NOT A COMMODITY"},
        confidence=0.99,  # High OCR but bad semantics
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"semantic_confidence": 0.4, "ocr_confidence": 0.99},
        scan_image_id="img1",
        image_type="FRONT",
        blocks=[]
    )
    result = resolve_declaration(DeclarationType.COMMODITY_NAME, [candidate])
    # With low semantic confidence, should not AUTO_RESOLVE
    assert result.get("resolution_status") == ResolutionStatus.NEEDS_REVIEW
    assert result.get("canonical_value") == {"name": "NOT A COMMODITY"}


def test_partial_complete_compatible_address():
    # Case: Duplicate/overlapping address candidates. Should combine or pick highest confidence without conflict.
    cand1 = ExtractedCandidate(
        declaration_type=DeclarationType.MANUFACTURER_ADDRESS,
        raw_text="Pune",
        raw_value="Pune",
        normalized_value={"address_line": "Pune", "city": "Pune"},
        confidence=0.6,
        confidence_level=ConfidenceLevel.MEDIUM,
        confidence_breakdown={"completeness_confidence": 0.3},
        scan_image_id="img1",
        image_type="FRONT",
        blocks=[]
    )
    cand2 = ExtractedCandidate(
        declaration_type=DeclarationType.MANUFACTURER_ADDRESS,
        raw_text="Flat 1, Pune, 411001",
        raw_value="Flat 1, Pune, 411001",
        normalized_value={"address_line": "Flat 1, Pune", "city": "Pune", "pin": "411001"},
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"ocr_confidence": 0.95, "association_confidence": 0.85, "completeness_confidence": 0.9, "semantic_confidence": 0.9},
        scan_image_id="img2",
        image_type="BACK",
        blocks=[]
    )
    result = resolve_declaration(DeclarationType.MANUFACTURER_ADDRESS, [cand1, cand2])
    # They are compatible, so one is picked without CONFLICT
    assert result.get("resolution_status") == ResolutionStatus.AUTO_RESOLVED
    assert result.get("canonical_value")["pin"] == "411001"


def test_true_address_conflict():
    # Case: Two completely different addresses that don't match
    cand1 = ExtractedCandidate(
        declaration_type=DeclarationType.MANUFACTURER_ADDRESS,
        raw_text="Mumbai, 400001",
        raw_value="Mumbai, 400001",
        normalized_value={"address_line": "Mumbai", "city": "Mumbai", "pin": "400001"},
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"completeness_confidence": 0.9, "semantic_confidence": 0.9},
        scan_image_id="img1",
        image_type="FRONT",
        blocks=[]
    )
    cand2 = ExtractedCandidate(
        declaration_type=DeclarationType.MANUFACTURER_ADDRESS,
        raw_text="Delhi, 110001",
        raw_value="Delhi, 110001",
        normalized_value={"address_line": "Delhi", "city": "Delhi", "pin": "110001"},
        confidence=0.95,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"completeness_confidence": 0.95, "semantic_confidence": 0.95},
        scan_image_id="img2",
        image_type="BACK",
        blocks=[]
    )
    result = resolve_declaration(DeclarationType.MANUFACTURER_ADDRESS, [cand1, cand2])
    assert result.get("resolution_status") == ResolutionStatus.CONFLICT


def test_same_value_on_two_panels_dedupe():
    # Case: Two panels have the exact same normalized value. Should dedupe and not cause conflict.
    cand1 = ExtractedCandidate(
        declaration_type=DeclarationType.MRP,
        raw_text="Rs. 100",
        raw_value="100",
        normalized_value={"amount": 100, "currency": "INR"},
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"ocr_confidence": 0.9, "association_confidence": 0.9, "completeness_confidence": 0.9, "semantic_confidence": 0.9},
        scan_image_id="img1",
        image_type="FRONT",
        blocks=[]
    )
    cand2 = ExtractedCandidate(
        declaration_type=DeclarationType.MRP,
        raw_text="100.00 Rs",
        raw_value="100.00",
        normalized_value={"amount": 100, "currency": "INR"},
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"ocr_confidence": 0.9, "association_confidence": 0.9, "completeness_confidence": 0.9, "semantic_confidence": 0.9},
        scan_image_id="img2",
        image_type="BACK",
        blocks=[]
    )
    result = resolve_declaration(DeclarationType.MRP, [cand1, cand2])
    assert result.get("resolution_status") == ResolutionStatus.AUTO_RESOLVED
    assert result.get("canonical_value")["amount"] == 100


def test_high_confidence_semantic_failure():
    # Case: A candidate with 0 semantic confidence but high overall because of OCR
    cand1 = ExtractedCandidate(
        declaration_type=DeclarationType.NET_QUANTITY,
        raw_text="Weight 500",
        raw_value="500",
        normalized_value={"value": 500},
        confidence=0.95,
        confidence_level=ConfidenceLevel.HIGH,
        confidence_breakdown={"semantic_confidence": 0.2, "ocr_confidence": 0.99},
        scan_image_id="img1",
        image_type="FRONT",
        blocks=[]
    )
    result = resolve_declaration(DeclarationType.NET_QUANTITY, [cand1])
    # The resolver explicitly requires high semantic confidence for AUTO_RESOLVED
    assert result.get("resolution_status") == ResolutionStatus.NEEDS_REVIEW
