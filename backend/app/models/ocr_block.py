from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import generate_uuid_str, get_utc_now


class OCRBlock(Base):
    __tablename__ = "ocr_blocks"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_image_id = Column(String(36), ForeignKey("scan_images.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    bbox_x1 = Column(Integer, nullable=False)
    bbox_y1 = Column(Integer, nullable=False)
    bbox_x2 = Column(Integer, nullable=False)
    bbox_y2 = Column(Integer, nullable=False)
    polygon = Column(
        JSON().with_variant(postgresql.JSONB(astext_type=String()), "postgresql"),
        nullable=True,
    )
    block_order = Column(Integer, default=0, nullable=False)
    ocr_engine = Column(String(50), default="paddleocr", nullable=False)
    ocr_engine_version = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    scan_image = relationship("ScanImage", back_populates="ocr_blocks")
    declarations = relationship("Declaration", secondary="declaration_ocr_blocks", back_populates="ocr_blocks")
