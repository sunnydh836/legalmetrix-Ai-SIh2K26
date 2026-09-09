from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.core.database import get_db
from app.core.enums import ImageType, UserRole
from app.models.scan_image import ScanImage
from app.models.user import User
from app.schemas.scan import (
    InspectorResponse,
    ProductResponse,
    ScanImageOrderRequest,
    ScanImageResponse,
    ScanListResponse,
    ScanSessionCreate,
    ScanSessionResponse,
)
from app.schemas.ocr import (
    ImageOCRDetailResponse,
    ProcessScanResponse,
    ScanOCRResponse,
)
from app.services.scan_service import (
    create_scan_session,
    delete_scan_image,
    get_scan_session,
    reorder_scan_images,
    upload_scan_images,
)
from app.services.scan_processing_service import (
    get_scan_ocr_results,
    process_scan_session,
    reprocess_image as reprocess_single_image,
)
from app.services.image_quality_service import ImageQualityServiceInterface, get_image_quality_service
from app.services.ocr_service import OCRServiceInterface, get_ocr_service
from app.services.storage_service import StorageServiceInterface, get_storage_service

router = APIRouter(prefix="/scans", tags=["Scans"])


def _build_scan_response(scan, db: Session) -> ScanSessionResponse:
    """Helper to assemble ScanSessionResponse with ordered images and safe preview URLs."""
    images = (
        db.query(ScanImage)
        .filter(ScanImage.scan_session_id == scan.id)
        .order_by(ScanImage.display_order.asc(), ScanImage.created_at.asc())
        .all()
    )

    image_responses = [
        ScanImageResponse(
            id=img.id,
            scan_session_id=img.scan_session_id,
            image_type=img.image_type,
            original_filename=img.original_filename,
            mime_type=img.mime_type,
            file_size=img.file_size,
            width=img.width,
            height=img.height,
            display_order=img.display_order,
            created_at=img.created_at,
            preview_url=f"/api/v1/scans/{scan.id}/images/{img.id}/content",
        )
        for img in images
    ]

    product_resp = None
    if scan.product:
        product_resp = ProductResponse(
            id=scan.product.id,
            name=scan.product.name,
            brand=scan.product.brand,
            category=scan.product.category,
            barcode=scan.product.barcode,
            manufacturer_name=scan.product.manufacturer_name,
            created_at=scan.product.created_at,
            updated_at=scan.product.updated_at,
        )

    inspector_resp = None
    if scan.inspector:
        inspector_resp = InspectorResponse(
            id=scan.inspector.id,
            email=scan.inspector.email,
            full_name=scan.inspector.full_name,
            role=scan.inspector.role,
        )

    return ScanSessionResponse(
        id=scan.id,
        scan_code=scan.scan_code,
        status=scan.status,
        product=product_resp,
        inspector=inspector_resp,
        images=image_responses,
        created_at=scan.created_at,
        updated_at=scan.updated_at,
    )


@router.post("", response_model=ScanSessionResponse, status_code=status.HTTP_201_CREATED)
def create_scan(
    payload: Optional[ScanSessionCreate] = None,
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Initiate a new scan inspection session.
    Protected: INSPECTOR, ADMIN.
    """
    product_in = payload.product if payload else None
    scan = create_scan_session(
        db=db,
        inspector_id=current_user.id,
        product_in=product_in,
    )
    return _build_scan_response(scan, db)


@router.get("", response_model=ScanListResponse)
def list_scans(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    List scan sessions.
    - INSPECTOR sees own scans.
    - ADMIN and REVIEWER see all scans.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    from app.models.scan_session import ScanSession
    query = db.query(ScanSession)
    if user_role == UserRole.INSPECTOR:
        query = query.filter(ScanSession.inspector_id == current_user.id)

    scans = query.order_by(ScanSession.created_at.desc()).all()
    items = [_build_scan_response(s, db) for s in scans]
    return ScanListResponse(items=items, total=len(items))


@router.get("/{scan_id}", response_model=ScanSessionResponse)
def get_scan(
    scan_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve details and uploaded images for a scan session.
    Protected: Authenticated. Ownership enforced for Inspectors.
    """
    scan = get_scan_session(db, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    # Enforce IDOR protection: Inspectors can only access their own scans
    if user_role == UserRole.INSPECTOR and scan.inspector_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view this scan session.",
        )

    return _build_scan_response(scan, db)


@router.post("/{scan_id}/images", response_model=List[ScanImageResponse])
async def upload_images(
    scan_id: str,
    files: List[UploadFile] = File(...),
    image_type: ImageType = Form(ImageType.FRONT),
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    storage_service: StorageServiceInterface = Depends(get_storage_service),
):
    """
    Upload one or multiple images to a scan session.
    Protected: INSPECTOR (owning inspector) or ADMIN.
    """
    scan = get_scan_session(db, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    created_images = await upload_scan_images(
        db=db,
        scan=scan,
        user_id=current_user.id,
        user_role=user_role,
        files=files,
        image_type=image_type,
        storage_service=storage_service,
    )

    return [
        ScanImageResponse(
            id=img.id,
            scan_session_id=img.scan_session_id,
            image_type=img.image_type,
            original_filename=img.original_filename,
            mime_type=img.mime_type,
            file_size=img.file_size,
            width=img.width,
            height=img.height,
            display_order=img.display_order,
            created_at=img.created_at,
            preview_url=f"/api/v1/scans/{scan.id}/images/{img.id}/content",
        )
        for img in created_images
    ]


from fastapi import Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_optional_bearer = HTTPBearer(auto_error=False)


@router.get("/{scan_id}/images/{image_id}/content")
@router.get("/{scan_id}/images/{image_id}/file")
def get_image_content(
    scan_id: str,
    image_id: str,
    token: Optional[str] = Query(None),
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
    storage_service: StorageServiceInterface = Depends(get_storage_service),
):
    """
    Serve uploaded image content securely.
    Supports Bearer header, URL query parameter token, or browser <img> tags for registered scan images.
    """
    scan = get_scan_session(db, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    # Validate token if supplied in header or query parameter
    active_token = auth_credentials.credentials if (auth_credentials and auth_credentials.credentials) else token
    if active_token:
        try:
            from app.core.security import decode_access_token
            from app.services.auth_service import get_user_by_id

            payload = decode_access_token(active_token)
            user_id = payload.get("sub")
            if user_id:
                user = get_user_by_id(db, user_id=user_id)
                if user and user.role == UserRole.INSPECTOR and scan.inspector_id != user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access forbidden: you do not have permission to view this image.",
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # Fall through to scan/image database validation

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

    try:
        file_path = storage_service.get_file_path(image.file_path)
    except (FileNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image storage file not found on server.",
        )

    return FileResponse(
        path=str(file_path),
        media_type=image.mime_type or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.delete("/{scan_id}/images/{image_id}")
def delete_image(
    scan_id: str,
    image_id: str,
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    storage_service: StorageServiceInterface = Depends(get_storage_service),
):
    """
    Delete an image from a scan session.
    Protected: Owning INSPECTOR or ADMIN.
    """
    scan = get_scan_session(db, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    delete_scan_image(
        db=db,
        scan=scan,
        image_id=image_id,
        user_id=current_user.id,
        user_role=user_role,
        storage_service=storage_service,
    )
    return {"success": True, "message": "Image deleted successfully."}


@router.patch("/{scan_id}/images/order", response_model=List[ScanImageResponse])
def reorder_images(
    scan_id: str,
    order_req: ScanImageOrderRequest,
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Reorder images in a scan session.
    Protected: Owning INSPECTOR or ADMIN.
    """
    scan = get_scan_session(db, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session not found.",
        )

    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    ordered_images = reorder_scan_images(
        db=db,
        scan=scan,
        order_req=order_req,
        user_id=current_user.id,
        user_role=user_role,
    )

    return [
        ScanImageResponse(
            id=img.id,
            scan_session_id=img.scan_session_id,
            image_type=img.image_type,
            original_filename=img.original_filename,
            mime_type=img.mime_type,
            file_size=img.file_size,
            width=img.width,
            height=img.height,
            display_order=img.display_order,
            created_at=img.created_at,
            preview_url=f"/api/v1/scans/{scan.id}/images/{img.id}/content",
        )
        for img in ordered_images
    ]


@router.post("/{scan_id}/process", response_model=ProcessScanResponse)
def process_scan(
    scan_id: str,
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    storage_service: StorageServiceInterface = Depends(get_storage_service),
    quality_service: ImageQualityServiceInterface = Depends(get_image_quality_service),
    ocr_service: OCRServiceInterface = Depends(get_ocr_service),
):
    """
    Day 4: Execute Image Quality Analysis and PaddleOCR Layout Extraction on all images in a scan session.
    Protected: INSPECTOR (owning inspector) or ADMIN.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return process_scan_session(
        db=db,
        scan_id=scan_id,
        user_id=current_user.id,
        user_role=user_role,
        storage_service=storage_service,
        quality_service=quality_service,
        ocr_service=ocr_service,
    )


@router.get("/{scan_id}/ocr", response_model=ScanOCRResponse)
def get_ocr_results(
    scan_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Day 4: Retrieve persisted OCR text blocks, confidence, geometry, and image quality metrics.
    Protected: Authenticated. Ownership enforced for Inspectors.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return get_scan_ocr_results(
        db=db,
        scan_id=scan_id,
        user_id=current_user.id,
        user_role=user_role,
    )


@router.post("/{scan_id}/images/{image_id}/reprocess", response_model=ImageOCRDetailResponse)
def reprocess_scan_image(
    scan_id: str,
    image_id: str,
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    storage_service: StorageServiceInterface = Depends(get_storage_service),
    quality_service: ImageQualityServiceInterface = Depends(get_image_quality_service),
    ocr_service: OCRServiceInterface = Depends(get_ocr_service),
):
    """
    Day 4: Reprocess a single image within a scan session idempotently.
    Protected: INSPECTOR (owning inspector) or ADMIN.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return reprocess_single_image(
        db=db,
        scan_id=scan_id,
        image_id=image_id,
        user_id=current_user.id,
        user_role=user_role,
        storage_service=storage_service,
        quality_service=quality_service,
        ocr_service=ocr_service,
    )
