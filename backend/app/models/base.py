from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON

# Cross-dialect JSON type: uses JSONB on PostgreSQL, standard JSON elsewhere (e.g. SQLite tests)
JSONType = JSON().with_variant(JSONB, "postgresql")


def get_utc_now():
    return datetime.now(timezone.utc)


def generate_uuid_str() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    """Provides self-updating created_at and updated_at columns."""

    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=True,
    )
