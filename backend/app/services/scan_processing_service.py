import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import (
    ImageProcessingStatus,
    ImageQualityStatus,
    ScanStatus,
    UserRole,
)
from app.models.image_quality import ImageQualityMetric
from app.models.ocr_block import OCRBlock
from app.models.scan_image import ScanImage
from app.models.scan_session import ScanSession
from app.schemas.ocr import (
    ImageOCRDetailResponse,
    OCRBlockResponse,
    ProcessScanResponse,
    ScanImageQualityResponse,
    ScanOCRResponse,
)
from app.services.audit_service import log_audit_event
from app.services.image_quality_service import ImageQualityServiceInterface, get_image_quality_service
from app.services.ocr_service import OCRServiceInterface, get_ocr_service
from app.services.storage_service import StorageServiceInterface, get_storage_service

logger = logging.getLogger(__name__)


def _build_image_detail_response(img: ScanImage, db: Session) -> ImageOCRDetailResponse:
    """Helper to assemble structured ImageOCRDetailResponse with quality metrics and OCR blocks."""
    quality_resp = None
    if img.quality_metric:
        qm = img.quality_metric
        # Ensure warnings is a list of strings
        raw_warnings = qm.warnings if isinstance(qm.warnings, list) else []
        warnings_list = [str(w) for w in raw_warnings]

        quality_resp = ScanImageQualityResponse(
            id=qm.id,
            scan_image_id=qm.scan_image_id,
            blur_score=qm.blur_score,
            glare_score=qm.glare_score,
            width=qm.width,
            height=qm.height,
            megapixels=qm.megapixels,
            resolution_status=qm.resolution_status,
            orientation_status=qm.orientation_status,
            quality_status=qm.quality_status.value if hasattr(qm.quality_status, "value") else str(qm.quality_status),
            warnings=warnings_list,
            quality_engine_version=qm.quality_engine_version,
            created_at=qm.created_at,
        )

    # Fetch OCR blocks ordered by block_order
    blocks = (
        db.query(OCRBlock)
        .filter(OCRBlock.scan_image_id == img.id)
        .order_by(OCRBlock.block_order.asc(), OCRBlock.created_at.asc())
        .all()
    )

    block_responses = [
        OCRBlockResponse(
            id=b.id,
            scan_image_id=b.scan_image_id,
            text=b.text,
            confidence=b.confidence,
            bbox_x1=b.bbox_x1,
            bbox_y1=b.bbox_y1,
            bbox_x2=b.bbox_x2,
            bbox_y2=b.bbox_y2,
            polygon=b.polygon,
            block_order=b.block_order,
            ocr_engine=b.ocr_engine,
            ocr_engine_version=b.ocr_engine_version,
            created_at=b.created_at,
        )
        for b in blocks
    ]

    return ImageOCRDetailResponse(
        image_id=img.id,
        image_type=img.image_type.value if hasattr(img.image_type, "value") else str(img.image_type),
        original_filename=img.original_filename,
        preview_url=f"/api/v1/scans/{img.scan_session_id}/images/{img.id}/content",
        processing_status=img.processing_status,
        ocr_processing_duration_ms=img.ocr_processing_duration_ms,
        quality=quality_resp,
        ocr_blocks=block_responses,
    )


def process_single_image(
    db: Session,
    image: ScanImage,
    storage_service: StorageServiceInterface,
    quality_service: ImageQualityServiceInterface,
    ocr_service: OCRServiceInterface,
) -> None:
    """
    Process an individual image: Image Quality Analysis + Preprocessing + PaddleOCR.
    Atomic and idempotent: replaces prior quality metrics and OCR blocks.
    """
    image.processing_status = ImageProcessingStatus.PROCESSING.value
    db.commit()
    db.refresh(image)

    try:
        file_path = storage_service.get_file_path(image.file_path)
        str_path = str(file_path)

        # 1. Run explainable Image Quality Analysis
        quality_res = quality_service.evaluate_quality(str_path, scan_image_id=image.id)
        warnings_serialized = [
            w.value if hasattr(w, "value") else str(w) for w in quality_res.warnings
        ]

        # Persist or update ImageQualityMetric
        if image.quality_metric:
            qm = image.quality_metric
            qm.blur_score = quality_res.blur_score
            qm.glare_score = quality_res.glare_score
            qm.width = quality_res.resolution.get("width", image.width or 0)
            qm.height = quality_res.resolution.get("height", image.height or 0)
            qm.megapixels = quality_res.details.get("megapixels", 0.0) if quality_res.details else 0.0
            qm.resolution_status = quality_res.details.get("resolution_status", "ACCEPTABLE") if quality_res.details else "ACCEPTABLE"
            qm.orientation_status = quality_res.details.get("orientation_status", "CORRECT") if quality_res.details else "CORRECT"
            qm.quality_status = quality_res.quality_status
            qm.warnings = warnings_serialized
            qm.quality_engine_version = quality_res.details.get("quality_engine_version", "opencv") if quality_res.details else "opencv"
        else:
            qm = ImageQualityMetric(
                scan_image_id=image.id,
                blur_score=quality_res.blur_score,
                glare_score=quality_res.glare_score,
                width=quality_res.resolution.get("width", image.width or 0),
                height=quality_res.resolution.get("height", image.height or 0),
                megapixels=quality_res.details.get("megapixels", 0.0) if quality_res.details else 0.0,
                resolution_status=quality_res.details.get("resolution_status", "ACCEPTABLE") if quality_res.details else "ACCEPTABLE",
                orientation_status=quality_res.details.get("orientation_status", "CORRECT") if quality_res.details else "CORRECT",
                quality_status=quality_res.quality_status,
                warnings=warnings_serialized,
                quality_engine_version=quality_res.details.get("quality_engine_version", "opencv") if quality_res.details else "opencv",
            )
            db.add(qm)

        # 2. Idempotent OCR reprocessing: clear prior OCR blocks
        db.query(OCRBlock).filter(OCRBlock.scan_image_id == image.id).delete()

        # 3. Run PaddleOCR / RapidOCR
        ocr_result = ocr_service.process_image(str_path, scan_image_id=image.id)

        for block in ocr_result.blocks:
            ocr_record = OCRBlock(
                scan_image_id=image.id,
                text=block.text,
                confidence=block.confidence,
                bbox_x1=block.bbox.x1,
                bbox_y1=block.bbox.y1,
                bbox_x2=block.bbox.x2,
                bbox_y2=block.bbox.y2,
                polygon=block.polygon,
                block_order=block.block_order,
                ocr_engine=ocr_result.engine,
                ocr_engine_version=ocr_result.engine_version,
            )
            db.add(ocr_record)

        image.ocr_processing_duration_ms = ocr_result.processing_duration_ms
        if quality_res.quality_status == ImageQualityStatus.RECAPTURE_RECOMMENDED:
            image.processing_status = ImageProcessingStatus.RECAPTURE_RECOMMENDED.value
        else:
            image.processing_status = ImageProcessingStatus.COMPLETED.value

        db.commit()
        db.refresh(image)

    except Exception as e:
        logger.error(f"Processing failed for image '{image.id}': {e}", exc_info=True)
        db.rollback()
        image.processing_status = ImageProcessingStatus.FAILED.value
        db.commit()
        db.refresh(image)


def process_scan_session(
    db: Session,
    scan_id: str,
    user_id: str,
    user_role: UserRole,
    storage_service: StorageServiceInterface,
    quality_service: ImageQualityServiceInterface,
    ocr_service: OCRServiceInterface,
) -> ProcessScanResponse:
    """
    Orchestrates end-to-end image quality analysis and OCR layout extraction for a scan.
    Enforces authorization, idempotent execution, and audit logging.
    """
    scan = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    # Enforce RBAC / IDOR: INSPECTOR can only process their own scan
    if user_role == UserRole.INSPECTOR and scan.inspector_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to process this scan session.",
        )

    # Ensure scan has images
    images = (
        db.query(ScanImage)
        .filter(ScanImage.scan_session_id == scan.id)
        .order_by(ScanImage.display_order.asc(), ScanImage.created_at.asc())
        .all()
    )
    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scan session has no uploaded images. Please upload packaging images before processing.",
        )

    # Set scan status to PROCESSING
    scan.status = ScanStatus.PROCESSING
    db.commit()
    db.refresh(scan)

    log_audit_event(
        db=db,
        user_id=user_id,
        action="SCAN_PROCESSING_STARTED",
        entity_type="ScanSession",
        entity_id=scan.id,
        metadata={"image_count": len(images)},
    )

    # Process each image with individual failure containment
    processed_count = 0
    for img in images:
        process_single_image(
            db=db,
            image=img,
            storage_service=storage_service,
            quality_service=quality_service,
            ocr_service=ocr_service,
        )
        processed_count += 1

    # Reload all images to determine final scan status
    db.refresh(scan)
    all_images = (
        db.query(ScanImage)
        .filter(ScanImage.scan_session_id == scan.id)
        .order_by(ScanImage.display_order.asc(), ScanImage.created_at.asc())
        .all()
    )

    all_failed = all(img.processing_status == ImageProcessingStatus.FAILED.value for img in all_images)
    if all_failed:
        scan.status = ScanStatus.FAILED
    else:
        # Move to OCR_COMPLETED (evidence extraction complete, ready for Day 5)
        scan.status = ScanStatus.OCR_COMPLETED

    db.commit()
    db.refresh(scan)

    log_audit_event(
        db=db,
        user_id=user_id,
        action="SCAN_PROCESSING_COMPLETED",
        entity_type="ScanSession",
        entity_id=scan.id,
        metadata={
            "scan_status": scan.status.value if hasattr(scan.status, "value") else str(scan.status),
            "processed_images": processed_count,
        },
    )

    image_details = [_build_image_detail_response(img, db) for img in all_images]

    return ProcessScanResponse(
        scan_id=scan.id,
        scan_code=scan.scan_code,
        status=scan.status.value if hasattr(scan.status, "value") else str(scan.status),
        message=f"Successfully processed {processed_count} image(s). OCR evidence and quality diagnostics generated.",
        images_processed=processed_count,
        images=image_details,
    )


def get_scan_ocr_results(
    db: Session,
    scan_id: str,
    user_id: str,
    user_role: UserRole,
) -> ScanOCRResponse:
    """Retrieve persisted image quality metrics and OCR layout blocks for a scan."""
    scan = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    if user_role == UserRole.INSPECTOR and scan.inspector_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view OCR results for this scan.",
        )

    images = (
        db.query(ScanImage)
        .filter(ScanImage.scan_session_id == scan.id)
        .order_by(ScanImage.display_order.asc(), ScanImage.created_at.asc())
        .all()
    )

    image_details = [_build_image_detail_response(img, db) for img in images]

    return ScanOCRResponse(
        scan_id=scan.id,
        scan_code=scan.scan_code,
        status=scan.status.value if hasattr(scan.status, "value") else str(scan.status),
        images=image_details,
    )


def reprocess_image(
    db: Session,
    scan_id: str,
    image_id: str,
    user_id: str,
    user_role: UserRole,
    storage_service: StorageServiceInterface,
    quality_service: ImageQualityServiceInterface,
    ocr_service: OCRServiceInterface,
) -> ImageOCRDetailResponse:
    """Reprocess a specific image in a scan session idempotently."""
    scan = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    if user_role == UserRole.INSPECTOR and scan.inspector_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to reprocess images in this scan.",
        )

    image = (
        db.query(ScanImage)
        .filter(ScanImage.id == image_id, ScanImage.scan_session_id == scan.id)
        .first()
    )
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found in this scan session.",
        )

    log_audit_event(
        db=db,
        user_id=user_id,
        action="IMAGE_REPROCESSING_STARTED",
        entity_type="ScanImage",
        entity_id=image.id,
        metadata={"scan_id": scan.id},
    )

    process_single_image(
        db=db,
        image=image,
        storage_service=storage_service,
        quality_service=quality_service,
        ocr_service=ocr_service,
    )

    return _build_image_detail_response(image, db)
