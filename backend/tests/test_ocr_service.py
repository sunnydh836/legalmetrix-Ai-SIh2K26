import cv2
import numpy as np
import pytest
from app.schemas.common import BoundingBox
from app.schemas.ocr import OCRBlockItem
from app.services.ocr_service import MockOCRService, PaddleOCRService


@pytest.fixture
def sample_text_image(tmp_path):
    """Generate image with readable text for OCR engine verification."""
    img_path = str(tmp_path / "ocr_sample.png")
    img = np.full((300, 600, 3), 255, dtype=np.uint8)

    # Line 1: Header
    cv2.putText(img, "LEGALMETRIX TEST", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    # Line 2: Mandatory declaration
    cv2.putText(img, "MRP Rs 150.00", (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    # Line 3: Net qty
    cv2.putText(img, "Net Qty: 1 kg", (30, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    cv2.imwrite(img_path, img)
    return img_path


@pytest.fixture
def blank_image(tmp_path):
    """Generate blank image with no text."""
    img_path = str(tmp_path / "blank.png")
    img = np.full((200, 400, 3), 255, dtype=np.uint8)
    cv2.imwrite(img_path, img)
    return img_path


def test_mock_ocr_service():
    service = MockOCRService()
    res = service.process_image("dummy_path.jpg", scan_image_id="img-001")

    assert res.scan_image_id == "img-001"
    assert len(res.blocks) == 4
    assert res.blocks[0].text.startswith("MRP")
    assert res.blocks[0].confidence == 0.96
    assert res.blocks[0].polygon is not None
    assert len(res.blocks[0].polygon) == 4
    assert res.blocks[0].block_order == 0


def test_paddle_ocr_real_inference(sample_text_image):
    service = PaddleOCRService()
    res = service.process_image(sample_text_image, scan_image_id="img-real-001")

    assert res.scan_image_id == "img-real-001"
    assert res.engine == "paddleocr-rapidocr"
    assert res.processing_duration_ms > 0
    assert len(res.blocks) >= 2

    # Verify extracted text content contains expected words
    full_text = " ".join(b.text.upper() for b in res.blocks)
    assert "MRP" in full_text or "150" in full_text or "QTY" in full_text or "LEGALMETRIX" in full_text

    # Verify geometry and confidence
    for block in res.blocks:
        assert 0.0 <= block.confidence <= 1.0
        assert block.bbox.x1 <= block.bbox.x2
        assert block.bbox.y1 <= block.bbox.y2
        assert block.polygon is not None
        assert len(block.polygon) == 4


def test_reading_order_sorting():
    blocks = [
        OCRBlockItem(
            text="Bottom Line",
            confidence=0.9,
            bbox=BoundingBox(x1=50, y1=300, x2=200, y2=330),
            polygon=[[50, 300], [200, 300], [200, 330], [50, 330]],
        ),
        OCRBlockItem(
            text="Top Line Right",
            confidence=0.9,
            bbox=BoundingBox(x1=300, y1=50, x2=450, y2=80),
            polygon=[[300, 50], [450, 50], [450, 80], [300, 80]],
        ),
        OCRBlockItem(
            text="Top Line Left",
            confidence=0.9,
            bbox=BoundingBox(x1=50, y1=50, x2=200, y2=80),
            polygon=[[50, 50], [200, 50], [200, 80], [50, 80]],
        ),
    ]

    sorted_blocks = PaddleOCRService._sort_reading_order(blocks)
    assert sorted_blocks[0].text == "Top Line Left"
    assert sorted_blocks[1].text == "Top Line Right"
    assert sorted_blocks[2].text == "Bottom Line"
    assert sorted_blocks[0].block_order == 0
    assert sorted_blocks[1].block_order == 1
    assert sorted_blocks[2].block_order == 2


def test_blank_image_handling(blank_image):
    service = PaddleOCRService()
    res = service.process_image(blank_image)

    assert res.blocks == []
    assert res.processing_duration_ms >= 0
