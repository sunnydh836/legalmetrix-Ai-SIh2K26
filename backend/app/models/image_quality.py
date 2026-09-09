from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, JSON
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.enums import ImageQualityStatus
from app.models.base import generate_uuid_str, get_utc_now


class ImageQualityMetric(Base):
    __tablename__ = "image_quality_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_image_id = Column(
        String(36),
        ForeignKey("scan_images.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    blur_score = Column(Float, nullable=False)
    glare_score = Column(Float, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    megapixels = Column(Float, nullable=False)
    resolution_status = Column(String(50), default="ACCEPTABLE", nullable=False)
    orientation_status = Column(String(50), default="CORRECT", nullable=False)
    quality_status = Column(
        SQLEnum(ImageQualityStatus, name="image_quality_status_enum", native_enum=False),
        default=ImageQualityStatus.ACCEPTED,
        nullable=False,
        index=True,
    )
    warnings = Column(
        JSON().with_variant(postgresql.JSONB(astext_type=String()), "postgresql"),
        default=list,
        nullable=False,
    )
    quality_engine_version = Column(String(50), default="opencv-5.0.0", nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=True,
    )

    # Relationships
    scan_image = relationship("ScanImage", back_populates="quality_metric")
