import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MappingType(str, enum.Enum):
    direct_copy = "direct_copy"
    static_default = "static_default"
    conditional = "conditional"


class FieldMapping(Base):
    __tablename__ = "field_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_field: Mapped[str] = mapped_column(String, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String, nullable=False)
    source_field: Mapped[str | None] = mapped_column(String, nullable=True)
    static_value: Mapped[str | None] = mapped_column(String, nullable=True)
    # Conditional mapping fields
    conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fallback: Mapped[str | None] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
