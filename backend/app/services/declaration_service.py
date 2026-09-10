"""Declaration service orchestrating extraction, normalization, database persistence,
evidence linkage, idempotency, review preservation, and audit logging.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ConfidenceLevel, DeclarationType, ReviewStatus, ScanStatus, UserRole, ResolutionStatus
from app.models.declaration import Declaration
from app.models.ocr_block import OCRBlock
from app.models.scan_image import ScanImage
from app.models.scan_session import ScanSession
from app.models.base import get_utc_now
from app.schemas.declaration import (
    DeclarationResponse,
    DeclarationReviewUpdate,
    ScanDeclarationsResponse,
)
from app.services.declaration_extraction.resolver import resolve_declaration
from app.services.audit_service import log_audit_event
from abc import ABC, abstractmethod
from app.services.declaration_extraction import (
    DECLARATION_EXTRACTOR_VERSION,
    DeclarationExtractor,
)
from app.services.declaration_extraction.extractor import ExtractedCandidate
from app.schemas.declaration import DeclarationBase
from app.schemas.ocr import OCRResult


class DeclarationServiceInterface(ABC):
    """Abstract interface for extracting structured legal declarations from OCR blocks."""

    @abstractmethod
    def extract_declarations(self, ocr_result: OCRResult) -> List[DeclarationBase]:
        pass

    @abstractmethod
    def normalize_declaration(
        self, declaration_type: DeclarationType, raw_text: str
    ) -> Dict[str, Any]:
        pass


class MockDeclarationService(DeclarationServiceInterface):
    """Mock declaration extractor and normalizer."""

    def extract_declarations(self, ocr_result: OCRResult) -> List[DeclarationBase]:
        extractor = DeclarationExtractor()
        blocks = ocr_result.blocks if hasattr(ocr_result, "blocks") else []
        candidates = extractor.extract_from_image_blocks(
            scan_image_id=getattr(ocr_result, "scan_image_id", "mock_img"),
            image_type="FRONT",
            blocks=blocks,
        )
        return [
            DeclarationBase(
                declaration_type=c.declaration_type,
                raw_text=c.raw_text,
                normalized_value=c.normalized_value,
                confidence=c.confidence,
                source_blocks=c.source_block_ids,
            )
            for c in candidates
        ]

    def normalize_declaration(
        self, declaration_type: DeclarationType, raw_text: str
    ) -> Dict[str, Any]:
        if declaration_type == DeclarationType.MRP:
            from app.services.declaration_extraction.normalizers import normalize_mrp
            return normalize_mrp(raw_text)
        elif declaration_type == DeclarationType.NET_QUANTITY:
            from app.services.declaration_extraction.normalizers import normalize_net_quantity
            return normalize_net_quantity(raw_text, "g")
        return {"raw": raw_text}



def _to_declaration_response(d: Declaration) -> DeclarationResponse:
    """Helper to convert Declaration ORM object to API response schema."""
    source_block_ids = [b.id for b in d.ocr_blocks] if d.ocr_blocks else []
    if d.source_ocr_block_id and d.source_ocr_block_id not in source_block_ids:
        source_block_ids.append(d.source_ocr_block_id)

    evidence_url = None
    if d.image_id:
        evidence_url = f"/api/v1/scans/{d.scan_session_id}/images/{d.image_id}/content"

    return DeclarationResponse(
        id=d.id,
        scan_session_id=d.scan_session_id,
        image_id=d.image_id,
        declaration_type=d.declaration_type,
        raw_text=d.raw_text,
        raw_value=d.raw_value,
        normalized_value=d.normalized_value,
        confidence=d.confidence,
        confidence_level=d.confidence_level,
        resolution_status=d.resolution_status,
        resolution_reason=d.resolution_reason,
        canonical_value=d.canonical_value,
        candidate_details=d.candidate_details,
        machine_extracted_value=d.machine_extracted_value,
        reviewed=d.reviewed,
        reviewed_value=d.reviewed_value,
        reviewed_by=d.reviewed_by,
        reviewed_at=d.reviewed_at,
        extractor_version=d.extractor_version,
        bounding_box=d.bounding_box,
        confidence_breakdown=d.confidence_breakdown,
        has_conflict=d.has_conflict,
        conflict_details=d.conflict_details,
        source_ocr_block_id=d.source_ocr_block_id,
        source_blocks=source_block_ids,
        evidence_preview_url=evidence_url,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


class DeclarationService:
    """Service handling declaration extraction and reviewer verification."""

    def __init__(self, extractor: Optional[DeclarationExtractor] = None):
        self.extractor = extractor or DeclarationExtractor()

    def extract_declarations_for_scan(
        self,
        db: Session,
        scan_id: str,
        user_id: str,
        user_role: UserRole,
    ) -> ScanDeclarationsResponse:
        """
        Execute deterministic declaration extraction on all persisted OCR blocks of a scan session.
        Guarantees idempotency and preserves previously saved human reviews.
        """
        start_time = time.time()

        # 1. Fetch scan session
        scan = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
        if not scan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan session '{scan_id}' not found.",
            )

        # IDOR protection
        if user_role == UserRole.INSPECTOR and scan.inspector_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: you do not have permission to extract declarations for this scan.",
            )

        # 2. Fetch images and OCR blocks with single roundtrip
        images = (
            db.query(ScanImage)
            .options(joinedload(ScanImage.ocr_blocks))
            .filter(ScanImage.scan_session_id == scan_id)
            .order_by(ScanImage.display_order.asc())
            .all()
        )

        if not images:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scan session contains no uploaded images.",
            )

        total_ocr_blocks = sum(len(img.ocr_blocks) for img in images)
        if total_ocr_blocks == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OCR blocks found for this scan session. Please run image OCR processing first.",
            )

        # 3. Structure inputs for extractor
        images_with_blocks = [
            {
                "image_id": img.id,
                "image_type": img.image_type.value if hasattr(img.image_type, "value") else str(img.image_type),
                "blocks": img.ocr_blocks,
            }
            for img in images
        ]

        # 4. Run deterministic extraction
        candidates = self.extractor.extract_and_consolidate_scan(images_with_blocks)

        # 5. Idempotent persistence with Human-Review Preservation
        existing_declarations = (
            db.query(Declaration)
            .options(joinedload(Declaration.ocr_blocks))
            .filter(Declaration.scan_session_id == scan_id)
            .all()
        )

        # Map reviewed declarations by declaration_type
        reviewed_map: Dict[DeclarationType, Declaration] = {
            d.declaration_type: d
            for d in existing_declarations
            if d.reviewed or d.resolution_status in [ResolutionStatus.CONFIRMED, ResolutionStatus.REJECTED]
        }

        # Delete only unreviewed existing declarations to avoid duplicate noise
        for old_decl in existing_declarations:
            if not old_decl.reviewed and old_decl.resolution_status not in [ResolutionStatus.CONFIRMED, ResolutionStatus.REJECTED]:
                db.delete(old_decl)
        db.flush()

        persisted_declarations: List[Declaration] = []

        # Group candidates by type
        from collections import defaultdict
        grouped_candidates = defaultdict(list)
        for cand in candidates:
            grouped_candidates[cand.declaration_type].append(cand)
            

        
        # We need to process all recognized declaration types
        all_types = list(DeclarationType)
        
        for dtype in all_types:
            if dtype in [DeclarationType.UNKNOWN, DeclarationType.OTHER]:
                continue
                
            type_cands = grouped_candidates.get(dtype, [])
            resolved = resolve_declaration(dtype, type_cands)
            
            # Check if this type already has a human review
            existing_reviewed = reviewed_map.get(dtype)

            if existing_reviewed:
                # Update machine snapshot and evidence while keeping human review intact!
                # We update the machine output with the new canonical result
                if type_cands:
                    best_cand = max(type_cands, key=lambda c: c.confidence)
                    existing_reviewed.raw_text = best_cand.raw_text
                    existing_reviewed.raw_value = best_cand.raw_value
                    existing_reviewed.image_id = best_cand.scan_image_id
                    existing_reviewed.bounding_box = best_cand.union_bounding_box
                    existing_reviewed.has_conflict = best_cand.has_conflict
                    existing_reviewed.conflict_details = best_cand.conflict_details
                    existing_reviewed.ocr_blocks = best_cand.blocks
                    if best_cand.blocks:
                        existing_reviewed.source_ocr_block_id = best_cand.blocks[0].id
                else:
                    existing_reviewed.raw_text = ""
                    existing_reviewed.raw_value = ""
                    existing_reviewed.image_id = None
                    existing_reviewed.bounding_box = None
                    existing_reviewed.has_conflict = False
                    existing_reviewed.conflict_details = None
                    existing_reviewed.ocr_blocks = []
                    existing_reviewed.source_ocr_block_id = None
                
                existing_reviewed.machine_extracted_value = resolved.get("canonical_value")
                existing_reviewed.confidence = resolved.get("confidence", 0.0)
                existing_reviewed.confidence_level = resolved.get("confidence_level", ConfidenceLevel.LOW)
                # DO NOT overwrite resolution_status for already reviewed items
                existing_reviewed.resolution_reason = "Machine extraction updated; human review preserved."
                existing_reviewed.canonical_value = existing_reviewed.reviewed_value or resolved.get("canonical_value")
                existing_reviewed.candidate_details = resolved.get("candidate_details")
                existing_reviewed.extractor_version = self.extractor.version
                existing_reviewed.updated_at = get_utc_now()
                
                persisted_declarations.append(existing_reviewed)
            else:
                # Create new machine extracted declaration
                if resolved.get("resolution_status") == ResolutionStatus.NOT_DETECTED:
                    continue # Do not create rows for entirely missing fields initially, only if we want
                    
                best_cand = None
                if type_cands:
                    best_cand = max(type_cands, key=lambda c: c.confidence)
                
                first_block_id = best_cand.blocks[0].id if best_cand and best_cand.blocks else None
                new_decl = Declaration(
                    scan_session_id=scan_id,
                    image_id=best_cand.scan_image_id if best_cand else None,
                    declaration_type=dtype,
                    raw_text=best_cand.raw_text if best_cand else "",
                    raw_value=best_cand.raw_value if best_cand else "",
                    normalized_value=resolved.get("canonical_value"),
                    confidence=resolved.get("confidence", 0.0),
                    confidence_level=resolved.get("confidence_level", ConfidenceLevel.LOW),
                    resolution_status=resolved.get("resolution_status"),
                    resolution_reason=resolved.get("resolution_reason"),
                    canonical_value=resolved.get("canonical_value"),
                    candidate_details=resolved.get("candidate_details"),
                    machine_extracted_value=resolved.get("canonical_value"),
                    source_ocr_block_id=first_block_id,
                    reviewed=False,
                    reviewed_value=None,
                    extractor_version=self.extractor.version,
                    bounding_box=best_cand.union_bounding_box if best_cand else None,
                    confidence_breakdown=best_cand.confidence_breakdown if best_cand else None,
                    has_conflict=best_cand.has_conflict if best_cand else False,
                    conflict_details=best_cand.conflict_details if best_cand else None,
                    created_at=get_utc_now(),
                    updated_at=get_utc_now(),
                )
                if best_cand:
                    new_decl.ocr_blocks = best_cand.blocks
                db.add(new_decl)
                persisted_declarations.append(new_decl)

        # Update ScanSession status
        if scan.status in [ScanStatus.OCR_COMPLETED, ScanStatus.IMAGES_UPLOADED, ScanStatus.PROCESSING]:
            scan.status = ScanStatus.DECLARATIONS_EXTRACTED
            scan.updated_at = get_utc_now()

        db.commit()

        # Audit logging
        duration_ms = int((time.time() - start_time) * 1000)
        log_audit_event(
            db=db,
            user_id=user_id,
            action="EXTRACT_DECLARATIONS",
            entity_type="ScanSession",
            entity_id=scan_id,
            metadata={
                "declarations_extracted_count": len(persisted_declarations),
                "extractor_version": self.extractor.version,
                "duration_ms": duration_ms,
            },
        )

        return self.get_scan_declarations(
            db=db,
            scan_id=scan_id,
            user_id=user_id,
            user_role=user_role,
            duration_ms=duration_ms,
        )

    def get_scan_declarations(
        self,
        db: Session,
        scan_id: str,
        user_id: str,
        user_role: UserRole,
        duration_ms: Optional[int] = None,
    ) -> ScanDeclarationsResponse:
        """Retrieve all structured declarations and evidence for a scan session."""
        scan = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
        if not scan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan session '{scan_id}' not found.",
            )

        if user_role == UserRole.INSPECTOR and scan.inspector_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: you do not have permission to view declarations for this scan.",
            )

        declarations = (
            db.query(Declaration)
            .options(joinedload(Declaration.ocr_blocks))
            .filter(Declaration.scan_session_id == scan_id)
            .order_by(Declaration.created_at.asc())
            .all()
        )

        responses = [_to_declaration_response(d) for d in declarations]

        unreviewed = sum(1 for d in declarations if d.resolution_status in [ResolutionStatus.NEEDS_REVIEW, ResolutionStatus.CONFLICT])
        confirmed = sum(1 for d in declarations if d.resolution_status == ResolutionStatus.CONFIRMED)
        corrected = 0 # Not applicable
        rejected = sum(1 for d in declarations if d.resolution_status == ResolutionStatus.REJECTED)

        return ScanDeclarationsResponse(
            scan_id=scan_id,
            total_declarations=len(declarations),
            unreviewed_count=unreviewed,
            confirmed_count=confirmed,
            corrected_count=corrected,
            rejected_count=rejected,
            declarations=responses,
            extractor_version=self.extractor.version,
            extraction_duration_ms=duration_ms,
        )

    def review_declaration(
        self,
        db: Session,
        declaration_id: str,
        review_in: DeclarationReviewUpdate,
        user_id: str,
        user_role: UserRole,
    ) -> DeclarationResponse:
        """
        Review, confirm, correct, or reject an extracted declaration.
        Never overwrites machine_extracted_value. Audits all human review actions.
        """
        decl = (
            db.query(Declaration)
            .options(joinedload(Declaration.ocr_blocks))
            .filter(Declaration.id == declaration_id)
            .first()
        )
        if not decl:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Declaration '{declaration_id}' not found.",
            )

        previous_status = decl.resolution_status.value if hasattr(decl.resolution_status, "value") else str(decl.resolution_status)

        # Map frontend review actions back to resolution status
        if review_in.review_status == ReviewStatus.CONFIRMED:
            decl.resolution_status = ResolutionStatus.CONFIRMED
            decl.reviewed_value = decl.machine_extracted_value or decl.canonical_value
        elif review_in.review_status == ReviewStatus.CORRECTED:
            if not review_in.reviewed_value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Corrected review requires a non-empty reviewed_value.",
                )
            decl.resolution_status = ResolutionStatus.CONFIRMED
            decl.reviewed_value = review_in.reviewed_value
            decl.canonical_value = review_in.reviewed_value
            decl.normalized_value = review_in.reviewed_value
        elif review_in.review_status == ReviewStatus.REJECTED:
            decl.resolution_status = ResolutionStatus.REJECTED
            decl.reviewed_value = None

        decl.reviewed = True
        decl.reviewed_by = user_id
        decl.reviewed_at = get_utc_now()
        decl.updated_at = get_utc_now()

        db.commit()

        # Audit logging
        log_audit_event(
            db=db,
            user_id=user_id,
            action=f"DECLARATION_{review_in.review_status.value}",
            entity_type="Declaration",
            entity_id=declaration_id,
            metadata={
                "scan_session_id": decl.scan_session_id,
                "declaration_type": decl.declaration_type.value if hasattr(decl.declaration_type, "value") else str(decl.declaration_type),
                "previous_status": previous_status,
                "new_status": review_in.review_status.value if hasattr(review_in.review_status, "value") else str(review_in.review_status),
                "reviewed_value": review_in.reviewed_value,
                "notes": review_in.review_notes,
            },
        )

        return _to_declaration_response(decl)


_declaration_service_instance: Optional[DeclarationService] = None


def get_declaration_service() -> DeclarationService:
    """Dependency provider for DeclarationService."""
    global _declaration_service_instance
    if _declaration_service_instance is None:
        _declaration_service_instance = DeclarationService()
    return _declaration_service_instance
