"""Evidence association and bounding box geometry utilities."""
from typing import Any, Dict, List, Optional


def compute_union_bounding_box(blocks: List[Any]) -> Dict[str, int]:
    """Compute the tight union bounding box enclosing all contributing OCR blocks."""
    if not blocks:
        return {"bbox_x1": 0, "bbox_y1": 0, "bbox_x2": 0, "bbox_y2": 0}

    x1 = min(b.bbox_x1 for b in blocks)
    y1 = min(b.bbox_y1 for b in blocks)
    x2 = max(b.bbox_x2 for b in blocks)
    y2 = max(b.bbox_y2 for b in blocks)

    return {
        "bbox_x1": int(x1),
        "bbox_y1": int(y1),
        "bbox_x2": int(x2),
        "bbox_y2": int(y2),
    }


def compute_average_ocr_confidence(blocks: List[Any]) -> float:
    """Compute mean OCR confidence across all contributing OCR blocks."""
    if not blocks:
        return 0.0
    total = sum(float(b.confidence) for b in blocks)
    return round(total / len(blocks), 4)


def build_evidence_payload(
    scan_image_id: Optional[str],
    blocks: List[Any],
    image_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build structured evidence summary referencing all OCR provenance data."""
    union_bbox = compute_union_bounding_box(blocks)
    avg_conf = compute_average_ocr_confidence(blocks)
    block_ids = [b.id for b in blocks if hasattr(b, "id") and b.id]

    block_summaries = [
        {
            "id": getattr(b, "id", None),
            "text": getattr(b, "text", ""),
            "confidence": float(getattr(b, "confidence", 0.0)),
            "bbox": {
                "x1": int(getattr(b, "bbox_x1", 0)),
                "y1": int(getattr(b, "bbox_y1", 0)),
                "x2": int(getattr(b, "bbox_x2", 0)),
                "y2": int(getattr(b, "bbox_y2", 0)),
            },
        }
        for b in blocks
    ]

    return {
        "scan_image_id": scan_image_id,
        "image_type": image_type,
        "ocr_block_ids": block_ids,
        "contributing_blocks_count": len(blocks),
        "bounding_box": union_bbox,
        "average_ocr_confidence": avg_conf,
        "blocks": block_summaries,
    }
