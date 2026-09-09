from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.core.enums import ReportStatus


class ReportCreate(BaseModel):
    scan_session_id: str
    version: int = 1
    status: ReportStatus = ReportStatus.DRAFT
    file_path: Optional[str] = None


class ReportResponse(ReportCreate):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
