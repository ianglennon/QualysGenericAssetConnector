import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class CanvasEndpoint(Base):
    __tablename__ = "canvas_endpoints"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canvas_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("canvases.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("connector_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_ref_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("canvas_endpoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    field_role: Mapped[str] = mapped_column(String, nullable=False, default="data")
    variable_extractions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    exclusion_rules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tree_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
