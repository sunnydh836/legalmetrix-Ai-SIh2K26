from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum as SQLEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.enums import ComplianceStatus, ReasonCode
from app.models.base import JSONType, generate_uuid_str, get_utc_now


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    scan_session_id = Column(String(36), ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(String(36), ForeignKey("compliance_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_code = Column(String(64), nullable=False, index=True)
    rule_version = Column(String(32), nullable=False, default="1.0")
    status = Column(SQLEnum(ComplianceStatus, name="compliance_status_enum", native_enum=False), nullable=False, index=True)
    reason_code = Column(SQLEnum(ReasonCode, name="reason_code_enum", native_enum=False), nullable=False)
    message = Column(Text, nullable=False)
    detected_value = Column(JSONType, nullable=True)
    expected_requirement = Column(JSONType, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    evidence_reference = Column(JSONType, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    scan_session = relationship("ScanSession", back_populates="findings")
    rule = relationship("ComplianceRule")
