"""Pydantic schemas for Canvas CRUD API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CanvasCreate(BaseModel):
    """Schema for creating a canvas under a connector."""
    name: str
    description: Optional[str] = None
    is_enabled: bool = True


class CanvasUpdate(BaseModel):
    """Schema for partially updating a canvas.

    All fields are Optional -- omitted fields preserve existing values.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class CanvasResponse(BaseModel):
    """Schema for canvas API responses."""
    id: str
    connector_id: str
    name: str
    description: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
