"""Core Declaration Extraction Engine for LegalMetrix AI.

Performs context-aware, deterministic multi-block extraction, normalization,
evidence linkage, composite confidence scoring, and genuine conflict detection.
"""
import re
from typing import Any, Dict, List, Optional, Tuple, Set
from app.core.enums import ConfidenceLevel, DeclarationType, ReviewStatus
from app.services.declaration_extraction.confidence import calculate_extraction_confidence
from app.services.declaration_extraction.evidence import (
    build_evidence_payload,
    compute_average_ocr_confidence,
    compute_union_bounding_box,
)
from app.services.declaration_extraction.grouping import TextSpan, generate_candidate_text_spans
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

        # Spatial expansion: blocks that overlap with nutrition vertical ranges and contain numbers/units
        if nutrition_y_ranges:
            for b in blocks:
                b_id = getattr(b, "id", "")
                if b_id in nutrition_block_ids:
                    continue
                y1 = getattr(b, "bbox_y1", 0)
                y2 = getattr(b, "bbox_y2", 0)
                # Check if block falls within any nutrition line's vertical bounds
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
                mrp_cand = self._extract_mrp(text, span, scan_image_id, image_type, avg_ocr_conf)
                if mrp_cand:
                    candidates.append(mrp_cand)

            # 2. Net Quantity Extraction (Strictly excluded from nutrition context)
            if not span_is_nutrition:
                net_qty_cand = self._extract_net_quantity(text, span, scan_image_id, image_type, avg_ocr_conf)
                if net_qty_cand:
                    candidates.append(net_qty_cand)

            # 3. Country of Origin Extraction
            country_cand = self._extract_country_of_origin(text, span, scan_image_id, image_type, avg_ocr_conf)
            if country_cand:
                candidates.append(country_cand)

            # 4. Dates Extraction
            date_cands = self._extract_dates(text, span, scan_image_id, image_type, avg_ocr_conf)
            candidates.extend(date_cands)

            # 5. Manufacturer / Packer / Importer
            org_cands = self._extract_organizations(text, span, scan_image_id, image_type, avg_ocr_conf)
            candidates.extend(org_cands)

            # 6. Consumer Care (Phone, Email, Address)
            care_cands = self._extract_consumer_care(text, span, scan_image_id, image_type, avg_ocr_conf)
            candidates.extend(care_cands)

            # 7. Batch / Lot Number
            batch_cand = self._extract_batch_number(text, span, scan_image_id, image_type, avg_ocr_conf)
            if batch_cand:
                candidates.append(batch_cand)

            # 8. Commodity Name
            comm_cand = self._extract_commodity_name(text, span, scan_image_id, image_type, avg_ocr_conf)
            if comm_cand:
                candidates.append(comm_cand)

        return candidates

    def _extract_mrp(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> Optional[ExtractedCandidate]:
        if is_nutrition_context(text):
            return None

        # 1. Explicit MRP Anchor match (e.g. MRP Rs 120, M.R.P. ₹ 99.00, MRPE 20.00)
        explicit_match = MRP_EXPLICIT_REGEX.search(text)
        if explicit_match:
            raw_amt = explicit_match.group(1)
            has_taxes = bool(INCL_TAXES_REGEX.search(text))
            normalized = normalize_mrp(raw_amt, has_taxes_incl=has_taxes)
            if normalized.get("amount") is None:
                return None

            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("amount") is not None else 0.7,
                spatial_score=1.0 if not span.is_multi_line else 0.9,
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
            # Ensure not part of date or weight
            if "/" in text or "g" in text.lower():
                return None
            raw_amt = amt_match.group(1)
            has_taxes = bool(INCL_TAXES_REGEX.search(text))
            normalized = normalize_mrp(raw_amt, has_taxes_incl=has_taxes)
            if normalized.get("amount") is None:
                return None

            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=False,
                pattern_score=0.75,
                spatial_score=1.0,
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
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> Optional[ExtractedCandidate]:
        if is_nutrition_context(text):
            return None

        # 1. Multi-pack compound expressions (e.g. "10 N x 82.7 g = 827 g")
        mp_match = NET_QTY_MULTIPACK_REGEX.search(text)
        if mp_match:
            normalized = normalize_net_quantity(text)
            if normalized.get("value") is not None:
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0,
                    spatial_score=1.0 if not span.is_multi_line else 0.95,
                )
                return ExtractedCandidate(
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
                )

        # 2. Explicit Net Quantity Anchor match (e.g. "NET WEIGHT 827 g", "Net Qty: 500 g")
        explicit_match = NET_QTY_EXPLICIT_REGEX.search(text)
        if explicit_match:
            raw_val = explicit_match.group(1)
            raw_unit = explicit_match.group(2) if len(explicit_match.groups()) >= 2 else None
            normalized = normalize_net_quantity(raw_val, raw_unit)
            has_unit = normalized.get("unit") is not None
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if has_unit else 0.5,
                spatial_score=1.0 if not span.is_multi_line else 0.9,
            )
            final_conf_level = conf_level
            if not has_unit and final_conf_level == ConfidenceLevel.HIGH:
                final_conf_level = ConfidenceLevel.MEDIUM

            raw_val_str = f"{raw_val} {raw_unit}".strip() if raw_unit else raw_val
            return ExtractedCandidate(
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
            )

        # 3. Standalone quantity (e.g. "827 g", "500 g", "1 kg") only if outside nutrition context
        standalone_match = NET_QTY_STANDALONE_REGEX.search(text)
        if standalone_match and len(span.blocks) <= 2:
            raw_val = standalone_match.group(1)
            raw_unit = standalone_match.group(2)
            # Standalone mg is almost exclusively a micronutrient (Sodium, Calcium, etc.)
            if raw_unit and raw_unit.lower() == "mg":
                return None
            if is_nutrition_context(text):
                return None
            normalized = normalize_net_quantity(raw_val, raw_unit)
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=False,
                pattern_score=0.70,
                spatial_score=1.0,
            )
            raw_val_str = f"{raw_val} {raw_unit}".strip() if raw_unit else raw_val
            return ExtractedCandidate(
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
            )
        return None

    def _extract_country_of_origin(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> Optional[ExtractedCandidate]:
        match = COUNTRY_ORIGIN_REGEX.search(text)
        if match:
            raw_country = match.group(1)
            normalized = normalize_country(raw_country)
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("is_recognized") else 0.75,
                spatial_score=1.0,
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

    def _extract_dates(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> List[ExtractedCandidate]:
        results: List[ExtractedCandidate] = []

        # 1. Date of Manufacture
        mfd_match = MFD_PREFIX_REGEX.search(text)
        if mfd_match:
            raw_date = mfd_match.group(1)
            normalized = normalize_date(raw_date, "DATE_OF_MANUFACTURE")
            if normalized.get("date") is not None or normalized.get("is_relative") is True:
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0 if normalized.get("date") or normalized.get("is_relative") else 0.7,
                    spatial_score=1.0,
                )
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.DATE_OF_MANUFACTURE,
                        raw_text=text,
                        raw_value=raw_date.strip(),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        # 2. Date of Packing
        pkd_match = PKD_PREFIX_REGEX.search(text)
        if pkd_match:
            raw_date = pkd_match.group(1)
            normalized = normalize_date(raw_date, "DATE_OF_PACKING")
            if normalized.get("date") is not None or normalized.get("is_relative") is True:
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0 if normalized.get("date") or normalized.get("is_relative") else 0.7,
                    spatial_score=1.0,
                )
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.DATE_OF_PACKING,
                        raw_text=text,
                        raw_value=raw_date.strip(),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        # 3. Date of Import
        imp_match = IMP_DATE_PREFIX_REGEX.search(text)
        if imp_match:
            raw_date = imp_match.group(1)
            normalized = normalize_date(raw_date, "DATE_OF_IMPORT")
            if normalized.get("date") is not None or normalized.get("is_relative") is True:
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0 if normalized.get("date") or normalized.get("is_relative") else 0.7,
                    spatial_score=1.0,
                )
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.DATE_OF_IMPORT,
                        raw_text=text,
                        raw_value=raw_date.strip(),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        # 4. Best Before (including relative e.g. "9 Months from Mfg")
        bb_match = BEST_BEFORE_PREFIX_REGEX.search(text) or RELATIVE_DATE_REGEX.search(text)
        if bb_match:
            raw_val = bb_match.group(1) if bb_match.lastindex else text
            normalized = normalize_date(text, "BEST_BEFORE")
            if normalized.get("date") is not None or normalized.get("is_relative") is True:
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0 if normalized.get("date") or normalized.get("is_relative") else 0.7,
                    spatial_score=1.0,
                )
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.BEST_BEFORE,
                        raw_text=text,
                        raw_value=raw_val.strip(),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        # 5. Expiry Date
        exp_match = EXPIRY_PREFIX_REGEX.search(text)
        if exp_match:
            raw_date = exp_match.group(1)
            normalized = normalize_date(raw_date, "EXPIRY_DATE")
            if normalized.get("date") is not None or normalized.get("is_relative") is True:
                conf_score, conf_level, breakdown = calculate_extraction_confidence(
                    ocr_confidence=ocr_conf,
                    has_explicit_label=True,
                    pattern_score=1.0 if normalized.get("date") else 0.7,
                    spatial_score=1.0,
                )
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.EXPIRY_DATE,
                        raw_text=text,
                        raw_value=raw_date.strip(),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        return results

    def _extract_organizations(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> List[ExtractedCandidate]:
        results: List[ExtractedCandidate] = []

        # 1. Manufacturer Name / Address
        mfd_match = MANUFACTURER_PREFIX_REGEX.search(text)
        if mfd_match:
            raw_content = mfd_match.group(1) or text
            normalized = normalize_organization_address(raw_content, "MANUFACTURER")
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("name") else 0.7,
                spatial_score=1.0 if not span.is_multi_line else 0.95,
            )
            results.append(
                ExtractedCandidate(
                    declaration_type=DeclarationType.MANUFACTURER_NAME,
                    raw_text=text,
                    raw_value=normalized.get("name"),
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=span.blocks,
                )
            )
            if normalized.get("address") and normalized.get("address") != normalized.get("name"):
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.MANUFACTURER_ADDRESS,
                        raw_text=text,
                        raw_value=normalized.get("address"),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        # 2. Packer Name / Address
        pkd_match = PACKER_PREFIX_REGEX.search(text)
        if pkd_match:
            raw_content = pkd_match.group(1) or text
            normalized = normalize_organization_address(raw_content, "PACKER")
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("name") else 0.7,
                spatial_score=1.0 if not span.is_multi_line else 0.95,
            )
            results.append(
                ExtractedCandidate(
                    declaration_type=DeclarationType.PACKER_NAME,
                    raw_text=text,
                    raw_value=normalized.get("name"),
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=span.blocks,
                )
            )
            if normalized.get("address") and normalized.get("address") != normalized.get("name"):
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.PACKER_ADDRESS,
                        raw_text=text,
                        raw_value=normalized.get("address"),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        # 3. Importer Name / Address
        imp_match = IMPORTER_PREFIX_REGEX.search(text)
        if imp_match:
            raw_content = imp_match.group(1) or text
            normalized = normalize_organization_address(raw_content, "IMPORTER")
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if normalized.get("name") else 0.7,
                spatial_score=1.0 if not span.is_multi_line else 0.95,
            )
            results.append(
                ExtractedCandidate(
                    declaration_type=DeclarationType.IMPORTER_NAME,
                    raw_text=text,
                    raw_value=normalized.get("name"),
                    normalized_value=normalized,
                    confidence=conf_score,
                    confidence_level=conf_level,
                    confidence_breakdown=breakdown,
                    scan_image_id=image_id,
                    image_type=image_type,
                    blocks=span.blocks,
                )
            )
            if normalized.get("address") and normalized.get("address") != normalized.get("name"):
                results.append(
                    ExtractedCandidate(
                        declaration_type=DeclarationType.IMPORTER_ADDRESS,
                        raw_text=text,
                        raw_value=normalized.get("address"),
                        normalized_value=normalized,
                        confidence=conf_score,
                        confidence_level=conf_level,
                        confidence_breakdown=breakdown,
                        scan_image_id=image_id,
                        image_type=image_type,
                        blocks=span.blocks,
                    )
                )

        return results

    def _extract_consumer_care(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> List[ExtractedCandidate]:
        results: List[ExtractedCandidate] = []
        is_care_header = bool(CONSUMER_CARE_HEADER_REGEX.search(text))
        has_contact_prefix = bool(PHONE_CONTACT_PREFIX_REGEX.search(text))
        has_licence_indicator = bool(LICENCE_OR_ID_REGEX.search(text))

        # 1. Phone Extraction
        # Reject FSSAI / Lic No / non-contact identifiers
        if not has_licence_indicator:
            phone_match = PHONE_REGEX.search(text)
            if phone_match:
                raw_phone = phone_match.group(0)
                # Ensure the match has contact context or is an explicit toll-free 1800 number
                is_toll_free = "1800" in raw_phone or "1-800" in raw_phone
                if is_care_header or has_contact_prefix or is_toll_free:
                    normalized = normalize_phone(raw_phone)
                    if normalized.get("is_valid", True) and normalized.get("number") is not None:
                        conf_score, conf_level, breakdown = calculate_extraction_confidence(
                            ocr_confidence=ocr_conf,
                            has_explicit_label=is_care_header or has_contact_prefix or is_toll_free,
                            pattern_score=1.0 if len(normalized.get("digits", "")) >= 10 else 0.75,
                            spatial_score=1.0,
                        )
                        results.append(
                            ExtractedCandidate(
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
                            )
                        )

        # 2. Email Extraction
        email_match = EMAIL_REGEX.search(text)
        if email_match:
            raw_email = email_match.group(1)
            normalized = normalize_email(raw_email)
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=is_care_header or "@" in text,
                pattern_score=1.0 if "@" in normalized.get("email", "") else 0.7,
                spatial_score=1.0,
            )
            results.append(
                ExtractedCandidate(
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
                )
            )

        # 3. Address under consumer care header (if multi-line)
        if is_care_header and span.is_multi_line and not PHONE_REGEX.search(text) and not email_match:
            normalized = {"address": text.strip(), "raw": text.strip()}
            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=0.85,
                spatial_score=0.9,
            )
            results.append(
                ExtractedCandidate(
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
                )
            )

        return results

    def _extract_batch_number(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> Optional[ExtractedCandidate]:
        match = BATCH_REGEX.search(text)
        if match:
            raw_val = match.group(1)
            normalized = normalize_batch_number(raw_val)
            if normalized.get("batch_number") is None or normalized.get("is_instruction_only"):
                return None

            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=1.0 if len(normalized.get("batch_number", "")) >= 2 else 0.7,
                spatial_score=1.0,
            )
            return ExtractedCandidate(
                declaration_type=DeclarationType.BATCH_OR_LOT_NUMBER,
                raw_text=text,
                raw_value=normalized.get("batch_number"),
                normalized_value=normalized,
                confidence=conf_score,
                confidence_level=conf_level,
                confidence_breakdown=breakdown,
                scan_image_id=image_id,
                image_type=image_type,
                blocks=span.blocks,
            )
        return None

    def _extract_commodity_name(
        self, text: str, span: TextSpan, image_id: str, image_type: str, ocr_conf: float
    ) -> Optional[ExtractedCandidate]:
        match = COMMODITY_PREFIX_REGEX.search(text)
        if match:
            raw_val = match.group(1)
            normalized = normalize_commodity_name(raw_val)
            if normalized.get("commodity_name") is None or not normalized.get("is_valid", True):
                return None

            conf_score, conf_level, breakdown = calculate_extraction_confidence(
                ocr_confidence=ocr_conf,
                has_explicit_label=True,
                pattern_score=0.9,
                spatial_score=1.0,
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
        - Merge exact/normalized duplicates and preserve contributing OCR blocks.
        - Rank candidates deterministically by confidence score.
        - Genuine Conflict Detection: only trigger conflict when two or more distinct candidates
          are BOTH credible/high-confidence (>= 0.70) and contradictory.
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

            # Deduplicate by canonical normalized signature
            unique_candidates: List[ExtractedCandidate] = []
            for cand in c_list:
                sig = self._get_normalized_signature(dtype, cand.normalized_value)
                matched_existing = False
                for u in unique_candidates:
                    u_sig = self._get_normalized_signature(dtype, u.normalized_value)
                    if sig == u_sig and sig is not None:
                        # Merge evidence blocks from duplicate candidate
                        for b in cand.blocks:
                            if b not in u.blocks:
                                u.blocks.append(b)
                        # Keep highest confidence
                        if cand.confidence > u.confidence:
                            u.confidence = cand.confidence
                            u.confidence_level = cand.confidence_level
                            u.confidence_breakdown = cand.confidence_breakdown
                        matched_existing = True
                        break
                if not matched_existing:
                    unique_candidates.append(cand)

            # If explicit label candidates exist, prune unanchored standalone candidates
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

            # Filter out weak candidates if a strong candidate (>= 0.80) exists
            if unique_candidates:
                top_cand = unique_candidates[0]
                if top_cand.confidence >= 0.80:
                    # Filter out candidates with low confidence (< 0.60)
                    filtered = [c for c in unique_candidates if c.confidence >= 0.60 or c == top_cand]
                else:
                    filtered = unique_candidates
            else:
                filtered = []

            # Genuine conflict detection among credible candidates (confidence >= 0.70)
            credible_candidates = [c for c in filtered if c.confidence >= 0.70]
            if len(credible_candidates) > 1:
                # Multiple distinct credible values exist across image panels
                for c in credible_candidates:
                    c.has_conflict = True
                    c.confidence_level = (
                        ConfidenceLevel.MEDIUM
                        if c.confidence_level == ConfidenceLevel.HIGH
                        else c.confidence_level
                    )
                    c.conflict_details = {
                        "conflict_type": "MULTIPLE_DISCREPANT_VALUES_ACROSS_PANELS",
                        "message": f"Conflicting declarations found across image panels for {dtype.value}.",
                        "candidate_values": [
                            {
                                "image_id": u.scan_image_id,
                                "image_type": u.image_type,
                                "raw_text": u.raw_text,
                                "normalized": u.normalized_value,
                                "confidence": u.confidence,
                            }
                            for u in credible_candidates
                        ],
                    }
                consolidated.extend(credible_candidates)
            elif filtered:
                # Return the top candidate or filtered candidates
                consolidated.append(filtered[0])

        return consolidated

    def _get_normalized_signature(
        self, dtype: DeclarationType, normalized: Dict[str, Any]
    ) -> Optional[str]:
        """Extract a canonical hashable signature from normalized value for deduplication."""
        if not normalized:
            return None
        if dtype == DeclarationType.MRP:
            return f"MRP_{normalized.get('amount')}"
        elif dtype == DeclarationType.NET_QUANTITY:
            return f"NETQTY_{normalized.get('canonical_value') or normalized.get('value')}_{normalized.get('canonical_unit') or normalized.get('unit')}"
        elif dtype in [
            DeclarationType.DATE_OF_MANUFACTURE,
            DeclarationType.DATE_OF_PACKING,
            DeclarationType.DATE_OF_IMPORT,
            DeclarationType.BEST_BEFORE,
            DeclarationType.EXPIRY_DATE,
        ]:
            return f"DATE_{normalized.get('date') or normalized.get('relative_text')}"
        elif dtype == DeclarationType.COUNTRY_OF_ORIGIN:
            return f"COUNTRY_{normalized.get('country')}"
        elif dtype == DeclarationType.CONSUMER_CARE_PHONE:
            return f"PHONE_{normalized.get('digits') or normalized.get('number')}"
        elif dtype == DeclarationType.CONSUMER_CARE_EMAIL:
            return f"EMAIL_{normalized.get('email')}"
        elif dtype == DeclarationType.BATCH_OR_LOT_NUMBER:
            return f"BATCH_{normalized.get('batch_number')}"
        elif dtype == DeclarationType.COMMODITY_NAME:
            return f"COMMODITY_{normalized.get('commodity_name')}"
        elif dtype in [
            DeclarationType.MANUFACTURER_NAME,
            DeclarationType.PACKER_NAME,
            DeclarationType.IMPORTER_NAME,
        ]:
            return f"ORG_{normalized.get('name')}"
        elif dtype in [
            DeclarationType.MANUFACTURER_ADDRESS,
            DeclarationType.PACKER_ADDRESS,
            DeclarationType.IMPORTER_ADDRESS,
        ]:
            return f"ADDR_{normalized.get('address')}"
        return str(normalized)
