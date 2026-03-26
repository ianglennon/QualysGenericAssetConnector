"""Pydantic schemas for ConnectorEndpoint CRUD API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EndpointCreate(BaseModel):
    """Schema for creating a connector endpoint."""
    name: str
    path: str
    pagination_config: Optional[dict] = None
    is_enabled: bool = True
    display_order: int = 0
    data_root: Optional[str] = None


class EndpointUpdate(BaseModel):
    """Schema for partially updating a connector endpoint.

    All fields are Optional — omitted fields preserve existing values.
    """
    name: Optional[str] = None
    path: Optional[str] = None
    pagination_config: Optional[dict] = None
    is_enabled: Optional[bool] = None
    display_order: Optional[int] = None
    data_root: Optional[str] = None


class EndpointResponse(BaseModel):
    """Schema for connector endpoint API responses."""
    id: str
    connector_id: str
    name: str
    path: str
    pagination_config: Optional[dict] = None
    is_enabled: bool
    display_order: int
    data_root: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReorderRequest(BaseModel):
    """Request body for POST /connectors/{id}/endpoints/reorder.

    order: list of endpoint IDs in desired display_order (0-indexed).
    """
    order: list[str]
