"""Declaration Extraction and Normalization package — v1.5.0."""
from app.services.declaration_extraction.version import DECLARATION_EXTRACTOR_VERSION
from app.services.declaration_extraction.extractor import DeclarationExtractor, ExtractedCandidate
from app.services.declaration_extraction.normalizers import (
    normalize_mrp,
    normalize_net_quantity,
    normalize_date,
    normalize_country,
    normalize_phone,
    normalize_email,
    normalize_organization_address,
    normalize_batch_number,
    normalize_commodity_name,
)
from app.services.declaration_extraction.confidence import calculate_extraction_confidence
from app.services.declaration_extraction.evidence import (
    compute_union_bounding_box,
    compute_average_ocr_confidence,
    build_evidence_payload,
)
from app.services.declaration_extraction.grouping import (
    TextSpan,
    cluster_blocks_into_lines,
    generate_candidate_text_spans,
)
from app.services.declaration_extraction.evaluator import evaluate_declaration_benchmark
from app.services.declaration_extraction.patterns import (
    is_nutrition_context,
    is_instruction_only,
    is_weight_or_measure_context,
    has_address_indicator,
)

__all__ = [
    "DECLARATION_EXTRACTOR_VERSION",
    "DeclarationExtractor",
    "ExtractedCandidate",
    "normalize_mrp",
    "normalize_net_quantity",
    "normalize_date",
    "normalize_country",
    "normalize_phone",
    "normalize_email",
    "normalize_organization_address",
    "normalize_batch_number",
    "normalize_commodity_name",
    "calculate_extraction_confidence",
    "compute_union_bounding_box",
    "compute_average_ocr_confidence",
    "build_evidence_payload",
    "TextSpan",
    "cluster_blocks_into_lines",
    "generate_candidate_text_spans",
    "evaluate_declaration_benchmark",
    "is_nutrition_context",
    "is_instruction_only",
    "is_weight_or_measure_context",
    "has_address_indicator",
]
