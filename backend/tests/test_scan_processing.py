import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import ImageProcessingStatus, ImageQualityStatus, ScanStatus, UserRole
from app.core.security import create_access_token
from app.models.image_quality import ImageQualityMetric
from app.models.ocr_block import OCRBlock
from app.models.scan_image import ScanImage
from app.models.scan_session import ScanSession
from app.models.user import User
from app.services.storage_service import LocalStorageService, get_storage_service
from app.main import app


def _create_sample_package_image_bytes() -> bytes:
    """Create a realistic synthetic package image bytes with crisp text."""
    img = np.full((600, 800, 3), 245, dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (780, 580), (30, 30, 30), 3)
    cv2.putText(img, "ORGANIC ROLLED OATS", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(img, "MRP Rs. 149.00", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, "Net Qty: 500 g", (50, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, "Mfg Date: 02/2026", (50, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "Consumer Care: 1800-111-222", (50, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


@pytest.fixture
def temp_storage(tmp_path):
    test_storage = LocalStorageService(base_dir=str(tmp_path / "proc_test_storage"))
    app.dependency_overrides[get_storage_service] = lambda: test_storage
    yield test_storage
    app.dependency_overrides.pop(get_storage_service, None)


@pytest.fixture
def second_inspector_token(db_session):
    user2 = User(
        id="usr-inspector-002",
        email="inspector2@legalmetrix.local",
        full_name="Second Inspector",
        password_hash="dummy",
        role=UserRole.INSPECTOR,
        is_active=True,
    )
    db_session.add(user2)
    db_session.commit()
    return create_access_token({"sub": "usr-inspector-002", "role": "INSPECTOR", "email": "inspector2@legalmetrix.local"})


def test_process_scan_end_to_end(client: TestClient, inspector_token: str, temp_storage, db_session: Session):
    # 1. Create scan
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    assert create_res.status_code == 201
    scan_id = create_res.json()["id"]

    # 2. Upload image
    img_bytes = _create_sample_package_image_bytes()
    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("label_back.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "BACK"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()[0]["id"]

    # 3. Process scan
    proc_res = client.post(
        f"/api/v1/scans/{scan_id}/process",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert proc_res.status_code == 200
    proc_data = proc_res.json()
    assert proc_data["status"] == "OCR_COMPLETED"
    assert proc_data["images_processed"] == 1
    img_detail = proc_data["images"][0]
    assert img_detail["image_id"] == image_id
    assert img_detail["processing_status"] in ["COMPLETED", "RECAPTURE_RECOMMENDED"]
    assert img_detail["quality"] is not None
    assert img_detail["quality"]["blur_score"] > 0
    assert len(img_detail["ocr_blocks"]) > 0

    # 4. Verify persistence in database
    db_img = db_session.query(ScanImage).filter(ScanImage.id == image_id).first()
    assert db_img.processing_status in ["COMPLETED", "RECAPTURE_RECOMMENDED"]
    assert db_img.ocr_processing_duration_ms > 0

    db_qm = db_session.query(ImageQualityMetric).filter(ImageQualityMetric.scan_image_id == image_id).first()
    assert db_qm is not None
    assert db_qm.width == 800
    assert db_qm.height == 600

    db_blocks = db_session.query(OCRBlock).filter(OCRBlock.scan_image_id == image_id).all()
    assert len(db_blocks) > 0
    for block in db_blocks:
        assert block.polygon is not None
        assert block.block_order >= 0
        assert 0.0 <= block.confidence <= 1.0


def test_get_ocr_results(client: TestClient, inspector_token: str, temp_storage):
    # Create scan + upload image + process
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    img_bytes = _create_sample_package_image_bytes()
    client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("label.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    client.post(f"/api/v1/scans/{scan_id}/process", headers={"Authorization": f"Bearer {inspector_token}"})

    # Fetch OCR results
    ocr_res = client.get(f"/api/v1/scans/{scan_id}/ocr", headers={"Authorization": f"Bearer {inspector_token}"})
    assert ocr_res.status_code == 200
    data = ocr_res.json()
    assert data["scan_id"] == scan_id
    assert data["status"] == "OCR_COMPLETED"
    assert len(data["images"]) == 1
    assert len(data["images"][0]["ocr_blocks"]) > 0


def test_reprocess_scan_idempotency(client: TestClient, inspector_token: str, temp_storage, db_session: Session):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    img_bytes = _create_sample_package_image_bytes()
    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("label_reprocess.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    image_id = upload_res.json()[0]["id"]

    # Process first time
    proc1 = client.post(f"/api/v1/scans/{scan_id}/process", headers={"Authorization": f"Bearer {inspector_token}"})
    assert proc1.status_code == 200
    block_count_1 = len(proc1.json()["images"][0]["ocr_blocks"])

    # Reprocess second time
    proc2 = client.post(f"/api/v1/scans/{scan_id}/process", headers={"Authorization": f"Bearer {inspector_token}"})
    assert proc2.status_code == 200
    block_count_2 = len(proc2.json()["images"][0]["ocr_blocks"])

    # Database count must equal block count (no duplicates accumulated)
    total_db_blocks = db_session.query(OCRBlock).filter(OCRBlock.scan_image_id == image_id).count()
    assert total_db_blocks == block_count_2
    assert total_db_blocks == block_count_1


def test_reprocess_single_image(client: TestClient, inspector_token: str, temp_storage, db_session: Session):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    img_bytes = _create_sample_package_image_bytes()
    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("panel.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    image_id = upload_res.json()[0]["id"]

    # Reprocess single image endpoint
    reproc_res = client.post(
        f"/api/v1/scans/{scan_id}/images/{image_id}/reprocess",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert reproc_res.status_code == 200
    data = reproc_res.json()
    assert data["image_id"] == image_id
    assert len(data["ocr_blocks"]) > 0


def test_unauthorized_processing_rejected(client: TestClient, inspector_token: str, second_inspector_token: str, temp_storage):
    # Inspector 1 creates scan
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    # Inspector 2 attempts to process Inspector 1's scan -> 403 Forbidden
    proc_res = client.post(
        f"/api/v1/scans/{scan_id}/process",
        headers={"Authorization": f"Bearer {second_inspector_token}"},
    )
    assert proc_res.status_code == 403


def test_zero_image_scan_processing_rejected(client: TestClient, inspector_token: str):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    proc_res = client.post(
        f"/api/v1/scans/{scan_id}/process",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert proc_res.status_code == 400
    assert "no uploaded images" in proc_res.json()["detail"].lower()
