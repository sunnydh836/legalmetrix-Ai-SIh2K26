"""Core Declaration Extraction Engine for LegalMetrix AI.

Performs context-aware, deterministic multi-block extraction, normalization,
evidence linkage, composite confidence scoring, and genuine conflict detection.

Hardened v1.5.0:
- Conflict detection now correctly distinguishes truly contradictory values (genuine conflict)
  from equivalent values appearing on different panels (corroboration → merge + confidence boost).
- MRP false-positive filter: reject number-only candidates if adjacent text contains
  weight/measure words to avoid labelling "500g Rs. 120" as MRP=500.
- Added MARKETED_BY extraction (→ MANUFACTURER_NAME fallback when no explicit MFD BY).
- count-only net quantity extraction via NET_QTY_COUNT_REGEX.
- value_validity_score wired into calculate_extraction_confidence calls.
- cross_panel_corroborated wired correctly during deduplication phase.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.enums import ConfidenceLevel, DeclarationType, ReviewStatus
from app.services.declaration_extraction.confidence import calculate_extraction_confidence
from app.services.declaration_extraction.evidence import (
    build_evidence_payload,
    compute_average_ocr_confidence,
    compute_union_bounding_box,
)
from app.services.declaration_extraction.grouping import (
    TextSpan,
    generate_candidate_text_spans,
    find_neighborhood_blocks,
)
from app.services.declaration_extraction.normalizers import (
    normalize_batch_number,
    normalize_commodity_name,
    normalize_country,
    normalize_date,
    normalize_email,
    normalize_mrp,
    normalize_net_quantity,
    normalize_organization_address,
    normalize_phone,
)
from app.services.declaration_extraction.patterns import (
    BATCH_REGEX,
    BEST_BEFORE_PREFIX_REGEX,
    COMMODITY_PREFIX_REGEX,
    CONSUMER_CARE_HEADER_REGEX,
    COUNTRY_ORIGIN_REGEX,
    EMAIL_REGEX,
    EXPIRY_PREFIX_REGEX,
    FSSAI_NUMBER_PATTERN,
    IMP_DATE_PREFIX_REGEX,
    IMPORTER_PREFIX_REGEX,
    INCL_TAXES_REGEX,
    INSTRUCTION_REFERENCE_REGEX,
    INSTRUCTION_STOP_WORDS,
    LICENCE_OR_ID_REGEX,
    MANUFACTURER_PREFIX_REGEX,
    MARKETED_PREFIX_REGEX,
    MFD_PREFIX_REGEX,
    MRP_AMOUNT_ONLY_REGEX,
    MRP_EXPLICIT_REGEX,
    NET_QTY_COUNT_REGEX,
    NET_QTY_EXPLICIT_REGEX,
    NET_QTY_MULTIPACK_REGEX,
    NET_QTY_STANDALONE_REGEX,
    PACKER_PREFIX_REGEX,
    PHONE_CONTACT_PREFIX_REGEX,
    PHONE_REGEX,
    PKD_PREFIX_REGEX,
    RELATIVE_DATE_REGEX,
    is_instruction_only,
    is_nutrition_context,
    is_weight_or_measure_context,
)
from app.services.declaration_extraction.version import DECLARATION_EXTRACTOR_VERSION


class ExtractedCandidate:
    """Represents an extracted declaration candidate before persistence."""

    def __init__(
        self,
        declaration_type: DeclarationType,
        raw_text: str,
        raw_value: Optional[str],
        normalized_value: Dict[str, Any],
        confidence: float,
        confidence_level: ConfidenceLevel,
        confidence_breakdown: Dict[str, Any],
        scan_image_id: Optional[str],
        image_type: Optional[str],
        blocks: List[Any],
        has_conflict: bool = False,
        conflict_details: Optional[Dict[str, Any]] = None,
    ):
        self.declaration_type = declaration_type
        self.raw_text = raw_text
        self.raw_value = raw_value
        self.normalized_value = normalized_value
        self.confidence = confidence
        self.confidence_level = confidence_level
        self.confidence_breakdown = confidence_breakdown
        self.scan_image_id = scan_image_id
        self.image_type = image_type
        self.blocks = list(blocks)
        self.has_conflict = has_conflict
        self.conflict_details = conflict_details

    @property
    def source_block_ids(self) -> List[str]:
        return [b.id for b in self.blocks if hasattr(b, "id") and b.id]

    @property
    def union_bounding_box(self) -> Dict[str, int]:
        return compute_union_bounding_box(self.blocks)

    @property
    def evidence_payload(self) -> Dict[str, Any]:
        return build_evidence_payload(
            scan_image_id=self.scan_image_id,
            blocks=self.blocks,
            image_type=self.image_type,
        )


class DeclarationExtractor:
    """Context-aware, deterministic extractor for LegalMetrix AI declaration taxonomy."""

    def __init__(self, extractor_version: str = DECLARATION_EXTRACTOR_VERSION):
        self.version = extractor_version

    def extract_from_image_blocks(
        self,
        scan_image_id: str,
        image_type: str,
        blocks: List[Any],
    ) -> List[ExtractedCandidate]:
        """Extract all candidate declarations from OCR blocks of a single image panel."""
        candidates: List[ExtractedCandidate] = []
        if not blocks:
            return candidates

        # 1. Identify all blocks that are nutrition context (lexically or spatially)
        nutrition_block_ids: Set[str] = set()
        nutrition_y_ranges: List[Tuple[float, float]] = []

        for b in blocks:
            b_text = getattr(b, "text", "")
            if is_nutrition_context(b_text):
                b_id = getattr(b, "id", "")
                if b_id:
                    nutrition_block_ids.add(b_id)
                y1 = getattr(b, "bbox_y1", 0)
                y2 = getattr(b, "bbox_y2", 0)
                nutrition_y_ranges.append((y1 - 10, y2 + 10))

        # Spatial expansion: blocks that overlap with nutrition vertical ranges
        if nutrition_y_ranges:
            for b in blocks:
                b_id = getattr(b, "id", "")
                if b_id in nutrition_block_ids:
                    continue
                y1 = getattr(b, "bbox_y1", 0)
                y2 = getattr(b, "bbox_y2", 0)
                for ny1, ny2 in nutrition_y_ranges:
                    if not (y2 < ny1 or y1 > ny2):
                        nutrition_block_ids.add(b_id)
                        break

        spans = generate_candidate_text_spans(blocks, max_n_gram=6)

        for span in spans:
            text = span.text
            avg_ocr_conf = span.confidence

            # Determine negative contexts for this span
            span_is_nutrition = (
                is_nutrition_context(text)
                or any(is_nutrition_context(getattr(b, "text", "")) for b in span.blocks)
                or any(getattr(b, "id", "") in nutrition_block_ids for b in span.blocks)
            )

            # 1. MRP Extraction (Strictly excluded from nutrition context)
            if not span_is_nutrition:
                mrp_cand = self._extract_mrp(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
                if mrp_cand:
                    candidates.append(mrp_cand)

            # 2. Net Quantity Extraction (Strictly excluded from nutrition context)
            if not span_is_nutrition:
                net_qty_cands = self._extract_net_quantity(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
                candidates.extend(net_qty_cands)

            # 3. Country of Origin Extraction
            country_cand = self._extract_country_of_origin(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
            if country_cand:
                candidates.append(country_cand)

            # 4. Dates Extraction
            date_cands = self._extract_dates(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
            candidates.extend(date_cands)

            # 5. Manufacturer / Packer / Importer / Marketed-By
            org_cands = self._extract_organizations(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
            candidates.extend(org_cands)

            # 6. Consumer Care (Phone, Email, Address)
            care_cands = self._extract_consumer_care(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
            candidates.extend(care_cands)

            # 7. Batch / Lot Number
            batch_cand = self._extract_batch_number(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
            if batch_cand:
                candidates.append(batch_cand)

            # 8. Commodity Name
            comm_cand = self._extract_commodity_name(text, span, scan_image_id, image_type, avg_ocr_conf, blocks)
            if comm_cand:
                candidates.append(comm_cand)

        return self._arbitrate_candidates_cross_field(candidates)

    def _arbitrate_candidates_cross_field(self, candidates: List[ExtractedCandidate]) -> List[ExtractedCandidate]:
        """Arbitrate between candidates that share the same OCR blocks.
        Enforces semantic exclusivity so the same text isn't a Batch and a Net Qty."""
        
        # Group candidates by their exact block identities
        from collections import defaultdict
        block_groups = defaultdict(list)
        for c in candidates:
            if not c.blocks:
                continue
            # Use tuple of block IDs as key
            b_ids = tuple(sorted(b.id for b in c.blocks if getattr(b, "id", None)))
            if b_ids:
                block_groups[b_ids].append(c)
                
        strong_types = {
            DeclarationType.NET_QUANTITY, 
            DeclarationType.CONSUMER_CARE_PHONE, 
            DeclarationType.CONSUMER_CARE_EMAIL,
            DeclarationType.MRP,
        }
        
        rejected_candidates = set()
        
        for b_ids, group in block_groups.items():
            if len(group) <= 1:
                continue
                
            # Find the strongest candidate in the group
            strongest = max(group, key=lambda c: c.confidence)
            
            # If the strongest is highly confident and is a semantic 'strong' type, it wins.
            if strongest.confidence >= 0.75 and strongest.declaration_type in strong_types:
                for c in group:
                    if c != strongest and c.declaration_type != strongest.declaration_type:
                        # Reject incompatible interpretation
                        c.has_conflict = True
                        c.confidence = 0.0
                        c.conflict_details = {
                            "conflict_type": f"semantic_conflict_with_{strongest.declaration_type.value}",
                            "message": f"Rejected in favor of {strongest.declaration_type.value}"
                        }
                        rejected_candidates.add(c)
                        
        return [c for c in candidates if c not in rejected_candidates]

    # ------------------------------------------------------------------
    # Field-specific extractors
    # ------------------------------------------------------------------

    def _extract_mrp(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> Optional[ExtractedCandidate]:
        if is_nutrition_context(text):
            return None

        # 1. Explicit MRP Anchor match (e.g. MRP Rs 120, M.R.P. ₹ 99.00, MRPE 20.00)
        explicit_match = MRP_EXPLICIT_REGEX.search(text)
        if explicit_match:
            raw_amt = explicit_match.group(1)
            has_taxes = bool(INCL_TAXES_REGEX.search(text))
            normalized = normalize_mrp(raw_amt, has_taxes_incl=has_taxes)
            if not normalized.get("amount"):
                return None

            validity = 1.0 if normalized.get("_valid") else 0.4
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0,
                spatial_score=1.0 if not span.is_multi_line else 0.9,
                value_validity_score=validity,
            )
            return ExtractedCandidate(
                declaration_type=DeclarationType.MRP,
                raw_text=text,
                raw_value=raw_amt,
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )

        # 2. Standalone currency + amount with strict word boundaries (e.g. ₹120 or Rs. 50)
        amt_match = MRP_AMOUNT_ONLY_REGEX.search(text)
        if amt_match and len(span.blocks) <= 2:
            # Reject if the surrounding text looks like a weight/measure context
            if is_weight_or_measure_context(text):
                return None
            # Reject if "/" in text (could be date or unit) or "g"/"kg" (could be weight)
            if re.search(r"\b\d+\s*(?:g|kg|gm|ml|l)\b", text, re.IGNORECASE):
                return None
            # Reject if the matched text contains date-separators
            if "/" in text or "-" in text:
                context = text[max(0, amt_match.start() - 5): amt_match.end() + 5]
                if re.search(r"\d{1,2}[/\-]\d{2,4}", context):
                    return None

            raw_amt = amt_match.group(1)
            has_taxes = bool(INCL_TAXES_REGEX.search(text))
            normalized = normalize_mrp(raw_amt, has_taxes_incl=has_taxes)
            if not normalized.get("amount"):
                return None

            validity = 1.0 if normalized.get("_valid") else 0.4
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=False,
                pattern_score=0.72,
                spatial_score=1.0,
                value_validity_score=validity,
            )
            return ExtractedCandidate(
                declaration_type=DeclarationType.MRP,
                raw_text=text,
                raw_value=raw_amt,
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )
        return None

    def _extract_net_quantity(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> List[ExtractedCandidate]:
        """Extract net quantity candidates; returns list (may be empty or single item)."""
        if is_nutrition_context(text):
            return []

        # 1. Multi-pack compound expressions (e.g. "10 N x 82.7 g = 827 g")
        mp_match = NET_QTY_MULTIPACK_REGEX.search(text)
        if mp_match:
            normalized = normalize_net_quantity(text)
            if normalized.get("value") is not None:
                validity = 1.0 if normalized.get("_valid") else 0.5
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0,
                    spatial_score=1.0 if not span.is_multi_line else 0.95,
                    value_validity_score=validity,
                )
                return [ExtractedCandidate(
                    declaration_type=DeclarationType.NET_QUANTITY,
                    raw_text=text,
                    raw_value=text.strip(),
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=span.blocks,
                )]

        # 2. Explicit Net Quantity Anchor match (e.g. "NET WEIGHT 827 g", "Net Qty: 500 g")
        explicit_match = NET_QTY_EXPLICIT_REGEX.search(text)
        if explicit_match:
            raw_val = explicit_match.group(1)
            raw_unit = explicit_match.group(2) if len(explicit_match.groups()) >= 2 else None
            normalized = normalize_net_quantity(raw_val, raw_unit)
            has_unit = normalized.get("unit") is not None
            validity = 1.0 if (normalized.get("_valid") and has_unit) else (0.6 if not has_unit else 0.4)
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if has_unit else 0.55,
                spatial_score=1.0 if not span.is_multi_line else 0.9,
                value_validity_score=validity,
            )
            final_conf_level = conf_level
            if not has_unit and final_conf_level == ConfidenceLevel.HIGH:
                final_conf_level = ConfidenceLevel.MEDIUM

            raw_val_str = f"{raw_val} {raw_unit}".strip() if raw_unit else raw_val
            return [ExtractedCandidate(
                declaration_type=DeclarationType.NET_QUANTITY,
                raw_text=text,
                raw_value=raw_val_str,
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=final_conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )]

        # 3. Count-only items (e.g. "30 Tablets", "10 Sachets") — pharma / consumer packs
        count_match = NET_QTY_COUNT_REGEX.search(text)
        if count_match and len(span.blocks) <= 2:
            raw_val = count_match.group(1)
            raw_unit = count_match.group(2)
            normalized = normalize_net_quantity(raw_val, raw_unit)
            validity = 1.0 if normalized.get("_valid") else 0.5
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=False,
                pattern_score=0.88,
                spatial_score=1.0,
                value_validity_score=validity,
            )
            raw_val_str = f"{raw_val} {raw_unit}".strip()
            return [ExtractedCandidate(
                declaration_type=DeclarationType.NET_QUANTITY,
                raw_text=text,
                raw_value=raw_val_str,
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )]

        # 4. Standalone quantity (e.g. "827 g", "500 g", "1 kg") only if outside nutrition context
        standalone_match = NET_QTY_STANDALONE_REGEX.search(text)
        if standalone_match and len(span.blocks) <= 2:
            raw_val = standalone_match.group(1)
            raw_unit = standalone_match.group(2)
            # Standalone mg is almost exclusively a micronutrient
            if raw_unit and raw_unit.lower() == "mg":
                return []
            if is_nutrition_context(text):
                return []
            normalized = normalize_net_quantity(raw_val, raw_unit)
            validity = 1.0 if normalized.get("_valid") else 0.4
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=False,
                pattern_score=0.68,
                spatial_score=1.0,
                value_validity_score=validity,
            )
            raw_val_str = f"{raw_val} {raw_unit}".strip() if raw_unit else raw_val
            return [ExtractedCandidate(
                declaration_type=DeclarationType.NET_QUANTITY,
                raw_text=text,
                raw_value=raw_val_str,
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )]
        return []

    def _extract_country_of_origin(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> Optional[ExtractedCandidate]:
        match = COUNTRY_ORIGIN_REGEX.search(text)
        if match:
            raw_country = match.group(1)
            normalized = normalize_country(raw_country)
            validity = 1.0 if normalized.get("is_recognized") else 0.6
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("is_recognized") else 0.72,
                spatial_score=1.0,
                value_validity_score=validity,
            )
            return ExtractedCandidate(
                declaration_type=DeclarationType.COUNTRY_OF_ORIGIN,
                raw_text=text,
                raw_value=raw_country.strip(),
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )
        return None

    from app.services.declaration_extraction.grouping import find_neighborhood_blocks
    def _extract_dates(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> List[ExtractedCandidate]:
        results: List[ExtractedCandidate] = []

        def _evaluate_date_candidate(
            date_type: DeclarationType, match_text: str, anchor_text: str, search_blocks: List[Any], 
            is_spatial: bool = False
        ) -> Optional[ExtractedCandidate]:
            sem_type = date_type.value
            normalized = normalize_date(match_text, sem_type)
            if normalized.get("date") is not None or normalized.get("is_relative") is True:
                validity = 1.0 if normalized.get("_valid") else 0.5
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0 if (normalized.get("date") or normalized.get("is_relative")) else 0.65,
                    spatial_score=0.9 if is_spatial else 1.0,
                    value_validity_score=validity,
                )
                if is_spatial:
                    breakdown["spatial_relation"] = "nearby_block"
                return ExtractedCandidate(
                    declaration_type=date_type,
                    raw_text=match_text if is_spatial else text,
                    raw_value=match_text,
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=search_blocks,
                )
            
            # Sub-case: Anchor without a value. 
            return None

        def _process_date_anchor(
            regex_match: Any, dtype: DeclarationType, full_text_or_val: str
        ) -> None:
            # 1. Try local matched text first (same line/ngram span)
            cand = _evaluate_date_candidate(dtype, full_text_or_val, regex_match.group(0), span.blocks, False)
            
            if cand and cand.confidence > 0.0:
                results.append(cand)
                return
            
            # 2. Try nearby blocks if local extraction failed (empty anchor case)
            if all_blocks:
                # Prioritize tight spatial neighbors (closest dx/dy first per find_neighborhood_blocks)
                nearby = find_neighborhood_blocks(span, all_blocks, max_horizontal_gap=200.0, max_vertical_gap=60.0)
                for nb in nearby:
                    nb_text = getattr(nb, "text", "")
                    # Verify it's not another anchor to avoid stealing values from other declarations
                    if MFD_PREFIX_REGEX.search(nb_text) or PKD_PREFIX_REGEX.search(nb_text) or EXPIRY_PREFIX_REGEX.search(nb_text):
                        continue
                        
                    nb_cand = _evaluate_date_candidate(dtype, nb_text, regex_match.group(0), span.blocks + [nb], True)
                    if nb_cand and nb_cand.confidence > 0.0:
                        # Found a valid date nearby!
                        results.append(nb_cand)
                        return
                        
            # If we reached here, even spatial search failed. Return nothing.

        # 1. Date of Manufacture
        mfd_match = MFD_PREFIX_REGEX.search(text)
        if mfd_match:
            _process_date_anchor(mfd_match, DeclarationType.DATE_OF_MANUFACTURE, mfd_match.group(1))

        # 2. Date of Packing
        pkd_match = PKD_PREFIX_REGEX.search(text)
        if pkd_match:
            _process_date_anchor(pkd_match, DeclarationType.DATE_OF_PACKING, pkd_match.group(1))

        # 3. Date of Import
        imp_match = IMP_DATE_PREFIX_REGEX.search(text)
        if imp_match:
            _process_date_anchor(imp_match, DeclarationType.DATE_OF_IMPORT, imp_match.group(1))

        # 4. Best Before (including relative e.g. "9 Months from Mfg")
        bb_match = BEST_BEFORE_PREFIX_REGEX.search(text) or RELATIVE_DATE_REGEX.search(text)
        if bb_match:
            raw_val = bb_match.group(1) if bb_match.lastindex else text
            _process_date_anchor(bb_match, DeclarationType.BEST_BEFORE, raw_val)

        # 5. Expiry Date
        exp_match = EXPIRY_PREFIX_REGEX.search(text)
        if exp_match:
            _process_date_anchor(exp_match, DeclarationType.EXPIRY_DATE, exp_match.group(1))

        return results

    def _extract_organizations(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> List[ExtractedCandidate]:
        results: List[ExtractedCandidate] = []

        def _make_org_candidates(
            prefix_match: Any,
            name_type: DeclarationType,
            addr_type: DeclarationType,
            role: str,
        ) -> List[ExtractedCandidate]:
            # Instead of relying on group(1) which stops at the first newline, strip the prefix explicitly.
            # We match the prefix portion up to the optional colon/dash, then take the rest of `text`.
            # prefix_match.re is the compiled regex
            pattern = prefix_match.re.pattern
            # remove the trailing \s*(.*) to just match the prefix
            clean_pattern = pattern.replace(r"\s*(.*)", "").replace(r"(.*)", "")
            # use re.sub to remove just the prefix from the beginning of text
            raw_content = re.sub(r"^" + clean_pattern, "", text, flags=re.IGNORECASE).strip()
            if not raw_content:
                # The text was purely the prefix itself without any actual name attached in this span.
                return []
            
            # Truncate at obvious next-section boundary (another label keyword)
            raw_content = re.split(r"\n{2,}", raw_content)[0].strip()
            normalized = normalize_organization_address(raw_content, role)
            validity = 1.0 if normalized.get("_valid") else 0.55
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("name") else 0.65,
                spatial_score=1.0 if not span.is_multi_line else 0.92,
                value_validity_score=validity,
            )
            local: List[ExtractedCandidate] = []
            local.append(ExtractedCandidate(
                declaration_type=name_type,
                raw_text=text,
                raw_value=normalized.get("name"),
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            ))
            if normalized.get("address") and normalized.get("address") != normalized.get("name"):
                local.append(ExtractedCandidate(
                    declaration_type=addr_type,
                    raw_text=text,
                    raw_value=normalized.get("address"),
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=span.blocks,
                ))
            return local

        # 1. Manufacturer
        mfd_match = MANUFACTURER_PREFIX_REGEX.search(text)
        if mfd_match:
            results.extend(_make_org_candidates(
                mfd_match, DeclarationType.MANUFACTURER_NAME, DeclarationType.MANUFACTURER_ADDRESS, "MANUFACTURER"
            ))

        # 2. Packer
        pkd_match = PACKER_PREFIX_REGEX.search(text)
        if pkd_match:
            results.extend(_make_org_candidates(
                pkd_match, DeclarationType.PACKER_NAME, DeclarationType.PACKER_ADDRESS, "PACKER"
            ))

        # 3. Importer
        imp_match = IMPORTER_PREFIX_REGEX.search(text)
        if imp_match:
            results.extend(_make_org_candidates(
                imp_match, DeclarationType.IMPORTER_NAME, DeclarationType.IMPORTER_ADDRESS, "IMPORTER"
            ))

        # 4. Marketed-By / Distributed-By → maps to MARKETER_NAME
        mktd_match = MARKETED_PREFIX_REGEX.search(text)
        if mktd_match:
            results.extend(_make_org_candidates(
                mktd_match, DeclarationType.MARKETER_NAME, DeclarationType.MARKETER_ADDRESS, "MARKETER"
            ))

        return results

    def _extract_consumer_care(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> List[ExtractedCandidate]:
        results: List[ExtractedCandidate] = []
        is_care_header = bool(CONSUMER_CARE_HEADER_REGEX.search(text))
        has_contact_prefix = bool(PHONE_CONTACT_PREFIX_REGEX.search(text))
        has_licence_indicator = bool(LICENCE_OR_ID_REGEX.search(text))
        has_fssai = bool(FSSAI_NUMBER_PATTERN.search(text))

        # 1. Phone Extraction — reject FSSAI / Lic No / non-contact identifiers
        if not has_licence_indicator and not has_fssai:
            phone_match = PHONE_REGEX.search(text)
            if phone_match:
                raw_phone = phone_match.group(0)
                is_toll_free = "1800" in raw_phone or "1-800" in raw_phone
                if is_care_header or has_contact_prefix or is_toll_free:
                    normalized = normalize_phone(raw_phone)
                    if normalized.get("is_valid") and normalized.get("number") is not None:
                        validity = 1.0 if normalized.get("is_valid") else 0.3
                        conf_score, conf_level, breakdown = calculate_extraction_confidence(
                            ocr_confidence=ocr_conf,
                            has_explicit_label=is_care_header or has_contact_prefix or is_toll_free,
                            pattern_score=1.0 if len(normalized.get("digits", "")) >= 10 else 0.72,
                            spatial_score=1.0,
                            value_validity_score=validity,
                        )
                        results.append(ExtractedCandidate(
                            declaration_type=DeclarationType.CONSUMER_CARE_PHONE,
                            raw_text=text,
                            raw_value=raw_phone.strip(),
                            normalized_value=normalized,
                            confidence=conf_score,
                            confidence_level=conf_level,
                            confidence_breakdown=breakdown,
                            scan_image_id=image_id,
                            image_type=image_type,
                            blocks=span.blocks,
                        ))

        # 2. Email Extraction
        email_match = EMAIL_REGEX.search(text)
        if email_match:
            raw_email = email_match.group(1)
            normalized = normalize_email(raw_email)
            validity = 1.0 if normalized.get("_valid") else 0.5
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=is_care_header or "@" in text,
                pattern_score=1.0 if "@" in normalized.get("email", "") else 0.65,
                spatial_score=1.0,
                value_validity_score=validity,
            )
            results.append(ExtractedCandidate(
                declaration_type=DeclarationType.CONSUMER_CARE_EMAIL,
                raw_text=text,
                raw_value=raw_email.strip(),
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            ))

        # 3. Address under consumer care header (if multi-line)
        if is_care_header and span.is_multi_line and not PHONE_REGEX.search(text) and not email_match:
            normalized = {"address": text.strip(), "raw": text.strip()}
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=0.82,
                spatial_score=0.88,
                value_validity_score=0.85,
            )
            results.append(ExtractedCandidate(
                declaration_type=DeclarationType.CONSUMER_CARE_ADDRESS,
                raw_text=text,
                raw_value=text.strip(),
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            ))

        return results

    def _extract_batch_number(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> Optional[ExtractedCandidate]:

        def _evaluate_batch_candidate(
            match_text: str, anchor_text: str, search_blocks: List[Any], 
            is_spatial: bool = False
        ) -> Optional[ExtractedCandidate]:
            normalized = normalize_batch_number(match_text)
            
            # If an explicit rejection or instruction was found, we don't proceed
            if normalized.get("is_instruction_only"):
                 return None
                 
            # Reject if it's clearly nutrition, weight, ID/Licence, multipack, or an address
            if is_nutrition_context(match_text) or is_weight_or_measure_context(match_text):
                return None
            if LICENCE_OR_ID_REGEX.search(match_text) or NET_QTY_MULTIPACK_REGEX.search(match_text):
                return None
            from app.services.declaration_extraction.patterns import has_address_indicator
            if has_address_indicator(match_text):
                return None
                 
            if normalized.get("batch_number") is not None:
                validity = 1.0 if normalized.get("_valid") else 0.5
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0,
                    spatial_score=0.9 if is_spatial else 1.0,
                    value_validity_score=validity,
                )
                if is_spatial:
                    breakdown["spatial_relation"] = "nearby_block"
                return ExtractedCandidate(
                    declaration_type=DeclarationType.BATCH_OR_LOT_NUMBER,
                    raw_text=match_text if is_spatial else text,
                    raw_value=normalized.get("batch_number"),
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=search_blocks,
                )
            
            if not is_spatial and not normalized.get("batch_number"):
                return None
                
            return None

        match = BATCH_REGEX.search(text)
        if match:
            # 1. Check local text
            cand = _evaluate_batch_candidate(match.group(1), match.group(0), span.blocks, False)
            if cand and cand.confidence > 0.0:
                return cand
                
            # 2. Check spatial neighborhood
            if all_blocks:
                nearby = find_neighborhood_blocks(span, all_blocks, max_horizontal_gap=300.0, max_vertical_gap=150.0)
                for nb in nearby:
                    nb_text = getattr(nb, "text", "")
                    # Ensure it's not stealing another anchor
                    if (
                        BATCH_REGEX.search(nb_text) 
                        or LICENCE_OR_ID_REGEX.search(nb_text) 
                        or PHONE_CONTACT_PREFIX_REGEX.search(nb_text)
                        or EMAIL_REGEX.search(nb_text)
                        or is_nutrition_context(nb_text)
                        or MFD_PREFIX_REGEX.search(nb_text)
                        or PKD_PREFIX_REGEX.search(nb_text)
                        or EXPIRY_PREFIX_REGEX.search(nb_text)
                        or BEST_BEFORE_PREFIX_REGEX.search(nb_text)
                    ):
                        continue
                    nb_cand = _evaluate_batch_candidate(nb_text, match.group(0), span.blocks + [nb], True)
                    if nb_cand and nb_cand.confidence > 0.0:
                        return nb_cand
                        
            return cand
            
        return None

    def _extract_commodity_name(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float, all_blocks: List[Any]
    ) -> Optional[ExtractedCandidate]:
        match = COMMODITY_PREFIX_REGEX.search(text)
        if match:
            raw_val = match.group(1)
            normalized = normalize_commodity_name(raw_val)
            if normalized.get("commodity_name") is None or not normalized.get("is_valid", True):
                return None

            validity = 1.0 if normalized.get("_valid") else 0.5
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=0.88,
                spatial_score=1.0,
                value_validity_score=validity,
            )
            return ExtractedCandidate(
                declaration_type=DeclarationType.COMMODITY_NAME,
                raw_text=text,
                raw_value=normalized.get("commodity_name"),
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )
        return None

    # ------------------------------------------------------------------
    # Multi-image consolidation
    # ------------------------------------------------------------------

    def extract_and_consolidate_scan(
        self,
        images_with_blocks: List[Dict[str, Any]],
    ) -> List[ExtractedCandidate]:
        """
        Run declaration extraction across all scan images and consolidate candidates.
        Performs multi-image deduplication and conflict detection without arbitrarily discarding evidence.
        """
        all_candidates: List[ExtractedCandidate] = []

        for item in images_with_blocks:
            image_id = item["image_id"]
            image_type = item.get("image_type", "FRONT")
            blocks = item.get("blocks", [])

            image_candidates = self.extract_from_image_blocks(
                scan_image_id=image_id,
                image_type=image_type,
                blocks=blocks,
            )
            all_candidates.extend(image_candidates)

        return self._consolidate_candidates(all_candidates)

    def _consolidate_candidates(
        self, candidates: List[ExtractedCandidate]
    ) -> List[ExtractedCandidate]:
        """
        Group candidates by declaration type.

        Hardened deduplication logic:
        1. Candidates with the same canonical normalized signature (same value) are MERGED,
           not flagged as conflicts. Merged candidate gets:
           - Highest confidence of the group.
           - cross_panel_corroborated = True if from ≥2 distinct image panels.
           - Union of all OCR blocks.
        2. Genuine Conflict Detection: only trigger when two or more candidates have
           DIFFERENT canonical signatures AND both have confidence ≥ 0.70.
        3. Weak low-confidence candidates are pruned when a strong one (≥0.80) exists.
        """
        if not candidates:
            return []

        grouped_by_type: Dict[DeclarationType, List[ExtractedCandidate]] = {}
        for c in candidates:
            grouped_by_type.setdefault(c.declaration_type, []).append(c)

        consolidated: List[ExtractedCandidate] = []

        for dtype, c_list in grouped_by_type.items():
            # Sort candidates by confidence descending
            c_list.sort(key=lambda x: x.confidence, reverse=True)

            # --- Phase 1: Merge candidates with identical normalized signatures ---
            unique_candidates: List[ExtractedCandidate] = []
            for cand in c_list:
                sig = self._get_normalized_signature(dtype, cand.normalized_value)
                matched_existing = False
                for u in unique_candidates:
                    u_sig = self._get_normalized_signature(dtype, u.normalized_value)
                    if sig is not None and sig == u_sig:
                        # MERGE: same value from possibly different panels
                        for b in cand.blocks:
                            if b not in u.blocks:
                                u.blocks.append(b)
                        # Upgrade confidence if this candidate is higher
                        if cand.confidence > u.confidence:
                            u.confidence = cand.confidence
                            u.confidence_level = cand.confidence_level
                            u.confidence_breakdown = cand.confidence_breakdown

                        # Track cross-panel corroboration
                        if cand.scan_image_id and cand.scan_image_id != u.scan_image_id:
                            # Mark corroboration on the surviving candidate
                            u.confidence_breakdown["cross_panel_corroborated"] = True
                            # Boost confidence slightly for corroborated values
                            boosted = min(1.0, u.confidence + 0.04)
                            u.confidence = round(boosted, 4)
                            if boosted >= 0.82:
                                u.confidence_level = ConfidenceLevel.HIGH
                            elif boosted >= 0.58:
                                u.confidence_level = ConfidenceLevel.MEDIUM

                        matched_existing = True
                        break
                if not matched_existing:
                    unique_candidates.append(cand)

            # --- Phase 2: Prune unanchored standalone if anchored candidates exist ---
            has_anchored = any(
                c.confidence_breakdown.get("has_explicit_label")
                or c.normalized_value.get("is_multipack")
                for c in unique_candidates
            )
            if has_anchored:
                unique_candidates = [
                    c
                    for c in unique_candidates
                    if c.confidence_breakdown.get("has_explicit_label")
                    or c.normalized_value.get("is_multipack")
                ]

            # --- Phase 3: Filter out weak candidates when a strong one exists ---
            if unique_candidates:
                top_cand = unique_candidates[0]
                if top_cand.confidence >= 0.80:
                    filtered = [c for c in unique_candidates if c.confidence >= 0.58 or c == top_cand]
                else:
                    filtered = unique_candidates
            else:
                filtered = []

            # --- Phase 4: Genuine conflict detection among credible distinct candidates ---
            credible_candidates = [c for c in filtered if c.confidence >= 0.70]
            if len(credible_candidates) > 1:
                # These are genuinely different values that are both credible → true conflict
                conflict_values = [
                    {
                        "image_id": u.scan_image_id,
                        "image_type": u.image_type,
                        "raw_text": u.raw_text,
                        "normalized": u.normalized_value,
                        "confidence": u.confidence,
                    }
                    for u in credible_candidates
                ]
                for c in credible_candidates:
                    c.has_conflict = True
                    # Downgrade HIGH → MEDIUM when conflicted
                    if c.confidence_level == ConfidenceLevel.HIGH:
                        c.confidence_level = ConfidenceLevel.MEDIUM
                    c.conflict_details = {
                        "conflict_type": "MULTIPLE_DISCREPANT_VALUES_ACROSS_PANELS",
                        "message": (
                            f"Conflicting declarations found across image panels for {dtype.value}. "
                            "Please confirm the correct value."
                        ),
                        "candidate_values": conflict_values,
                    }
                consolidated.extend(credible_candidates)
            elif filtered:
                # No conflict: return only the single best candidate (deduplicated)
                consolidated.append(filtered[0])

        return consolidated

    def _get_normalized_signature(
        self, dtype: DeclarationType, normalized: Dict[str, Any]
    ) -> Optional[str]:
        """Extract a canonical hashable signature from normalized value for deduplication.

        Two candidates with the same signature represent the same information on different
        image panels and should be MERGED, not flagged as conflicts.
        """
        if not normalized:
            return None
        if dtype == DeclarationType.MRP:
            return f"MRP_{normalized.get('amount')}"
        elif dtype == DeclarationType.NET_QUANTITY:
            return (
                f"NETQTY_{normalized.get('canonical_value') or normalized.get('value')}"
                f"_{normalized.get('canonical_unit') or normalized.get('unit')}"
            )
        elif dtype in [
            DeclarationType.DATE_OF_MANUFACTURE,
            DeclarationType.DATE_OF_PACKING,
            DeclarationType.DATE_OF_IMPORT,
            DeclarationType.BEST_BEFORE,
            DeclarationType.EXPIRY_DATE,
        ]:
            # For relative dates, use the relative_text as key
            return f"DATE_{normalized.get('date') or normalized.get('relative_text')}"
        elif dtype == DeclarationType.COUNTRY_OF_ORIGIN:
            return f"COUNTRY_{normalized.get('country')}"
        elif dtype == DeclarationType.CONSUMER_CARE_PHONE:
            # Normalize digits for deduplication (ignore formatting)
            return f"PHONE_{normalized.get('digits') or normalized.get('number')}"
        elif dtype == DeclarationType.CONSUMER_CARE_EMAIL:
            return f"EMAIL_{normalized.get('email', '').lower()}"
        elif dtype == DeclarationType.BATCH_OR_LOT_NUMBER:
            return f"BATCH_{normalized.get('batch_number', '').upper()}"
        elif dtype == DeclarationType.COMMODITY_NAME:
            return f"COMMODITY_{normalized.get('commodity_name', '').upper()}"
        elif dtype in [
            DeclarationType.MANUFACTURER_NAME,
            DeclarationType.PACKER_NAME,
            DeclarationType.IMPORTER_NAME,
        ]:
            name = (normalized.get("name") or "").strip().upper()
            return f"ORG_{name[:40]}"  # Cap at 40 chars to avoid trivial OCR noise diff
        elif dtype in [
            DeclarationType.MANUFACTURER_ADDRESS,
            DeclarationType.PACKER_ADDRESS,
            DeclarationType.IMPORTER_ADDRESS,
        ]:
            # Use PIN code as address dedup key if present, otherwise first 50 chars of address
            pin = normalized.get("pincode")
            if pin:
                return f"ADDR_PIN_{pin}"
            addr = (normalized.get("address") or "").strip().upper()
            return f"ADDR_{addr[:50]}"
        return str(normalized)
