from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.security import decode_access_token
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.auth_service import get_user_by_id

# HTTPBearer security scheme
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate request via JWT Bearer token.
    Raises 401 Unauthorized if missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not auth_credentials or not auth_credentials.credentials:
        raise credentials_exception

    token = auth_credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the authenticated user account is active.
    Raises 401 Unauthorized if user is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_roles(*allowed_roles: UserRole) -> Callable[[User, Session], User]:
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that the current authenticated active user has one of the allowed roles.
    Raises 403 Forbidden if user does not have permission.
    """
    def role_checker(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_role = current_user.role
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role)
            except ValueError:
                pass

        if user_role not in allowed_roles:
            log_audit_event(
                db=db,
                action="ACCESS_DENIED",
                entity_type="ROUTE",
                user_id=current_user.id,
                metadata={
                    "user_role": str(current_user.role),
                    "required_roles": [str(r.value if hasattr(r, "value") else r) for r in allowed_roles],
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient permissions for this resource",
            )
        return current_user

    return role_checker
