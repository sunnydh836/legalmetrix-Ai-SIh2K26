from datetime import datetime
import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.enums import UserRole

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email_format(v: str) -> str:
    cleaned = v.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError("Invalid email address format")
    return cleaned


class LoginRequest(BaseModel):
    """Schema for user authentication request."""
    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(..., min_length=1, description="Plaintext password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_format(v)


class UserBase(BaseModel):
    """Base user schema."""
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., max_length=255)
    role: UserRole = UserRole.INSPECTOR
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_format(v)


class UserCreate(UserBase):
    """Schema for creating a new user (Admin-only or seed)."""
    password: str = Field(..., min_length=6, description="Plaintext password")


class UserPublic(BaseModel):
    """Publicly safe user profile representation (never exposes password_hash)."""
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """JWT Token response schema."""
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class TokenPayload(BaseModel):
    """Decoded JWT payload structure."""
    sub: str
    role: str
    exp: int
    iat: Optional[int] = None
