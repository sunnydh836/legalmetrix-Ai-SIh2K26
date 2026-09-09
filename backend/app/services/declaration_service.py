"""Declaration service orchestrating extraction, normalization, database persistence,
evidence linkage, idempotency, review preservation, and audit logging.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ConfidenceLevel, DeclarationType, ReviewStatus, ScanStatus, UserRole
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
from app.services.audit_service import log_audit_event
from abc import ABC, abstractmethod
from app.services.declaration_extraction import (
    DECLARATION_EXTRACTOR_VERSION,
    DeclarationExtractor,
)
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
        review_status=d.review_status,
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
            if d.reviewed or d.review_status != ReviewStatus.UNREVIEWED
        }

        # Delete only unreviewed existing declarations to avoid duplicate noise
        for old_decl in existing_declarations:
            if not old_decl.reviewed and old_decl.review_status == ReviewStatus.UNREVIEWED:
                db.delete(old_decl)
        db.flush()

        persisted_declarations: List[Declaration] = []

        for cand in candidates:
            # Check if this type already has a human review
            existing_reviewed = reviewed_map.get(cand.declaration_type)

            if existing_reviewed:
                # Update machine snapshot and evidence while keeping human review intact!
                existing_reviewed.raw_text = cand.raw_text
                existing_reviewed.raw_value = cand.raw_value
                existing_reviewed.machine_extracted_value = cand.normalized_value
                existing_reviewed.confidence = cand.confidence
                existing_reviewed.confidence_level = cand.confidence_level
                existing_reviewed.confidence_breakdown = cand.confidence_breakdown
                existing_reviewed.image_id = cand.scan_image_id
                existing_reviewed.bounding_box = cand.union_bounding_box
                existing_reviewed.has_conflict = cand.has_conflict
                existing_reviewed.conflict_details = cand.conflict_details
                existing_reviewed.extractor_version = self.extractor.version
                existing_reviewed.updated_at = get_utc_now()
                # Update associated blocks
                existing_reviewed.ocr_blocks = cand.blocks
                if cand.blocks:
                    existing_reviewed.source_ocr_block_id = cand.blocks[0].id
                persisted_declarations.append(existing_reviewed)
            else:
                # Create new machine extracted declaration
                first_block_id = cand.blocks[0].id if cand.blocks else None
                new_decl = Declaration(
                    scan_session_id=scan_id,
                    image_id=cand.scan_image_id,
                    declaration_type=cand.declaration_type,
                    raw_text=cand.raw_text,
                    raw_value=cand.raw_value,
                    normalized_value=cand.normalized_value,
                    confidence=cand.confidence,
                    confidence_level=cand.confidence_level,
                    review_status=ReviewStatus.UNREVIEWED,
                    machine_extracted_value=cand.normalized_value,
                    source_ocr_block_id=first_block_id,
                    reviewed=False,
                    reviewed_value=None,
                    extractor_version=self.extractor.version,
                    bounding_box=cand.union_bounding_box,
                    confidence_breakdown=cand.confidence_breakdown,
                    has_conflict=cand.has_conflict,
                    conflict_details=cand.conflict_details,
                    created_at=get_utc_now(),
                    updated_at=get_utc_now(),
                )
                new_decl.ocr_blocks = cand.blocks
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

        unreviewed = sum(1 for d in declarations if d.review_status == ReviewStatus.UNREVIEWED)
        confirmed = sum(1 for d in declarations if d.review_status == ReviewStatus.CONFIRMED)
        corrected = sum(1 for d in declarations if d.review_status == ReviewStatus.CORRECTED)
        rejected = sum(1 for d in declarations if d.review_status == ReviewStatus.REJECTED)

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

        previous_status = decl.review_status.value if hasattr(decl.review_status, "value") else str(decl.review_status)

        decl.review_status = review_in.review_status
        decl.reviewed = True
        decl.reviewed_by = user_id
        decl.reviewed_at = get_utc_now()
        decl.updated_at = get_utc_now()

        if review_in.review_status == ReviewStatus.CORRECTED:
            if not review_in.reviewed_value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Corrected review requires a non-empty reviewed_value.",
                )
            decl.reviewed_value = review_in.reviewed_value
            # Also update normalized_value to reflect human correction as effective value
            decl.normalized_value = review_in.reviewed_value
        elif review_in.review_status == ReviewStatus.CONFIRMED:
            decl.reviewed_value = decl.machine_extracted_value or decl.normalized_value
        elif review_in.review_status == ReviewStatus.REJECTED:
            decl.reviewed_value = None

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
                "declaration_type": decl.declaration_type.value,
                "previous_status": previous_status,
                "new_status": review_in.review_status.value,
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
