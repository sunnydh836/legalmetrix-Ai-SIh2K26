"""Deterministic confidence calculation for LegalMetrix AI Declaration Extraction."""
from typing import Any, Dict, Tuple
from app.core.enums import ConfidenceLevel


def calculate_extraction_confidence(
    ocr_confidence: float,
    has_explicit_label: bool,
    pattern_score: float = 1.0,
    spatial_score: float = 1.0,
    custom_penalty: float = 0.0,
) -> Tuple[float, ConfidenceLevel, Dict[str, Any]]:
    """
    Calculate deterministic extraction confidence and return score, level, and breakdown.

    Formula:
        score = 0.35 * ocr_conf + 0.30 * label_conf + 0.25 * pattern_conf + 0.10 * spatial_conf - penalty
    """
    label_score = 1.0 if has_explicit_label else 0.70

    weighted_ocr = 0.35 * max(0.0, min(1.0, ocr_confidence))
    weighted_label = 0.30 * max(0.0, min(1.0, label_score))
    weighted_pattern = 0.25 * max(0.0, min(1.0, pattern_score))
    weighted_spatial = 0.10 * max(0.0, min(1.0, spatial_score))

    raw_score = (weighted_ocr + weighted_label + weighted_pattern + weighted_spatial) - custom_penalty
    final_score = round(max(0.0, min(1.0, raw_score)), 4)

    if final_score >= 0.82:
        level = ConfidenceLevel.HIGH
    elif final_score >= 0.60:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    breakdown = {
        "final_confidence": final_score,
        "confidence_level": level.value,
        "ocr_confidence": round(ocr_confidence, 4),
        "label_score": round(label_score, 4),
        "has_explicit_label": has_explicit_label,
        "pattern_score": round(pattern_score, 4),
        "spatial_score": round(spatial_score, 4),
        "penalty": round(custom_penalty, 4),
    }

    return final_score, level, breakdown
