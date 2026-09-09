"""Declarations router for LegalMetrix AI Day 5 Review and Extraction."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.declaration import (
    BenchmarkEvaluationResponse,
    DeclarationResponse,
    DeclarationReviewUpdate,
    ScanDeclarationsResponse,
)
from app.services.declaration_extraction.evaluator import evaluate_declaration_benchmark
from app.services.declaration_service import DeclarationService, get_declaration_service

router = APIRouter(tags=["Declarations"])


@router.post(
    "/scans/{scan_id}/extract-declarations",
    response_model=ScanDeclarationsResponse,
    status_code=status.HTTP_200_OK,
)
def extract_declarations(
    scan_id: str,
    current_user: User = Depends(require_roles(UserRole.INSPECTOR, UserRole.ADMIN, UserRole.REVIEWER)),
    db: Session = Depends(get_db),
    declaration_service: DeclarationService = Depends(get_declaration_service),
):
    """
    Day 5: Extract and normalize legal declarations from persisted OCR blocks.
    Protected: INSPECTOR (owning), ADMIN, REVIEWER.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return declaration_service.extract_declarations_for_scan(
        db=db,
        scan_id=scan_id,
        user_id=current_user.id,
        user_role=user_role,
    )


@router.get(
    "/scans/{scan_id}/declarations",
    response_model=ScanDeclarationsResponse,
)
def get_declarations(
    scan_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    declaration_service: DeclarationService = Depends(get_declaration_service),
):
    """
    Day 5: Retrieve all structured declarations, OCR evidence linkage, and review statuses for a scan session.
    Protected: Authenticated (Inspector ownership enforced).
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return declaration_service.get_scan_declarations(
        db=db,
        scan_id=scan_id,
        user_id=current_user.id,
        user_role=user_role,
    )


@router.patch(
    "/declarations/{declaration_id}",
    response_model=DeclarationResponse,
)
def review_declaration(
    declaration_id: str,
    payload: DeclarationReviewUpdate,
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    declaration_service: DeclarationService = Depends(get_declaration_service),
):
    """
    Day 5: Review, confirm, correct, or reject an extracted declaration.
    Protected: REVIEWER, INSPECTOR, ADMIN.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return declaration_service.review_declaration(
        db=db,
        declaration_id=declaration_id,
        review_in=payload,
        user_id=current_user.id,
        user_role=user_role,
    )


@router.patch(
    "/scans/{scan_id}/declarations/{declaration_id}",
    response_model=DeclarationResponse,
)
def review_scan_declaration(
    scan_id: str,
    declaration_id: str,
    payload: DeclarationReviewUpdate,
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.INSPECTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db),
    declaration_service: DeclarationService = Depends(get_declaration_service),
):
    """
    Day 5: Review/correct a declaration under a scan session context.
    """
    user_role = current_user.role
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            pass

    return declaration_service.review_declaration(
        db=db,
        declaration_id=declaration_id,
        review_in=payload,
        user_id=current_user.id,
        user_role=user_role,
    )


@router.get(
    "/scans/{scan_id}/declarations/benchmark-eval",
    response_model=BenchmarkEvaluationResponse,
)
def get_benchmark_evaluation(
    scan_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Day 5: Benchmark evaluation status against ground-truth datasets.
    Reports 'benchmark dataset pending' when insufficient real-package labels exist.
    """
    return evaluate_declaration_benchmark(dataset_records=None, min_package_threshold=50)
