"""Pydantic schemas for CanvasEndpoint CRUD API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class CanvasEndpointCreate(BaseModel):
    """Schema for adding an endpoint reference to a canvas."""

    endpoint_id: str
    parent_ref_id: Optional[str] = None
    field_role: str = "data"
    variable_extractions: Optional[dict[str, str]] = None
    max_concurrency: int = 5
    tree_order: int = 0
    exclusion_rules: Optional[list[dict[str, Any]]] = None

    @field_validator("field_role")
    @classmethod
    def validate_field_role(cls, v: str) -> str:
        if v not in ("data", "iterator", "both"):
            raise ValueError("field_role must be 'data', 'iterator', or 'both'")
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_max_concurrency(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_concurrency must be >= 1")
        return v


class CanvasEndpointUpdate(BaseModel):
    """Schema for partially updating a canvas-endpoint reference.

    All fields are Optional -- omitted fields preserve existing values.
    """

    parent_ref_id: Optional[str] = None
    field_role: Optional[str] = None
    variable_extractions: Optional[dict[str, str]] = None
    max_concurrency: Optional[int] = None
    tree_order: Optional[int] = None
    exclusion_rules: Optional[list[dict[str, Any]]] = None

    @field_validator("field_role")
    @classmethod
    def validate_field_role(cls, v: str) -> str:
        if v is not None and v not in ("data", "iterator", "both"):
            raise ValueError("field_role must be 'data', 'iterator', or 'both'")
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_max_concurrency(cls, v: int) -> int:
        if v is not None and v < 1:
            raise ValueError("max_concurrency must be >= 1")
        return v


class CanvasEndpointResponse(BaseModel):
    """Schema for canvas-endpoint API responses."""

    id: str
    canvas_id: str
    endpoint_id: str
    parent_ref_id: Optional[str] = None
    field_role: str
    variable_extractions: Optional[dict[str, str]] = None
    max_concurrency: int
    tree_order: int
    exclusion_rules: Optional[list[dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
