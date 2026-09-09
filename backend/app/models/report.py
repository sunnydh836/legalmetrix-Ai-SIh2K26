from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.enums import ReportStatus
from app.models.base import generate_uuid_str, get_utc_now


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_session_id = Column(String(36), ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(ReportStatus, name="report_status_enum", native_enum=False), default=ReportStatus.DRAFT, nullable=False)
    file_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    scan_session = relationship("ScanSession", back_populates="reports")
