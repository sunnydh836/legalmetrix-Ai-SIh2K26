import logging
from typing import Any, Dict, List, Optional
from app.core.enums import DeclarationType, ResolutionStatus
from app.services.declaration_extraction.extractor import ExtractedCandidate

logger = logging.getLogger(__name__)

def resolve_declaration(
    field_type: DeclarationType, 
    candidates: List[ExtractedCandidate], 
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Exception-based resolution logic to determine the canonical value and ResolutionStatus.
    """
    if not candidates:
        return {
            "resolution_status": ResolutionStatus.NOT_DETECTED,
            "canonical_value": None,
            "resolution_reason": "No candidates found for this field.",
            "candidate_details": []
        }

    # Filter out candidates with zero confidence or marked as conflicted locally
    valid_candidates = [c for c in candidates if c.confidence > 0 and not c.has_conflict]
    
    candidate_details = [
        {
            "raw_text": c.raw_text,
            "raw_value": c.raw_value,
            "normalized_value": c.normalized_value,
            "confidence_breakdown": c.confidence_breakdown,
            "source_block_ids": c.source_block_ids,
            "image_id": c.scan_image_id
        }
        for c in candidates
    ]

    if not valid_candidates:
        return {
            "resolution_status": ResolutionStatus.NOT_DETECTED,
            "canonical_value": None,
            "resolution_reason": "All candidates were rejected due to zero confidence or conflicts.",
            "candidate_details": candidate_details
        }

    # Sort candidates by overall confidence descending
    sorted_candidates = sorted(valid_candidates, key=lambda x: x.confidence, reverse=True)
    best_candidate = sorted_candidates[0]
    best_breakdown = best_candidate.confidence_breakdown

    # If there is only one valid candidate or the best is extremely dominant
    # We must explicitly check specific confidences (semantic, association, etc.)
    # to allow AUTO_RESOLVED. Just high OCR confidence is NOT enough.
    
    # Extract dimensions
    assoc_conf = best_breakdown.get("association_confidence", 0.0)
    sem_conf = best_breakdown.get("semantic_confidence", 0.0)
    comp_conf = best_breakdown.get("completeness_confidence", 0.0)
    ocr_conf = best_breakdown.get("ocr_confidence", 0.0)
    overall_conf = best_breakdown.get("overall_resolution_confidence", 0.0)

    # Criteria for AUTO_RESOLVED:
    is_auto_resolvable = (
        ocr_conf >= 0.70 and
        assoc_conf >= 0.80 and
        sem_conf >= 0.75 and
        comp_conf >= 0.80
    )

    if len(valid_candidates) == 1:
        if is_auto_resolvable:
            status = ResolutionStatus.AUTO_RESOLVED
            reason = "A highly confident, semantically valid candidate was found."
        else:
            status = ResolutionStatus.NEEDS_REVIEW
            reason = "Candidate found but confidence metrics (semantic/association/completeness) are too low for auto-resolution."
    else:
        # Multiple valid candidates -> Check for true conflict vs partial
        # Simple heuristic: if the best candidate is significantly better, use it.
        # Otherwise, true conflict.
        second_best = sorted_candidates[1]
        
        # Conflict check threshold
        if (best_candidate.confidence - second_best.confidence) < 0.15:
            # We have a potential conflict. Wait, partial vs true conflict resolution logic should ideally merge them.
            # Normalizer logic check
            val1 = best_candidate.normalized_value.get("value") or best_candidate.normalized_value.get("name") or best_candidate.raw_value
            val2 = second_best.normalized_value.get("value") or second_best.normalized_value.get("name") or second_best.raw_value
            
            val1_str = str(val1).lower()
            val2_str = str(val2).lower()

            if val1_str in val2_str or val2_str in val1_str:
                # Partial match (e.g., partial address). The larger one should be considered better completeness.
                better_val, lower_val = (best_candidate, second_best) if len(val1_str) >= len(val2_str) else (second_best, best_candidate)
                best_candidate = better_val
                status = ResolutionStatus.AUTO_RESOLVED if is_auto_resolvable else ResolutionStatus.NEEDS_REVIEW
                reason = "Resolved partial collision by selecting the most complete candidate."
            else:
                status = ResolutionStatus.CONFLICT
                reason = "Multiple strong, incompatible candidates detected."
                best_candidate = None # Don't auto-pick a canonical value on true conflict
        else:
            if is_auto_resolvable:
                status = ResolutionStatus.AUTO_RESOLVED
                reason = "Dominant candidate resolved automatically."
            else:
                status = ResolutionStatus.NEEDS_REVIEW
                reason = "Dominant candidate needs review due to low specific confidence metrics."

    res = {
        "resolution_status": status,
        "canonical_value": best_candidate.normalized_value if best_candidate else None,
        "resolution_reason": reason,
        "candidate_details": candidate_details
    }
    
    # Store overall confidence inside the returned object to set on the instance later
    if best_candidate:
         res["confidence"] = best_candidate.confidence
         res["confidence_level"] = best_candidate.confidence_level

    return res
