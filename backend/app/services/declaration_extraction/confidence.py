"""Deterministic confidence calculation for LegalMetrix AI Declaration Extraction.

Hardened v1.5.0:
- Added value_validity_score dimension (0.0–1.0) to penalize structurally invalid values.
- Added cross-panel_corroboration_bonus for candidates confirmed across multiple image panels.
- Thresholds adjusted to HIGH ≥ 0.82, MEDIUM ≥ 0.58 (was 0.60) for better calibration.
"""
from typing import Any, Dict, Optional, Tuple
from app.core.enums import ConfidenceLevel


def calculate_extraction_confidence(
    ocr_confidence: float,
    has_explicit_label: bool,
    pattern_score: float = 1.0,
    spatial_score: float = 1.0,
    custom_penalty: float = 0.0,
    value_validity_score: float = 1.0,
    cross_panel_corroborated: bool = False,
) -> Tuple[float, ConfidenceLevel, Dict[str, Any]]:
    """
    Calculate deterministic extraction confidence and return score, level, and breakdown.

    Formula (weights sum to 1.0):
        score = 0.30 * ocr_conf
              + 0.25 * label_conf
              + 0.22 * pattern_conf
              + 0.13 * validity_conf
              + 0.10 * spatial_conf
              + 0.05 * corroboration_bonus
              - penalty

    Args:
        ocr_confidence:           Average OCR engine confidence for source blocks (0–1).
        has_explicit_label:       True when the declaration has a printed keyword prefix.
        pattern_score:            How well the extracted value matches the expected pattern (0–1).
        spatial_score:            Layout quality (single-line=1.0, multi-line=0.9, etc.) (0–1).
        custom_penalty:           Caller-supplied deduction for domain-specific issues (0–1).
        value_validity_score:     Structural validity of the normalized value (amount>0, date valid, etc.) (0–1).
        cross_panel_corroborated: True if an identical value was extracted from ≥2 image panels.
    """
    label_score = 1.0 if has_explicit_label else 0.65
    corroboration_bonus = 0.05 if cross_panel_corroborated else 0.0

    weighted_ocr = 0.30 * max(0.0, min(1.0, ocr_confidence))
    weighted_label = 0.25 * max(0.0, min(1.0, label_score))
    weighted_pattern = 0.22 * max(0.0, min(1.0, pattern_score))
    weighted_validity = 0.13 * max(0.0, min(1.0, value_validity_score))
    weighted_spatial = 0.10 * max(0.0, min(1.0, spatial_score))

    raw_score = (
        weighted_ocr
        + weighted_label
        + weighted_pattern
        + weighted_validity
        + weighted_spatial
        + corroboration_bonus
    ) - custom_penalty
    final_score = round(max(0.0, min(1.0, raw_score)), 4)

    if final_score >= 0.82:
        level = ConfidenceLevel.HIGH
    elif final_score >= 0.58:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    breakdown = {
        "overall_resolution_confidence": final_score,
        "confidence_level": level.value,
        "ocr_confidence": round(ocr_confidence, 4),
        "association_confidence": round((label_score + spatial_score) / 2.0, 4),
        "semantic_confidence": round((pattern_score + value_validity_score) / 2.0, 4),
        "completeness_confidence": round(value_validity_score, 4),
        "consistency_confidence": round(0.5 + corroboration_bonus if cross_panel_corroborated else 0.5, 4),
        "has_explicit_label": has_explicit_label,
        "cross_panel_corroborated": cross_panel_corroborated,
        "penalty": round(custom_penalty, 4),
        # keep old fields for backwards compat
        "final_confidence": final_score,
        "label_score": round(label_score, 4),
        "pattern_score": round(pattern_score, 4),
        "value_validity_score": round(value_validity_score, 4),
        "spatial_score": round(spatial_score, 4),
    }

    return final_score, level, breakdown
