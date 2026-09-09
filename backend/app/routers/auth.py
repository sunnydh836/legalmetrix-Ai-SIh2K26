from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_roles
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserPublic
from app.schemas.common import ApiResponse
from app.services.audit_service import log_audit_event
from app.services.auth_service import (
    authenticate_user,
    create_user,
    generate_user_token,
    get_user_by_email,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, summary="Authenticate user and obtain JWT token")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email and password.
    Returns signed JWT access token and public user profile.
    """
    user, failure_reason = authenticate_user(
        db, email=login_data.email, password=login_data.password
    )

    if not user:
        # Audit log failed login attempt safely without storing plaintext password
        log_audit_event(
            db=db,
            action="LOGIN_FAILED",
            entity_type="USER",
            metadata={
                "email": login_data.email.strip().lower(),
                "reason": failure_reason or "invalid_credentials",
            },
        )
        if failure_reason == "inactive_account":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated. Please contact an administrator.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Issue token
    access_token = generate_user_token(user)

    # Audit log successful login
    log_audit_event(
        db=db,
        action="LOGIN_SUCCESS",
        entity_type="USER",
        user_id=user.id,
        entity_id=user.id,
        metadata={"email": user.email, "role": str(user.role)},
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic, summary="Get current authenticated user profile")
def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Returns the currently authenticated and active user's details.
    """
    return UserPublic.model_validate(current_user)


@router.post("/logout", summary="Logout current user and record audit event")
def logout(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Record logout audit event for the current authenticated user.
    """
    log_audit_event(
        db=db,
        action="LOGOUT",
        entity_type="USER",
        user_id=current_user.id,
        entity_id=current_user.id,
        metadata={"email": current_user.email},
    )
    return {"message": "Logged out successfully", "user_id": current_user.id}


@router.post(
    "/users",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (Admin only)",
)
def create_new_user(
    user_in: UserCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Admin-only endpoint to register a new user in the system.
    """
    existing_user = get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists",
        )

    new_user = create_user(
        db=db,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=user_in.is_active,
    )

    log_audit_event(
        db=db,
        action="USER_CREATED",
        entity_type="USER",
        user_id=current_user.id,
        entity_id=new_user.id,
        metadata={"created_email": new_user.email, "assigned_role": str(new_user.role)},
    )

    return UserPublic.model_validate(new_user)


# Protected RBAC test / verification endpoints
@router.get("/test/admin-only", summary="Verify Admin-only RBAC access")
def test_admin_access(current_user: User = Depends(require_roles(UserRole.ADMIN))):
    return {"message": "Admin authorization granted", "user_id": current_user.id, "role": current_user.role}


@router.get("/test/inspector-access", summary="Verify Inspector/Admin RBAC access")
def test_inspector_access(current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INSPECTOR))):
    return {"message": "Inspector authorization granted", "user_id": current_user.id, "role": current_user.role}


@router.get("/test/reviewer-access", summary="Verify Reviewer/Admin RBAC access")
def test_reviewer_access(current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER))):
    return {"message": "Reviewer authorization granted", "user_id": current_user.id, "role": current_user.role}
