from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.core.enums import UserRole
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import UserCreate


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Find a user by email address."""
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Find a user by UUID identifier."""
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> Tuple[Optional[User], Optional[str]]:
    """
    Authenticate user with email and password.
    Returns (user, None) if successful.
    Returns (None, reason) if authentication fails:
      - reason="invalid_credentials"
      - reason="inactive_account"
    """
    user = get_user_by_email(db, email)
    if not user:
        return None, "invalid_credentials"
    
    if not verify_password(password, user.password_hash):
        return None, "invalid_credentials"
    
    if not user.is_active:
        return None, "inactive_account"
    
    return user, None


def create_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.INSPECTOR,
    is_active: bool = True,
) -> User:
    """Create a new user with hashed password."""
    user = User(
        email=email.strip().lower(),
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def generate_user_token(user: User) -> str:
    """Generate JWT access token for authenticated user."""
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }
    return create_access_token(payload)
