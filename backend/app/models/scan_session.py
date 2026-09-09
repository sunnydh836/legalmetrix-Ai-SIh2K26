from sqlalchemy import Column, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.enums import ScanStatus
from app.models.base import TimestampMixin, generate_uuid_str


class ScanSession(Base, TimestampMixin):
    __tablename__ = "scan_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_code = Column(String(64), unique=True, index=True, nullable=False)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    inspector_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(SQLEnum(ScanStatus, name="scan_status_enum", native_enum=False), default=ScanStatus.CREATED, nullable=False, index=True)

    # Relationships
    product = relationship("Product", backref="scan_sessions")
    inspector = relationship("User", backref="inspections")
    images = relationship("ScanImage", back_populates="scan_session", cascade="all, delete-orphan")
    declarations = relationship("Declaration", back_populates="scan_session", cascade="all, delete-orphan")
    findings = relationship("ComplianceFinding", back_populates="scan_session", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="scan_session", cascade="all, delete-orphan")
