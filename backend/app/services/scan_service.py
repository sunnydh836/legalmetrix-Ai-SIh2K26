import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ImageType, ScanStatus, UserRole
from app.models.product import Product
from app.models.scan_image import ScanImage
from app.models.scan_session import ScanSession
from app.schemas.scan import ProductCreate, ScanImageOrderRequest
from app.services.audit_service import log_audit_event
from app.services.image_intake_service import ImageIntakeService, ProcessedImage
from app.services.storage_service import StorageServiceInterface

logger = logging.getLogger(__name__)


def generate_unique_scan_code(db: Session) -> str:
    """
    Generate collision-safe human-readable scan code.
    Format: SCAN-2026-000001
    """
    current_year = datetime.now(timezone.utc).year
    prefix = f"SCAN-{current_year}-"

    # Query highest existing sequence for this year
    latest_scan = (
        db.query(ScanSession.scan_code)
        .filter(ScanSession.scan_code.like(f"{prefix}%"))
        .order_by(desc(ScanSession.scan_code))
        .first()
    )

    next_num = 1
    if latest_scan and latest_scan[0]:
        try:
            suffix = latest_scan[0].replace(prefix, "")
            next_num = int(suffix) + 1
        except ValueError:
            next_num = 1

    # Format with 6 digits padding
    scan_code = f"{prefix}{next_num:06d}"

    # Safety check for uniqueness
    while db.query(ScanSession).filter(ScanSession.scan_code == scan_code).first():
        next_num += 1
        scan_code = f"{prefix}{next_num:06d}"

    return scan_code


def get_or_create_product(db: Session, product_in: Optional[ProductCreate]) -> Optional[Product]:
    """
    Find existing product by exact barcode or create new product record.
    Preserves leading zeros in barcode strings.
    """
    if not product_in:
        return None

    name = (product_in.name or "").strip()
    barcode = (product_in.barcode or "").strip()
    brand = (product_in.brand or "").strip() or None
    category = (product_in.category or "").strip() or None
    mfg = (product_in.manufacturer_name or "").strip() or None

    if not name and not barcode and not brand and not category and not mfg:
        return None

    if not name:
        name = "Untitled Packaging Capture"

    # 1. Barcode lookup
    if barcode:
        existing = db.query(Product).filter(Product.barcode == barcode).first()
        if existing:
            # Update non-empty metadata if missing
            updated = False
            if brand and not existing.brand:
                existing.brand = brand
                updated = True
            if category and not existing.category:
                existing.category = category
                updated = True
            if mfg and not existing.manufacturer_name:
                existing.manufacturer_name = mfg
                updated = True
            if updated:
                db.commit()
                db.refresh(existing)
            return existing

    # 2. Create new Product
    new_product = Product(
        name=name,
        brand=brand,
        category=category,
        barcode=barcode if barcode else None,
        manufacturer_name=mfg,
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


def create_scan_session(
    db: Session,
    inspector_id: str,
    product_in: Optional[ProductCreate] = None,
) -> ScanSession:
    """Create a new scan session with status CREATED and unique scan code."""
    scan_code = generate_unique_scan_code(db)
    product = get_or_create_product(db, product_in)

    scan = ScanSession(
        scan_code=scan_code,
        inspector_id=inspector_id,
        product_id=product.id if product else None,
        status=ScanStatus.CREATED,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    log_audit_event(
        db=db,
        action="SCAN_CREATED",
        entity_type="SCAN_SESSION",
        user_id=inspector_id,
        entity_id=scan.id,
        metadata={
            "scan_code": scan.scan_code,
            "product_id": product.id if product else None,
            "product_name": product.name if product else None,
            "barcode": product.barcode if product else None,
        },
    )

    return scan


def get_scan_session(db: Session, scan_id: str) -> Optional[ScanSession]:
    """Fetch scan session by ID or scan_code."""
    return (
        db.query(ScanSession)
        .filter((ScanSession.id == scan_id) | (ScanSession.scan_code == scan_id))
        .first()
    )


def verify_scan_modification_access(scan: ScanSession, user_id: str, user_role: UserRole) -> None:
    """Enforce that only the owning Inspector or Admin can modify a scan."""
    if user_role == UserRole.ADMIN:
        return
    if scan.inspector_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to modify this scan session.",
        )


async def upload_scan_images(
    db: Session,
    scan: ScanSession,
    user_id: str,
    user_role: UserRole,
    files: List[UploadFile],
    image_type: ImageType,
    storage_service: StorageServiceInterface,
) -> List[ScanImage]:
    """
    Validate, process, and persist uploaded inspection images.
    Enforces size limits, format validation, EXIF transposition, and duplicate detection.
    """
    verify_scan_modification_access(scan, user_id, user_role)

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files provided for upload.",
        )

    # Check total image count limit
    current_count = db.query(ScanImage).filter(ScanImage.scan_session_id == scan.id).count()
    if current_count + len(files) > settings.MAX_IMAGES_PER_SCAN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.MAX_IMAGES_PER_SCAN} images per inspection session exceeded.",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    created_scan_images: List[ScanImage] = []
    saved_storage_paths: List[str] = []

    # Get max current display order
    max_order = (
        db.query(func.max(ScanImage.display_order))
        .filter(ScanImage.scan_session_id == scan.id)
        .scalar()
    )
    current_order = (max_order if max_order is not None else -1) + 1

    try:
        for file in files:
            raw_bytes = await file.read()

            # File size check
            if len(raw_bytes) > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File '{file.filename}' exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                )

            # Process & validate image with Pillow
            try:
                processed: ProcessedImage = ImageIntakeService.process_image(
                    raw_bytes=raw_bytes,
                    original_filename=file.filename,
                )
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation error for '{file.filename}': {str(e)}",
                )

            # Duplicate detection within the SAME scan session
            existing_duplicate = (
                db.query(ScanImage)
                .filter(
                    ScanImage.scan_session_id == scan.id,
                    ScanImage.sha256 == processed.sha256,
                )
                .first()
            )
            if existing_duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This image has already been uploaded for this scan (filename: '{file.filename}').",
                )

            # Save to storage abstraction
            rel_path, stored_filename = storage_service.save_file(
                file_bytes=processed.file_bytes,
                scan_id=scan.id,
                extension=processed.extension,
            )
            saved_storage_paths.append(rel_path)

            # Create ScanImage DB record
            scan_img = ScanImage(
                scan_session_id=scan.id,
                image_type=image_type,
                file_path=rel_path,
                stored_filename=stored_filename,
                original_filename=file.filename,
                mime_type=processed.mime_type,
                file_size=processed.file_size,
                width=processed.width,
                height=processed.height,
                display_order=current_order,
                sha256=processed.sha256,
            )
            db.add(scan_img)
            created_scan_images.append(scan_img)
            current_order += 1

        # Update ScanSession status to IMAGES_UPLOADED
        if scan.status == ScanStatus.CREATED:
            scan.status = ScanStatus.IMAGES_UPLOADED

        db.commit()

        # Refresh all created records
        for img in created_scan_images:
            db.refresh(img)
            log_audit_event(
                db=db,
                action="IMAGE_UPLOADED",
                entity_type="SCAN_IMAGE",
                user_id=user_id,
                entity_id=img.id,
                metadata={
                    "scan_id": scan.id,
                    "scan_code": scan.scan_code,
                    "image_type": str(img.image_type.value if hasattr(img.image_type, 'value') else img.image_type),
                    "file_size": img.file_size,
                    "dimensions": f"{img.width}x{img.height}",
                    "sha256": img.sha256,
                },
            )

        return created_scan_images

    except Exception:
        db.rollback()
        # Clean up any saved files on disk to prevent orphaned files
        for rel_path in saved_storage_paths:
            try:
                storage_service.delete_file(rel_path)
            except Exception as clean_err:
                logger.error(f"Failed to cleanup orphaned file {rel_path}: {clean_err}")
        raise


def delete_scan_image(
    db: Session,
    scan: ScanSession,
    image_id: str,
    user_id: str,
    user_role: UserRole,
    storage_service: StorageServiceInterface,
) -> bool:
    """Delete a scan image record and its physical storage file."""
    verify_scan_modification_access(scan, user_id, user_role)

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

    file_path = image.file_path
    image_meta = {
        "scan_id": scan.id,
        "scan_code": scan.scan_code,
        "image_id": image.id,
        "image_type": str(image.image_type.value if hasattr(image.image_type, 'value') else image.image_type),
    }

    db.delete(image)
    db.commit()

    # Delete physical file from disk
    if file_path:
        storage_service.delete_file(file_path)

    # Check remaining images and update status if 0
    remaining_count = db.query(ScanImage).filter(ScanImage.scan_session_id == scan.id).count()
    if remaining_count == 0 and scan.status == ScanStatus.IMAGES_UPLOADED:
        scan.status = ScanStatus.CREATED
        db.commit()

    log_audit_event(
        db=db,
        action="IMAGE_DELETED",
        entity_type="SCAN_IMAGE",
        user_id=user_id,
        entity_id=image_id,
        metadata=image_meta,
    )

    return True


def reorder_scan_images(
    db: Session,
    scan: ScanSession,
    order_req: ScanImageOrderRequest,
    user_id: str,
    user_role: UserRole,
) -> List[ScanImage]:
    """Reorder scan images by given sequence of IDs."""
    verify_scan_modification_access(scan, user_id, user_role)

    existing_images = (
        db.query(ScanImage)
        .filter(ScanImage.scan_session_id == scan.id)
        .all()
    )
    existing_map = {img.id: img for img in existing_images}

    if len(order_req.image_ids) != len(existing_images):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reorder list count must match total existing images for this scan.",
        )

    if set(order_req.image_ids) != set(existing_map.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reorder list contains invalid, duplicate, or foreign image IDs.",
        )

    for index, img_id in enumerate(order_req.image_ids):
        existing_map[img_id].display_order = index

    db.commit()

    log_audit_event(
        db=db,
        action="IMAGE_REORDERED",
        entity_type="SCAN_SESSION",
        user_id=user_id,
        entity_id=scan.id,
        metadata={
            "scan_id": scan.id,
            "scan_code": scan.scan_code,
            "new_order": order_req.image_ids,
        },
    )

    return (
        db.query(ScanImage)
        .filter(ScanImage.scan_session_id == scan.id)
        .order_by(ScanImage.display_order.asc(), ScanImage.created_at.asc())
        .all()
    )
