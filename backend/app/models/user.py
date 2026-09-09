from sqlalchemy import Boolean, Column, Enum as SQLEnum, String
from app.core.database import Base
from app.core.enums import UserRole
from app.models.base import TimestampMixin, generate_uuid_str


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole, name="user_role_enum", native_enum=False), default=UserRole.INSPECTOR, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
