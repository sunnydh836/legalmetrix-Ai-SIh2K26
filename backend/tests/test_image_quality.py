import io
import os
import tempfile
import cv2
import numpy as np
import pytest
from PIL import Image

from app.core.enums import ImageQualityStatus, ImageQualityWarning
from app.services.image_quality_service import OpenCVImageQualityService


@pytest.fixture
def temp_image_dir(tmp_path):
    """Fixture providing temporary directory for test image generation."""
    img_dir = tmp_path / "quality_test_images"
    img_dir.mkdir()
    return img_dir


def _create_sharp_image(path: str, size=(800, 600)):
    """Generate high-contrast, sharp image with crisp text."""
    img = np.full((size[1], size[0], 3), 240, dtype=np.uint8)
    # Add high-contrast text and geometric patterns
    cv2.rectangle(img, (50, 50), (size[0] - 50, size[1] - 50), (20, 20, 20), 4)
    for y in range(100, size[1] - 100, 60):
        cv2.putText(img, f"MRP Rs. 149.00 NET QTY 500g BATCH #{y}", (70, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.imwrite(str(path), img)


def _create_blurry_image(path: str, size=(800, 600)):
    """Generate heavily blurred image."""
    img = np.full((size[1], size[0], 3), 200, dtype=np.uint8)
    cv2.putText(img, "Faint Blurry Text", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2)
    # Strong Gaussian blur
    blurred = cv2.GaussianBlur(img, (51, 51), 0)
    cv2.imwrite(str(path), blurred)


def _create_glare_image(path: str, size=(800, 600)):
    """Generate image with heavy specular glare blowout."""
    img = np.full((size[1], size[0], 3), 100, dtype=np.uint8)
    # Large saturated white circle simulating flash / glare
    cv2.circle(img, (size[0] // 2, size[1] // 2), 220, (255, 255, 255), -1)
    cv2.imwrite(str(path), img)


def _create_low_res_image(path: str, size=(200, 150)):
    """Generate low-resolution image below minimum OCR threshold."""
    img = np.full((size[1], size[0], 3), 220, dtype=np.uint8)
    cv2.putText(img, "Low Res", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    cv2.imwrite(str(path), img)


def test_sharp_image_evaluation(temp_image_dir):
    img_path = str(temp_image_dir / "sharp.jpg")
    _create_sharp_image(img_path)

    service = OpenCVImageQualityService(blur_threshold=50.0)
    res = service.evaluate_quality(img_path)

    assert res.quality_status == ImageQualityStatus.ACCEPTED
    assert res.blur_score > 50.0
    assert res.glare_score < 0.05
    assert len(res.warnings) == 0
    assert res.resolution["width"] == 800
    assert res.resolution["height"] == 600


def test_blurry_image_detection(temp_image_dir):
    img_path = str(temp_image_dir / "blurred.jpg")
    _create_blurry_image(img_path)

    service = OpenCVImageQualityService(blur_threshold=100.0)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.BLUR in res.warnings
    assert res.blur_score < 100.0
    assert res.quality_status in [ImageQualityStatus.REVIEW, ImageQualityStatus.RECAPTURE_RECOMMENDED]


def test_glare_image_detection(temp_image_dir):
    img_path = str(temp_image_dir / "glare.jpg")
    _create_glare_image(img_path)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.GLARE in res.warnings
    assert res.glare_score > 0.05
    assert res.quality_status in [ImageQualityStatus.REVIEW, ImageQualityStatus.RECAPTURE_RECOMMENDED]


def test_low_resolution_detection(temp_image_dir):
    img_path = str(temp_image_dir / "low_res.jpg")
    _create_low_res_image(img_path, size=(200, 150))

    service = OpenCVImageQualityService(min_width=400, min_height=400)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.LOW_RESOLUTION in res.warnings
    assert res.resolution["width"] == 200
    assert res.resolution["height"] == 150
    assert res.quality_status in [ImageQualityStatus.REVIEW, ImageQualityStatus.RECAPTURE_RECOMMENDED]


def test_missing_file_raises_not_found():
    service = OpenCVImageQualityService()
    with pytest.raises(FileNotFoundError):
        service.evaluate_quality("non_existent_image_path_12345.jpg")


def test_case_a_product_on_large_plain_white_background(temp_image_dir):
    """Case A: Product packaging centered on a large plain white backdrop."""
    img_path = str(temp_image_dir / "case_a_white_bg.jpg")
    # 800x600 pure white background
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    # Centered packaging (brown/gold box with text)
    img[120:480, 200:600] = (40, 140, 210)
    cv2.putText(img, "PARLE-G GOLD BISCUITS", (230, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "Net Qty: 100g MRP: Rs. 10.00", (230, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(img_path, img)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.GLARE not in res.warnings
    assert res.glare_score < 0.05
    assert res.quality_status == ImageQualityStatus.ACCEPTED
    assert res.details["background_ratio"] > 0.35


def test_case_b_product_on_dark_background(temp_image_dir):
    """Case B: Product on dark textured background with no specular glare."""
    img_path = str(temp_image_dir / "case_b_dark_bg.jpg")
    img = np.full((600, 800, 3), 35, dtype=np.uint8)
    # Product package in center
    img[100:500, 150:650] = (60, 150, 220)
    cv2.putText(img, "PREMIUM COOKIES", (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2)
    cv2.putText(img, "Batch #B442 MFD: 08/2026", (200, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.imwrite(img_path, img)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.GLARE not in res.warnings
    assert res.glare_score < 0.05
    assert res.quality_status == ImageQualityStatus.ACCEPTED


def test_case_c_product_with_small_genuine_reflected_highlight(temp_image_dir):
    """Case C: Product with a genuine small localized specular reflection hotspot."""
    img_path = str(temp_image_dir / "case_c_small_highlight.jpg")
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    # Package area
    img[100:500, 200:600] = (40, 120, 200)
    # Small specular reflection hotspot (radius 18)
    cv2.circle(img, (380, 280), 18, (255, 255, 255), -1)
    cv2.imwrite(img_path, img)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    # Glare should be localized to foreground only (small percentage)
    assert res.glare_score > 0.0
    assert res.glare_score < 0.05  # small highlight does not exceed 5% total product area


def test_case_d_product_with_strong_flash_reflection(temp_image_dir):
    """Case D: Product with strong glossy flash reflection across label."""
    img_path = str(temp_image_dir / "case_d_flash_glare.jpg")
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    img[100:500, 200:600] = (40, 120, 200)
    # Large intense flash glare covering substantial portion of label
    cv2.circle(img, (400, 300), 110, (255, 255, 255), -1)
    cv2.imwrite(img_path, img)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.GLARE in res.warnings
    assert res.glare_score > 0.05
    assert res.quality_status in [ImageQualityStatus.REVIEW, ImageQualityStatus.RECAPTURE_RECOMMENDED]


def test_case_e_completely_overexposed_image(temp_image_dir):
    """Case E: Completely washed-out / overexposed image."""
    img_path = str(temp_image_dir / "case_e_overexposed.jpg")
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    cv2.imwrite(img_path, img)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.GLARE in res.warnings
    assert res.glare_score >= 0.9
    assert res.quality_status in [ImageQualityStatus.REVIEW, ImageQualityStatus.RECAPTURE_RECOMMENDED]


def test_case_f_large_white_printed_package_design(temp_image_dir):
    """Case F: Product packaging with large white printed graphic elements."""
    img_path = str(temp_image_dir / "case_f_white_print.jpg")
    img = np.full((600, 800, 3), 40, dtype=np.uint8)
    # Product body
    img[100:500, 150:650] = (50, 100, 180)
    # Printed white label panel (diffuse white print ~225 luminance)
    img[180:420, 220:580] = (225, 225, 225)
    cv2.putText(img, "NUTRITION FACTS & INGREDIENTS", (230, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(img, "Energy: 450 kcal | Protein: 8g", (230, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.putText(img, "Manufactured by: Legal Food Ltd", (230, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.imwrite(img_path, img)

    service = OpenCVImageQualityService(glare_threshold=0.05)
    res = service.evaluate_quality(img_path)

    assert ImageQualityWarning.GLARE not in res.warnings
    assert res.glare_score < 0.05
    assert res.quality_status == ImageQualityStatus.ACCEPTED

