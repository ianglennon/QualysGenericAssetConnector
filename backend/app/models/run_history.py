import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, JSON, Enum, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RunStatus(str, enum.Enum):
    running = "running"
    success = "success"
    partial_success = "partial_success"
    failed = "failed"
    skipped = "skipped"


class FailureStage(str, enum.Enum):
    source_fetch = "source_fetch"
    transformation = "transformation"
    qualys_submit = "qualys_submit"


class RunHistory(Base):
    """Stores ingestion run history.

    error_context stores structured metadata only. Never persist raw credentials
    or full payloads in this field.
    """

    __tablename__ = "run_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), nullable=False, default=RunStatus.running)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False, default='manual')
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_type: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    error_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_api_calls: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    qualys_api_calls: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RunFailure(Base):
    __tablename__ = "run_failures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("run_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_identifier: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EndpointRunLog(Base):
    __tablename__ = "endpoint_run_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("run_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("connector_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False)
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_filtered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # String (not Enum) — consistent with project convention for new models
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    http_request: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    http_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    canvas_id: Mapped[str | None] = mapped_column(String, nullable=True)
    canvas_endpoint_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_api_calls: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    child_requests_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    child_requests_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    child_requests_skipped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
