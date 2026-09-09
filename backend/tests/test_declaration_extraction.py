"""Tests for Day 5 Declaration Extraction, Normalization, Evidence Linkage, and Review Workflow."""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.core.enums import ConfidenceLevel, DeclarationType, ReviewStatus, UserRole
from app.models.declaration import Declaration
from app.models.ocr_block import OCRBlock
from app.models.scan_image import ScanImage
from app.models.scan_session import ScanSession
from app.models.user import User
from app.services.declaration_extraction import (
    DeclarationExtractor,
    evaluate_declaration_benchmark,
    normalize_country,
    normalize_date,
    normalize_email,
    normalize_mrp,
    normalize_net_quantity,
    normalize_phone,
)


# -------------------------------------------------------------------
# Unit Tests: Normalizers & Regex Patterns
# -------------------------------------------------------------------

def test_mrp_normalization():
    res1 = normalize_mrp("10")
    assert res1["amount"] == 10.0
    assert res1["currency"] == "INR"

    res2 = normalize_mrp("99.00", has_taxes_incl=True)
    assert res2["amount"] == 99.0
    assert res2["taxes_inclusive"] is True

    res3 = normalize_mrp("120,50")
    assert res3["amount"] == 120.50


def test_net_quantity_normalization():
    res1 = normalize_net_quantity("79", "g")
    assert res1["value"] == 79
    assert res1["unit"] == "g"

    res2 = normalize_net_quantity("500", "gm")
    assert res2["value"] == 500
    assert res2["unit"] == "g"
    assert res2["canonical_value"] == 500

    res3 = normalize_net_quantity("1", "kg")
    assert res3["value"] == 1
    assert res3["unit"] == "kg"
    assert res3["canonical_value"] == 1000

    res4 = normalize_net_quantity("750", "mL")
    assert res4["value"] == 750
    assert res4["unit"] == "ml"

    res5 = normalize_net_quantity("2", "litres")
    assert res5["value"] == 2
    assert res5["unit"] == "L"
    assert res5["canonical_value"] == 2000


def test_date_normalization():
    # MM/YYYY
    res1 = normalize_date("08/2026", "DATE_OF_MANUFACTURE")
    assert res1["date"] == "2026-08"
    assert res1["month"] == 8
    assert res1["year"] == 2026

    # MMM YYYY
    res2 = normalize_date("AUG 2026", "DATE_OF_PACKING")
    assert res2["date"] == "2026-08"
    assert res2["month"] == 8

    # DD/MM/YYYY
    res3 = normalize_date("15/08/2026", "EXPIRY_DATE")
    assert res3["date"] == "2026-08-15"
    assert res3["day"] == 15

    # Relative expression
    res4 = normalize_date("Best Before 9 Months From Manufacture", "BEST_BEFORE")
    assert res4["is_relative"] is True
    assert res4["relative_duration"] == 9
    assert res4["relative_unit"] == "MONTHS"


def test_country_normalization():
    res1 = normalize_country("India")
    assert res1["country"] == "India"
    assert res1["is_recognized"] is True

    res2 = normalize_country("MADE IN BANGLADESH")
    assert res2["country"] == "Bangladesh"
    assert res2["is_recognized"] is True


def test_consumer_care_normalization():
    # Phone
    res_phone = normalize_phone("1800-123-456")
    assert "1800" in res_phone["digits"]

    # Email with OCR spaces
    res_email = normalize_email("care @ example . com")
    assert res_email["email"] == "care@example.com"


# -------------------------------------------------------------------
# Unit Tests: Extractor & Multi-block Spatial Grouping
# -------------------------------------------------------------------

class MockOCRBlock:
    def __init__(self, id, text, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2):
        self.id = id
        self.text = text
        self.confidence = confidence
        self.bbox_x1 = bbox_x1
        self.bbox_y1 = bbox_y1
        self.bbox_x2 = bbox_x2
        self.bbox_y2 = bbox_y2


def test_multi_block_net_quantity_extraction():
    extractor = DeclarationExtractor()

    # Multi-block: "Net", "Qty", "79", "g" on same line
    b1 = MockOCRBlock("b1", "Net", 0.95, 10, 100, 40, 120)
    b2 = MockOCRBlock("b2", "Qty", 0.94, 45, 100, 75, 120)
    b3 = MockOCRBlock("b3", "79", 0.98, 80, 100, 100, 120)
    b4 = MockOCRBlock("b4", "g", 0.92, 105, 100, 115, 120)

    candidates = extractor.extract_from_image_blocks(
        scan_image_id="img_1",
        image_type="BACK",
        blocks=[b1, b2, b3, b4],
    )

    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is not None
    assert net_qty.normalized_value["value"] == 79
    assert net_qty.normalized_value["unit"] == "g"
    # Verify all 4 blocks are referenced in evidence
    assert len(net_qty.source_block_ids) == 4
    assert set(net_qty.source_block_ids) == {"b1", "b2", "b3", "b4"}
    # Union bbox encompasses all 4
    bbox = net_qty.union_bounding_box
    assert bbox["bbox_x1"] == 10
    assert bbox["bbox_x2"] == 115


def test_multi_image_conflict_detection():
    extractor = DeclarationExtractor()

    # Image 1 (Front): MRP ₹10
    b_front = MockOCRBlock("bf", "MRP ₹10", 0.95, 20, 20, 100, 40)
    # Image 2 (Back): MRP ₹20
    b_back = MockOCRBlock("bb", "MRP ₹20", 0.94, 20, 20, 100, 40)

    images_data = [
        {"image_id": "img_front", "image_type": "FRONT", "blocks": [b_front]},
        {"image_id": "img_back", "image_type": "BACK", "blocks": [b_back]},
    ]

    consolidated = extractor.extract_and_consolidate_scan(images_data)
    mrp_candidates = [c for c in consolidated if c.declaration_type == DeclarationType.MRP]

    assert len(mrp_candidates) == 2
    # Both candidates preserved and flagged with conflict
    assert all(c.has_conflict for c in mrp_candidates)
    assert mrp_candidates[0].conflict_details is not None
    assert mrp_candidates[0].conflict_details["conflict_type"] == "MULTIPLE_DISCREPANT_VALUES_ACROSS_PANELS"


def test_benchmark_evaluator_under_threshold():
    res = evaluate_declaration_benchmark(dataset_records=[], min_package_threshold=50)
    assert res["status"] == "benchmark dataset pending"
    assert res["labeled_packages_count"] == 0


def test_benchmark_evaluator_sufficient_dataset():
    # 50 mock records
    records = []
    for i in range(50):
        records.append({
            "scan_id": f"scan_{i}",
            "expected_declarations": [{"type": "MRP", "normalized_expected": {"amount": 10.0}}],
            "predicted_declarations": [{"type": "MRP", "normalized_value": {"amount": 10.0}}],
        })
    res = evaluate_declaration_benchmark(dataset_records=records, min_package_threshold=50)
    assert res["status"] == "COMPLETED"
    assert res["overall"]["micro_f1"] == 1.0


# -------------------------------------------------------------------
# Integration & API Tests with TestClient
# -------------------------------------------------------------------

@pytest.fixture
def scan_with_ocr_blocks(client: TestClient, db_session, inspector_token):
    """Fixture providing an existing scan session with populated OCR blocks."""
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    # Create scan
    resp = client.post("/api/v1/scans", json={"product": {"name": "Demo Oat Milk"}}, headers=inspector_headers)
    scan_id = resp.json()["id"]

    # Insert scan image & OCR blocks directly in DB
    img = ScanImage(
        id=f"img_{scan_id[:8]}",
        scan_session_id=scan_id,
        image_type="BACK",
        file_path="storage/scans/test.jpg",
        mime_type="image/jpeg",
        processing_status="COMPLETED",
    )
    db_session.add(img)
    db_session.flush()

    blocks = [
        OCRBlock(
            id=f"blk_mrp_{scan_id[:6]}",
            scan_image_id=img.id,
            text="MRP Rs. 149.00 (Incl. of all taxes)",
            confidence=0.96,
            bbox_x1=50, bbox_y1=100, bbox_x2=250, bbox_y2=130,
            block_order=0,
        ),
        OCRBlock(
            id=f"blk_qty_{scan_id[:6]}",
            scan_image_id=img.id,
            text="Net Quantity: 500 g",
            confidence=0.94,
            bbox_x1=50, bbox_y1=140, bbox_x2=200, bbox_y2=170,
            block_order=1,
        ),
        OCRBlock(
            id=f"blk_mfd_{scan_id[:6]}",
            scan_image_id=img.id,
            text="MFD: 08/2026",
            confidence=0.91,
            bbox_x1=50, bbox_y1=180, bbox_x2=160, bbox_y2=210,
            block_order=2,
        ),
        OCRBlock(
            id=f"blk_care_{scan_id[:6]}",
            scan_image_id=img.id,
            text="Consumer Care: care@legalmetrix.ai",
            confidence=0.93,
            bbox_x1=50, bbox_y1=220, bbox_x2=300, bbox_y2=250,
            block_order=3,
        ),
        OCRBlock(
            id=f"blk_org_{scan_id[:6]}",
            scan_image_id=img.id,
            text="Manufactured by Heritage Foods Pvt Ltd, Pune 411001",
            confidence=0.89,
            bbox_x1=50, bbox_y1=260, bbox_x2=400, bbox_y2=290,
            block_order=4,
        ),
    ]
    for b in blocks:
        db_session.add(b)
    db_session.commit()

    return scan_id


def test_extract_declarations_api_success(client: TestClient, scan_with_ocr_blocks: str, inspector_token):
    scan_id = scan_with_ocr_blocks
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    resp = client.post(f"/api/v1/scans/{scan_id}/extract-declarations", headers=inspector_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scan_id"] == scan_id
    assert data["total_declarations"] >= 4
    assert data["extractor_version"] == "1.0.0"

    types = [d["declaration_type"] for d in data["declarations"]]
    assert "MRP" in types
    assert "NET_QUANTITY" in types
    assert "DATE_OF_MANUFACTURE" in types
    assert "CONSUMER_CARE_EMAIL" in types

    # Verify MRP structured data
    mrp_decl = next(d for d in data["declarations"] if d["declaration_type"] == "MRP")
    assert mrp_decl["normalized_value"]["amount"] == 149.0
    assert mrp_decl["confidence_level"] == "HIGH"
    assert len(mrp_decl["source_blocks"]) >= 1


def test_extraction_idempotency(client: TestClient, scan_with_ocr_blocks: str, inspector_token):
    scan_id = scan_with_ocr_blocks
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    # Run 1st time
    resp1 = client.post(f"/api/v1/scans/{scan_id}/extract-declarations", headers=inspector_headers)
    assert resp1.status_code == 200
    count1 = resp1.json()["total_declarations"]

    # Run 2nd time
    resp2 = client.post(f"/api/v1/scans/{scan_id}/extract-declarations", headers=inspector_headers)
    assert resp2.status_code == 200
    count2 = resp2.json()["total_declarations"]

    # Idempotent: Count of declarations remains unchanged
    assert count1 == count2


def test_reviewer_workflow_and_machine_preservation(client: TestClient, scan_with_ocr_blocks: str, inspector_token, reviewer_token):
    scan_id = scan_with_ocr_blocks
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}

    # 1. Extract
    resp = client.post(f"/api/v1/scans/{scan_id}/extract-declarations", headers=inspector_headers)
    declarations = resp.json()["declarations"]
    mrp_decl = next(d for d in declarations if d["declaration_type"] == "MRP")
    decl_id = mrp_decl["id"]

    # 2. Reviewer corrects the value
    patch_resp = client.patch(
        f"/api/v1/declarations/{decl_id}",
        json={
            "review_status": "CORRECTED",
            "reviewed_value": {"amount": 150.0, "currency": "INR", "corrected_reason": "Typo"},
            "review_notes": "Verified against physical invoice",
        },
        headers=reviewer_headers,
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["review_status"] == "CORRECTED"
    assert updated["reviewed"] is True
    assert updated["reviewed_value"]["amount"] == 150.0
    # Machine extracted value remains strictly preserved as 149.0!
    assert updated["machine_extracted_value"]["amount"] == 149.0

    # 3. Re-extract: verify human correction is not wiped out
    re_extract_resp = client.post(f"/api/v1/scans/{scan_id}/extract-declarations", headers=inspector_headers)
    assert re_extract_resp.status_code == 200
    refreshed_mrp = next(d for d in re_extract_resp.json()["declarations"] if d["declaration_type"] == "MRP")
    assert refreshed_mrp["review_status"] == "CORRECTED"
    assert refreshed_mrp["reviewed_value"]["amount"] == 150.0


def test_unauthorized_user_cannot_review(client: TestClient, scan_with_ocr_blocks: str, inspector_token):
    scan_id = scan_with_ocr_blocks
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    resp = client.post(f"/api/v1/scans/{scan_id}/extract-declarations", headers=inspector_headers)
    decl_id = resp.json()["declarations"][0]["id"]

    # Attempt to review without auth token
    unauth_resp = client.patch(
        f"/api/v1/declarations/{decl_id}",
        json={"review_status": "CONFIRMED"},
    )
    assert unauth_resp.status_code == 401


# -------------------------------------------------------------------
# Regression Tests: Parle-G Edge Cases & Image Serving
# -------------------------------------------------------------------

def test_ocr_noisy_net_weight_and_invalid_date():
    extractor = DeclarationExtractor()

    # Raw OCR text containing "NETWEIGHT: 475 MRPE PKD1 BATCH:"
    b1 = MockOCRBlock("b1", "NETWEIGHT: 475 MRPE PKD1 BATCH:", 0.95, 10, 100, 300, 130)

    candidates = extractor.extract_from_image_blocks(
        scan_image_id="img_parle_g",
        image_type="BACK",
        blocks=[b1],
    )

    # 1. Net Quantity should be extracted with value 475, unit None, confidence MEDIUM/LOW
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is not None
    assert net_qty.normalized_value["value"] == 475
    assert net_qty.normalized_value["unit"] is None
    assert net_qty.confidence_level != ConfidenceLevel.HIGH

    # 2. Date of Packing should NOT be extracted because "1 BATCH" cannot be parsed into a date
    pkd_cand = next((c for c in candidates if c.declaration_type == DeclarationType.DATE_OF_PACKING), None)
    assert pkd_cand is None

    # 3. MRP should NOT be extracted without a price amount
    mrp_cand = next((c for c in candidates if c.declaration_type == DeclarationType.MRP), None)
    assert mrp_cand is None


def test_mrpe_with_price():
    extractor = DeclarationExtractor()
    b1 = MockOCRBlock("b1", "MRPE 20.00 (INCL OF ALL TAXES)", 0.95, 10, 100, 200, 130)

    candidates = extractor.extract_from_image_blocks(
        scan_image_id="img_test",
        image_type="BACK",
        blocks=[b1],
    )

    mrp_cand = next((c for c in candidates if c.declaration_type == DeclarationType.MRP), None)
    assert mrp_cand is not None
    assert mrp_cand.normalized_value["amount"] == 20.0
    assert mrp_cand.normalized_value["taxes_inclusive"] is True


def test_image_serving_endpoints(client: TestClient, inspector_token):
    # Setup scan and upload image via API
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    resp = client.post("/api/v1/scans", json={"product": {"name": "Image Serving Test"}}, headers=inspector_headers)
    scan_id = resp.json()["id"]

    import io
    from PIL import Image
    buf = io.BytesIO()
    img_obj = Image.new("RGB", (600, 800), color="blue")
    img_obj.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    upload_resp = client.post(
        f"/api/v1/scans/{scan_id}/images?image_type=FRONT",
        files=[("files", ("panel.jpg", img_bytes, "image/jpeg"))],
        headers=inspector_headers,
    )
    assert upload_resp.status_code == 200
    uploaded_images = upload_resp.json()
    assert len(uploaded_images) == 1
    image_id = uploaded_images[0]["id"]

    # Access via /content without auth header (simulate browser <img>)
    content_resp = client.get(f"/api/v1/scans/{scan_id}/images/{image_id}/content")
    assert content_resp.status_code == 200
    assert content_resp.headers["content-type"] == "image/jpeg"
    assert "public, max-age=86400" in content_resp.headers["cache-control"]
    assert len(content_resp.content) > 0

    # Access via /file with token query param
    file_resp = client.get(f"/api/v1/scans/{scan_id}/images/{image_id}/file?token={inspector_token}")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "image/jpeg"


# -------------------------------------------------------------------
# Day 4 -> Day 5 Hardening: Britannia Packaged Food Regression Tests
# -------------------------------------------------------------------

def test_britannia_net_weight_827g():
    """Case 1: 'NET WEIGHT 827 g' => NET_QUANTITY 827g"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "NET WEIGHT 827 g", 0.95, 10, 100, 200, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is not None
    assert net_qty.normalized_value["value"] == 827
    assert net_qty.normalized_value["unit"] == "g"
    assert net_qty.normalized_value["canonical_value"] == 827


def test_britannia_multipack_net_quantity_expression():
    """Case 2: '10 N x 82.7 g = 827 g' => NET_QUANTITY canonical value 827g (not 7g)"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "10 N x 82.7 g = 827 g", 0.96, 10, 100, 250, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is not None
    assert net_qty.normalized_value["value"] == 827
    assert net_qty.normalized_value["canonical_value"] == 827
    assert net_qty.normalized_value["unit"] == "g"
    assert net_qty.normalized_value["is_multipack"] is True
    assert net_qty.normalized_value["multipack"]["units"] == 10
    assert net_qty.normalized_value["multipack"]["unit_value"] == 82.7


def test_britannia_serving_size_rejected_as_net_qty():
    """Case 3: 'Serving Size Approx. 15 g' => NOT NET_QUANTITY"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "Serving Size: Approx. 15g (Approx. 2 Biscuits)", 0.95, 10, 100, 300, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is None


def test_britannia_total_sugars_rejected_as_mrp_and_net_qty():
    """Case 4: 'of which Total Sugars 20.5g' => NOT NET_QUANTITY and NOT MRP"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "of which Total Sugars 20.5g", 0.97, 10, 100, 250, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    mrp = next((c for c in candidates if c.declaration_type == DeclarationType.MRP), None)
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert mrp is None
    assert net_qty is None


def test_britannia_added_sugars_rejected_as_mrp():
    """Case 5: 'Added Sugars 20.3g' => NOT MRP"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "Added Sugars 20.3g", 0.96, 10, 100, 200, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    mrp = next((c for c in candidates if c.declaration_type == DeclarationType.MRP), None)
    assert mrp is None


def test_britannia_trans_fat_rejected_as_net_qty():
    """Case 6: 'Trans fatty acids 0g' => NOT NET_QUANTITY"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "Trans fatty acids 0g", 0.95, 10, 100, 200, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is None


def test_britannia_mrp_with_taxes():
    """Case 7: 'MRP ₹ 120 (Incl. of all taxes)' => MRP 120 INR"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "MRP ₹ 120 (Incl. of all taxes)", 0.98, 10, 100, 250, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    mrp = next((c for c in candidates if c.declaration_type == DeclarationType.MRP), None)
    assert mrp is not None
    assert mrp.normalized_value["amount"] == 120.0
    assert mrp.normalized_value["currency"] == "INR"
    assert mrp.normalized_value["taxes_inclusive"] is True


def test_britannia_consumer_care_phone():
    """Case 8: 'Consumer Care: 1-800-4254449' => CONSUMER_CARE_PHONE"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "Consumer Care: 1-800-4254449", 0.96, 10, 100, 280, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    phone = next((c for c in candidates if c.declaration_type == DeclarationType.CONSUMER_CARE_PHONE), None)
    assert phone is not None
    assert "1800" in phone.normalized_value["digits"]
    assert "4254449" in phone.normalized_value["digits"]


def test_britannia_fssai_licence_not_phone():
    """Case 9: 'Lic. No. 10015043001129' => NOT CONSUMER_CARE_PHONE"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "Lic. No. 10015043001129", 0.95, 10, 100, 250, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    phone = next((c for c in candidates if c.declaration_type == DeclarationType.CONSUMER_CARE_PHONE), None)
    assert phone is None


def test_britannia_consumer_care_email():
    """Case 10: 'E-mail: feedback@britindia.com' => CONSUMER_CARE_EMAIL"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "E-mail: feedback@britindia.com", 0.97, 10, 100, 260, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    email = next((c for c in candidates if c.declaration_type == DeclarationType.CONSUMER_CARE_EMAIL), None)
    assert email is not None
    assert email.normalized_value["email"] == "feedback@britindia.com"


def test_britannia_batch_instruction_not_batch_value():
    """Case 11: 'Batch No. printed on the pack' => no fabricated batch value"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "Batch No. printed on the pack", 0.94, 10, 100, 260, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    batch = next((c for c in candidates if c.declaration_type == DeclarationType.BATCH_OR_LOT_NUMBER), None)
    assert batch is None


def test_britannia_meaningless_punctuation_not_commodity_name():
    """Case 12: Meaningless punctuation '(' => NOT COMMODITY_NAME"""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "COMMODITY: (", 0.90, 10, 100, 100, 130)
    candidates = extractor.extract_from_image_blocks("img_brit", "BACK", [b])
    comm = next((c for c in candidates if c.declaration_type == DeclarationType.COMMODITY_NAME), None)
    assert comm is None


def test_britannia_full_panel_consolidation_and_no_spurious_conflicts():
    """Verify that a realistic multi-block Britannia panel extracts true values without spurious conflicts."""
    extractor = DeclarationExtractor()
    blocks = [
        MockOCRBlock("b1", "BRITANNIA GOOD DAY BUTTER COOKIES", 0.98, 10, 20, 300, 50),
        MockOCRBlock("b2", "GENERIC NAME: BISCUITS", 0.95, 10, 60, 200, 80),
        MockOCRBlock("b3", "NET WEIGHT 827 g", 0.96, 10, 90, 180, 110),
        MockOCRBlock("b4", "10 N x 82.7 g = 827 g", 0.94, 10, 120, 240, 140),
        MockOCRBlock("b5", "MRP Rs. 120.00 (INCL. OF ALL TAXES)", 0.97, 10, 150, 320, 170),
        MockOCRBlock("b6", "NUTRITION INFORMATION (Approx. per 100g)", 0.96, 10, 200, 350, 220),
        MockOCRBlock("b7", "Serving Size: Approx. 15g (Approx. 2 Biscuits)", 0.95, 10, 230, 350, 250),
        MockOCRBlock("b8", "Energy 492 kcal, Protein 7g", 0.94, 10, 260, 300, 280),
        MockOCRBlock("b9", "Total Sugars 20.5g, Added Sugars 20.3g", 0.95, 10, 290, 320, 310),
        MockOCRBlock("b10", "Trans fatty acids 0g", 0.94, 10, 320, 220, 340),
        MockOCRBlock("b11", "Lic. No. 10015043001129", 0.95, 10, 360, 250, 380),
        MockOCRBlock("b12", "For Feedback Contact Consumer Care: 1-800-4254449", 0.96, 10, 400, 400, 420),
        MockOCRBlock("b13", "E-mail: feedback@britindia.com", 0.97, 10, 430, 280, 450),
        MockOCRBlock("b14", "Batch No. printed on the pack", 0.93, 10, 460, 260, 480),
    ]

    images_data = [{"image_id": "img_brit_full", "image_type": "BACK", "blocks": blocks}]
    consolidated = extractor.extract_and_consolidate_scan(images_data)

    by_type = {c.declaration_type: c for c in consolidated}

    # Net Quantity is extracted as 827g
    assert DeclarationType.NET_QUANTITY in by_type
    assert by_type[DeclarationType.NET_QUANTITY].normalized_value["canonical_value"] == 827
    assert by_type[DeclarationType.NET_QUANTITY].has_conflict is False

    # MRP is extracted as 120 INR
    assert DeclarationType.MRP in by_type
    assert by_type[DeclarationType.MRP].normalized_value["amount"] == 120.0
    assert by_type[DeclarationType.MRP].has_conflict is False

    # Commodity Name is Biscuits
    assert DeclarationType.COMMODITY_NAME in by_type
    assert by_type[DeclarationType.COMMODITY_NAME].normalized_value["commodity_name"] == "Biscuits"

    # Consumer Care Phone & Email
    assert DeclarationType.CONSUMER_CARE_PHONE in by_type
    assert "1800" in by_type[DeclarationType.CONSUMER_CARE_PHONE].normalized_value["digits"]
    assert DeclarationType.CONSUMER_CARE_EMAIL in by_type
    assert by_type[DeclarationType.CONSUMER_CARE_EMAIL].normalized_value["email"] == "feedback@britindia.com"

    # Batch No with instruction only must NOT exist
    assert DeclarationType.BATCH_OR_LOT_NUMBER not in by_type

    # Ensure no spurious conflicts exist on any extracted candidate
    for cand in consolidated:
        assert cand.has_conflict is False


def test_lot_no_alone_does_not_produce_batch_value():
    """'LOT No.' alone or 'LOT NO.' without code must not fabricate 'No' as batch number."""
    extractor = DeclarationExtractor()
    b1 = MockOCRBlock("b1", "LOT No.", 0.95, 10, 100, 100, 130)
    candidates1 = extractor.extract_from_image_blocks("img_test", "BACK", [b1])
    assert not any(c.declaration_type == DeclarationType.BATCH_OR_LOT_NUMBER for c in candidates1)

    b2 = MockOCRBlock("b2", "LOT NO.", 0.95, 10, 100, 100, 130)
    candidates2 = extractor.extract_from_image_blocks("img_test", "BACK", [b2])
    assert not any(c.declaration_type == DeclarationType.BATCH_OR_LOT_NUMBER for c in candidates2)


def test_nutrition_sodium_and_protein_not_net_quantity():
    """'Sodium 220 mg' and 'Protein 6.7 g' in nutrient contexts must not become NET_QUANTITY."""
    extractor = DeclarationExtractor()
    b1 = MockOCRBlock("b1", "Sodium 220 mg", 0.96, 10, 100, 180, 130)
    candidates1 = extractor.extract_from_image_blocks("img_test", "BACK", [b1])
    assert not any(c.declaration_type == DeclarationType.NET_QUANTITY for c in candidates1)

    b2 = MockOCRBlock("b2", "Recommended Dietary Allowance 220mg", 0.95, 10, 140, 300, 170)
    candidates2 = extractor.extract_from_image_blocks("img_test", "BACK", [b2])
    assert not any(c.declaration_type == DeclarationType.NET_QUANTITY for c in candidates2)

    b3 = MockOCRBlock("b3", "Protein 6.7 g", 0.95, 10, 180, 180, 210)
    candidates3 = extractor.extract_from_image_blocks("img_test", "BACK", [b3])
    assert not any(c.declaration_type == DeclarationType.NET_QUANTITY for c in candidates3)


def test_biscuits_net_weight_multipack_net_qty():
    """'BISCUITS NET WEIGHT 10 N x 82.7 g = 827 g' => NET_QUANTITY 827g."""
    extractor = DeclarationExtractor()
    b = MockOCRBlock("b1", "BISCUITS NET WEIGHT 10 N x 82.7 g = 827 g", 0.98, 10, 100, 350, 130)
    candidates = extractor.extract_from_image_blocks("img_test", "BACK", [b])
    net_qty = next((c for c in candidates if c.declaration_type == DeclarationType.NET_QUANTITY), None)
    assert net_qty is not None
    assert net_qty.normalized_value["canonical_value"] == 827
    assert net_qty.normalized_value["unit"] == "g"


def test_invalid_nutrition_candidates_do_not_create_conflicts():
    """Package with true Net Weight 827g and nutrition items must not trigger NET_QUANTITY conflict."""
    extractor = DeclarationExtractor()
    blocks = [
        MockOCRBlock("b1", "NET WEIGHT 827 g", 0.97, 10, 50, 200, 80),
        MockOCRBlock("b2", "Serving Size 15 g", 0.95, 10, 100, 200, 130),
        MockOCRBlock("b3", "Sodium 220 mg", 0.95, 10, 150, 180, 180),
        MockOCRBlock("b4", "Protein 6.7 g", 0.94, 10, 200, 180, 230),
    ]
    images_data = [{"image_id": "img_conf_test", "image_type": "BACK", "blocks": blocks}]
    consolidated = extractor.extract_and_consolidate_scan(images_data)

    net_qty_cands = [c for c in consolidated if c.declaration_type == DeclarationType.NET_QUANTITY]
    assert len(net_qty_cands) == 1
    assert net_qty_cands[0].normalized_value["canonical_value"] == 827
    assert net_qty_cands[0].has_conflict is False


def test_taxonomy_enum_mappings_consistency():
    """Verify backend DeclarationType enum values map consistently."""
    expected_types = [
        "MRP", "NET_QUANTITY", "COMMODITY_NAME", "DATE_OF_MANUFACTURE",
        "DATE_OF_PACKING", "EXPIRY_DATE", "MANUFACTURER_NAME", "MANUFACTURER_ADDRESS",
        "PACKER_NAME", "PACKER_ADDRESS", "IMPORTER_NAME", "IMPORTER_ADDRESS",
        "COUNTRY_OF_ORIGIN", "CONSUMER_CARE_PHONE", "CONSUMER_CARE_EMAIL",
        "BATCH_OR_LOT_NUMBER"
    ]
    for t in expected_types:
        assert hasattr(DeclarationType, t)
        assert DeclarationType[t].value == t




