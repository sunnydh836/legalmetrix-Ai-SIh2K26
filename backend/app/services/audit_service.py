import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Record an immutable audit log entry in the database.
    Ensures no passwords, secrets, or JWT tokens are stored in metadata.
    """
    # Sanitize metadata to prevent any accidental credential leakage
    safe_metadata = {}
    if metadata:
        for k, v in metadata.items():
            if any(sensitive in k.lower() for sensitive in ["password", "token", "secret", "key", "authorization"]):
                continue
            safe_metadata[k] = v

    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        audit_metadata=safe_metadata if safe_metadata else None,
    )
    try:
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write audit log: {e}")
    
    return audit_entry
