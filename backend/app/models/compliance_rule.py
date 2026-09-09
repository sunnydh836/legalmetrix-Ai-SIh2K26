from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, String, Text, UniqueConstraint
from app.core.database import Base
from app.core.enums import DeclarationType, RuleSeverity
from app.models.base import JSONType, generate_uuid_str, get_utc_now


class ComplianceRule(Base):
    __tablename__ = "compliance_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    rule_code = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    declaration_type = Column(SQLEnum(DeclarationType, name="declaration_type_rule_enum", native_enum=False), nullable=True, index=True)
    rule_version = Column(String(32), nullable=False, default="1.0", index=True)
    severity = Column(SQLEnum(RuleSeverity, name="rule_severity_enum", native_enum=False), default=RuleSeverity.HIGH, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    rule_definition = Column(JSONType, nullable=False)
    valid_from = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("rule_code", "rule_version", name="uq_rule_code_version"),
    )
