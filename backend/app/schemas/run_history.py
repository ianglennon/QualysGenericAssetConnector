from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RunFailureSummary(BaseModel):
    record_identifier: str
    error_message: str
    created_at: datetime

    class Config:
        from_attributes = True


class RunHistoryResponse(BaseModel):
    id: str
    connector_id: str
    connector_name: Optional[str] = None
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    records_fetched: int
    records_submitted: int
    records_failed: int
    error_type: Optional[str]
    error_message: Optional[str]
    error_context: Optional[dict]
    failures: list[RunFailureSummary] = []

    class Config:
        from_attributes = True
