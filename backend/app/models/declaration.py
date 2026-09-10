from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Float, ForeignKey, String, Table, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.enums import ConfidenceLevel, DeclarationType, ResolutionStatus
from app.models.base import JSONType, generate_uuid_str, get_utc_now

# Many-to-many association table linking declarations to contributing OCR blocks
declaration_ocr_blocks = Table(
    "declaration_ocr_blocks",
    Base.metadata,
    Column("declaration_id", String(36), ForeignKey("declarations.id", ondelete="CASCADE"), primary_key=True),
    Column("ocr_block_id", String(36), ForeignKey("ocr_blocks.id", ondelete="CASCADE"), primary_key=True),
)


class Declaration(Base):
    __tablename__ = "declarations"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_session_id = Column(String(36), ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = Column(String(36), ForeignKey("scan_images.id", ondelete="SET NULL"), nullable=True, index=True)
    declaration_type = Column(SQLEnum(DeclarationType, name="declaration_type_enum", native_enum=False), nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(JSONType, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    confidence_level = Column(
        SQLEnum(ConfidenceLevel, name="confidence_level_enum", native_enum=False),
        nullable=False,
        default=ConfidenceLevel.MEDIUM,
        index=True,
    )
    resolution_status = Column(
        SQLEnum(ResolutionStatus, name="resolution_status_enum", native_enum=False),
        nullable=False,
        default=ResolutionStatus.NOT_DETECTED,
        index=True,
    )
    resolution_reason = Column(Text, nullable=True)
    canonical_value = Column(JSONType, nullable=True)
    candidate_details = Column(JSONType, nullable=True)
    machine_extracted_value = Column(JSONType, nullable=True)
    source_ocr_block_id = Column(String(36), ForeignKey("ocr_blocks.id", ondelete="SET NULL"), nullable=True)
    reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_value = Column(JSONType, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    extractor_version = Column(String(32), default="1.0.0", nullable=False)
    bounding_box = Column(JSONType, nullable=True)
    confidence_breakdown = Column(JSONType, nullable=True)
    has_conflict = Column(Boolean, default=False, nullable=False)
    conflict_details = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=True)

    # Relationships
    scan_session = relationship("ScanSession", back_populates="declarations")
    image = relationship("ScanImage")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    source_ocr_block = relationship("OCRBlock", foreign_keys=[source_ocr_block_id])
    ocr_blocks = relationship("OCRBlock", secondary=declaration_ocr_blocks, back_populates="declarations")
