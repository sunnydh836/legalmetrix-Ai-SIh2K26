from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.enums import ImageType
from app.models.base import generate_uuid_str, get_utc_now


class ScanImage(Base):
    __tablename__ = "scan_images"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_session_id = Column(String(36), ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    image_type = Column(SQLEnum(ImageType, name="image_type_enum", native_enum=False), default=ImageType.FRONT, nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)
    stored_filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), default="image/jpeg", nullable=False)
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)
    sha256 = Column(String(64), nullable=True, index=True)
    processing_status = Column(String(50), default="UPLOADED", nullable=False)
    ocr_processing_duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    scan_session = relationship("ScanSession", back_populates="images")
    ocr_blocks = relationship("OCRBlock", back_populates="scan_image", cascade="all, delete-orphan")
    quality_metric = relationship("ImageQualityMetric", back_populates="scan_image", uselist=False, cascade="all, delete-orphan")

