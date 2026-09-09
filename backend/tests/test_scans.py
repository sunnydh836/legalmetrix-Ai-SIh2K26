import io
import os
import shutil
import tempfile
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ImageType, ScanStatus, UserRole
from app.core.security import create_access_token
from app.models.product import Product
from app.models.scan_image import ScanImage
from app.models.scan_session import ScanSession
from app.models.user import User
from app.services.storage_service import LocalStorageService, get_storage_service
from app.main import app


def _create_sample_image_bytes(format="JPEG", size=(600, 800), color="blue") -> bytes:
    """Helper to generate valid image bytes in-memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def temp_storage(tmp_path):
    """Fixture providing an isolated LocalStorageService for testing."""
    test_storage = LocalStorageService(base_dir=str(tmp_path / "test_storage"))
    app.dependency_overrides[get_storage_service] = lambda: test_storage
    yield test_storage
    app.dependency_overrides.pop(get_storage_service, None)


@pytest.fixture
def second_inspector_token(db_session):
    """Token for a second seeded inspector for IDOR/ownership tests."""
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


# =========================================================================
# 1. SCAN CREATION & RBAC TESTS
# =========================================================================

def test_inspector_can_create_scan(client: TestClient, inspector_token: str, db_session: Session):
    response = client.post(
        "/api/v1/scans",
        json={
            "product": {
                "name": "Organic Rolled Oats 500g",
                "brand": "Nature Valley",
                "category": "Packaged Food",
                "barcode": "8901234567890",
                "manufacturer_name": "Nature Foods Ltd",
            }
        },
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scan_code"].startswith("SCAN-")
    assert data["status"] == "CREATED"
    assert data["product"]["name"] == "Organic Rolled Oats 500g"
    assert data["product"]["barcode"] == "8901234567890"
    assert data["inspector"]["id"] == "usr-inspector-001"
    assert len(data["images"]) == 0


def test_unauthenticated_scan_creation_rejected(client: TestClient):
    response = client.post("/api/v1/scans", json={})
    assert response.status_code == 401


def test_reviewer_cannot_create_scan(client: TestClient, reviewer_token: str):
    response = client.post(
        "/api/v1/scans",
        json={"product": {"name": "Unauthorized Test"}},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 403


def test_admin_can_create_scan(client: TestClient, admin_token: str):
    response = client.post(
        "/api/v1/scans",
        json={"product": {"name": "Admin Test Product"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "CREATED"


def test_inspector_id_comes_from_token_not_payload(client: TestClient, inspector_token: str):
    # Attempt to spoof inspector_id
    response = client.post(
        "/api/v1/scans",
        json={"product": {"name": "Spoof Test"}, "inspector_id": "usr-admin-001"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["inspector"]["id"] == "usr-inspector-001"


# =========================================================================
# 2. PRODUCT METADATA & EXACT BARCODE REUSE
# =========================================================================

def test_exact_barcode_reuse(client: TestClient, inspector_token: str):
    barcode = "8909999888877"
    # Create first scan with barcode
    res1 = client.post(
        "/api/v1/scans",
        json={"product": {"name": "Product Alpha", "brand": "Brand X", "barcode": barcode}},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res1.status_code == 201
    prod1_id = res1.json()["product"]["id"]

    # Create second scan with same barcode
    res2 = client.post(
        "/api/v1/scans",
        json={"product": {"name": "Product Beta", "barcode": barcode, "category": "Dairy"}},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res2.status_code == 201
    prod2_id = res2.json()["product"]["id"]

    # Must reuse the same product ID
    assert prod1_id == prod2_id


def test_barcode_lookup_endpoint(client: TestClient, inspector_token: str):
    barcode = "8905555444433"
    client.post(
        "/api/v1/scans",
        json={"product": {"name": "Lookup Item", "barcode": barcode, "brand": "TestBrand"}},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )

    res = client.get(
        f"/api/v1/products/by-barcode/{barcode}",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Lookup Item"
    assert res.json()["barcode"] == barcode


# =========================================================================
# 3. IMAGE UPLOADS & VALIDATION
# =========================================================================

def test_jpeg_upload_and_status_transition(client: TestClient, inspector_token: str, temp_storage):
    # 1. Create scan
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]
    assert create_res.json()["status"] == "CREATED"

    # 2. Upload JPEG image
    img_bytes = _create_sample_image_bytes(format="JPEG", size=(800, 600), color="red")
    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("front_label.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert upload_res.status_code == 200
    images = upload_res.json()
    assert len(images) == 1
    assert images[0]["image_type"] == "FRONT"
    assert images[0]["original_filename"] == "front_label.jpg"
    assert images[0]["width"] == 800
    assert images[0]["height"] == 600
    assert images[0]["display_order"] == 0
    assert images[0]["preview_url"].startswith(f"/api/v1/scans/{scan_id}/images/")

    # 3. Verify scan status transitioned to IMAGES_UPLOADED
    get_res = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {inspector_token}"})
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "IMAGES_UPLOADED"
    assert len(get_res.json()["images"]) == 1


def test_png_upload_and_preview_content(client: TestClient, inspector_token: str, temp_storage):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    png_bytes = _create_sample_image_bytes(format="PNG", size=(640, 480), color="green")
    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("back_panel.png", png_bytes, "image/png")},
        data={"image_type": "BACK"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()[0]["id"]

    # Fetch preview content
    content_res = client.get(
        f"/api/v1/scans/{scan_id}/images/{image_id}/content",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert content_res.status_code == 200
    assert content_res.headers["content-type"] == "image/png"
    assert len(content_res.content) > 0


def test_malformed_and_fake_images_rejected(client: TestClient, inspector_token: str, temp_storage):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    # Fake JPG containing text
    fake_jpg_bytes = b"THIS IS NOT AN IMAGE CONTENT AT ALL"
    res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("fake.jpg", fake_jpg_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 400
    assert "Malformed" in res.json()["detail"] or "Validation" in res.json()["detail"]


def test_unsupported_image_format_rejected(client: TestClient, inspector_token: str, temp_storage):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    # GIF image
    buf = io.BytesIO()
    img = Image.new("P", (100, 100))
    img.save(buf, format="GIF")
    gif_bytes = buf.getvalue()

    res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("anim.gif", gif_bytes, "image/gif")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res.status_code == 400
    assert "Unsupported image format" in res.json()["detail"]


def test_duplicate_image_in_same_scan_rejected(client: TestClient, inspector_token: str, temp_storage):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    img_bytes = _create_sample_image_bytes(format="JPEG", size=(500, 500), color="yellow")

    # First upload succeeds
    res1 = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("label_front.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res1.status_code == 200

    # Second upload with identical image content must return 409 Conflict
    res2 = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("label_front_duplicate.jpg", img_bytes, "image/jpeg")},
        data={"image_type": "SIDE"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert res2.status_code == 409
    assert "already been uploaded for this scan" in res2.json()["detail"]


def test_exif_orientation_normalization(client: TestClient, inspector_token: str, temp_storage):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    # Create image with EXIF orientation tag (e.g. 6 = 90 deg CW rotation)
    img = Image.new("RGB", (400, 200), color="purple")
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    exif_bytes = buf.getvalue()

    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("oriented.jpg", exif_bytes, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert upload_res.status_code == 200
    data = upload_res.json()[0]
    # Width and height should be transposed (400x200 rotated becomes 200x400)
    assert data["width"] == 200
    assert data["height"] == 400


# =========================================================================
# 4. REORDER & DELETE IMAGES
# =========================================================================

def test_reorder_and_delete_images(client: TestClient, inspector_token: str, temp_storage):
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    # Upload 3 different images
    img1 = _create_sample_image_bytes(format="JPEG", size=(300, 300), color="red")
    img2 = _create_sample_image_bytes(format="JPEG", size=(300, 300), color="green")
    img3 = _create_sample_image_bytes(format="JPEG", size=(300, 300), color="blue")

    res1 = client.post(f"/api/v1/scans/{scan_id}/images", files={"files": ("1.jpg", img1, "image/jpeg")}, data={"image_type": "FRONT"}, headers={"Authorization": f"Bearer {inspector_token}"})
    res2 = client.post(f"/api/v1/scans/{scan_id}/images", files={"files": ("2.jpg", img2, "image/jpeg")}, data={"image_type": "BACK"}, headers={"Authorization": f"Bearer {inspector_token}"})
    res3 = client.post(f"/api/v1/scans/{scan_id}/images", files={"files": ("3.jpg", img3, "image/jpeg")}, data={"image_type": "SIDE"}, headers={"Authorization": f"Bearer {inspector_token}"})

    id1 = res1.json()[0]["id"]
    id2 = res2.json()[0]["id"]
    id3 = res3.json()[0]["id"]

    # Reorder: [id3, id1, id2]
    reorder_res = client.patch(
        f"/api/v1/scans/{scan_id}/images/order",
        json={"image_ids": [id3, id1, id2]},
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert reorder_res.status_code == 200
    ordered_imgs = reorder_res.json()
    assert ordered_imgs[0]["id"] == id3
    assert ordered_imgs[0]["display_order"] == 0
    assert ordered_imgs[1]["id"] == id1
    assert ordered_imgs[1]["display_order"] == 1
    assert ordered_imgs[2]["id"] == id2
    assert ordered_imgs[2]["display_order"] == 2

    # Delete middle image (id1)
    del_res = client.delete(
        f"/api/v1/scans/{scan_id}/images/{id1}",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert del_res.status_code == 200

    # Verify remaining in scan
    get_res = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {inspector_token}"})
    remaining = get_res.json()["images"]
    assert len(remaining) == 2
    assert [img["id"] for img in remaining] == [id3, id2]

    # Delete remaining images and verify status reverts to CREATED
    client.delete(f"/api/v1/scans/{scan_id}/images/{id3}", headers={"Authorization": f"Bearer {inspector_token}"})
    client.delete(f"/api/v1/scans/{scan_id}/images/{id2}", headers={"Authorization": f"Bearer {inspector_token}"})

    get_res_empty = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {inspector_token}"})
    assert get_res_empty.json()["status"] == "CREATED"
    assert len(get_res_empty.json()["images"]) == 0


# =========================================================================
# 5. IDOR & OWNERSHIP TESTS
# =========================================================================

def test_inspector_cannot_modify_or_view_another_inspectors_scan(
    client: TestClient,
    inspector_token: str,
    second_inspector_token: str,
    temp_storage,
):
    # Inspector 1 creates scan
    create_res = client.post("/api/v1/scans", json={}, headers={"Authorization": f"Bearer {inspector_token}"})
    scan_id = create_res.json()["id"]

    # Inspector 2 tries to GET scan -> 403 Forbidden
    get_res = client.get(f"/api/v1/scans/{scan_id}", headers={"Authorization": f"Bearer {second_inspector_token}"})
    assert get_res.status_code == 403

    # Inspector 2 tries to upload image -> 403 Forbidden
    img = _create_sample_image_bytes()
    upload_res = client.post(
        f"/api/v1/scans/{scan_id}/images",
        files={"files": ("hacked.jpg", img, "image/jpeg")},
        data={"image_type": "FRONT"},
        headers={"Authorization": f"Bearer {second_inspector_token}"},
    )
    assert upload_res.status_code == 403
