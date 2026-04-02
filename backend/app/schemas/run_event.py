from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StageEntry(BaseModel):
    stage: str
    records_in: int
    records_out: int
    duration_ms: int
    status: str
    error: Optional[str] = None


class EventEntry(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    stage: str
    message: str
    detail: Optional[dict] = None

    class Config:
        from_attributes = True


class RunEventsResponse(BaseModel):
    stages: list[StageEntry]
    events: list[EventEntry]
    total_events: int
