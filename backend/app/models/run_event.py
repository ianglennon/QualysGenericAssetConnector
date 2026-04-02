import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, JSON, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RunEvent(Base):
    """Stores pipeline event timeline entries for a connector sync run.

    Events are accumulated in memory by EventCollector and bulk-inserted
    after each pipeline stage completes. Detail events are only captured
    when the connector has fault_diagnosis enabled.
    """

    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("run_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
