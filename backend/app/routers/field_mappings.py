"""Field mapping CRUD and preview endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import require_role
from app.models.field_mapping import FieldMapping
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.core.errors import make_error
from app.schemas.field_mapping import (
    BatchReplaceRequest,
    BatchReplaceResponse,
    FieldMappingCreate,
    FieldMappingResponse,
)
from app.services.preview import preview_mappings
from app.services.validation import validate_endpoint_mappings
import uuid

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoint-scoped routes (v1.2+)
# ---------------------------------------------------------------------------

@router.get(
    "/connectors/{connector_id}/endpoints/{endpoint_id}/mappings",
    response_model=list[FieldMappingResponse],
)
def list_endpoint_mappings(
    connector_id: str,
    endpoint_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin", "operator")),
):
    """List all mappings for a specific endpoint."""
    return (
        db.query(FieldMapping)
        .filter_by(endpoint_id=endpoint_id)
        .order_by(FieldMapping.order)
        .all()
    )


@router.put(
    "/connectors/{connector_id}/endpoints/{endpoint_id}/mappings",
    response_model=BatchReplaceResponse,
)
def batch_replace_endpoint_mappings(
    connector_id: str,
    endpoint_id: str,
    payload: BatchReplaceRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Atomically replace all field mappings for a specific endpoint.

    Validates the endpoint belongs to the connector, then deletes all existing
    mappings and inserts the provided set in a single transaction.
    """
    # Validate endpoint exists and belongs to connector
    endpoint = (
        db.query(ConnectorEndpoint)
        .filter_by(id=endpoint_id, connector_id=connector_id)
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "ENDPOINT_NOT_FOUND",
                "Endpoint not found",
                {"endpoint_id": endpoint_id, "connector_id": connector_id},
            ),
        )

    # Transactional replace: delete all then insert all
    db.query(FieldMapping).filter_by(endpoint_id=endpoint_id).delete()
    for m in payload.mappings:
        db.add(FieldMapping(
            id=str(uuid.uuid4()),
            endpoint_id=endpoint_id,
            mapping_type=m.mapping_type,
            target_field=m.target_field,
            source_field=m.source_field,
            static_value=m.static_value,
            conditions=m.conditions,
            fallback=m.fallback,
            order=m.order,
        ))

    # Single commit — if any prior step raised, nothing is persisted
    db.commit()

    is_valid, invalid_endpoints = validate_endpoint_mappings(connector_id, db)
    validation_errors = [ep["name"] for ep in invalid_endpoints]

    return BatchReplaceResponse(
        replaced=len(payload.mappings),
        is_valid_mappings=is_valid,
        validation_errors=validation_errors,
    )


# ---------------------------------------------------------------------------
# DEPRECATED: v1.1 connector-scoped routes — remove after v1.2 migration
# These routes are broken at DB level since FieldMapping has endpoint_id not
# connector_id. They remain temporarily to avoid breaking imports.
# ---------------------------------------------------------------------------

@router.post("/connectors/{connector_id}/mappings", response_model=FieldMappingResponse)
def create_mapping(
    connector_id: str,
    mapping: FieldMappingCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Create a field mapping. DEPRECATED: use endpoint-scoped routes."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use endpoint-scoped routes: /connectors/{connector_id}/endpoints/{endpoint_id}/mappings"),
    )


# DEPRECATED: v1.1 connector-scoped route — remove after v1.2 migration
@router.get("/connectors/{connector_id}/mappings", response_model=list[FieldMappingResponse])
def list_mappings(
    connector_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin", "operator"))
):
    """List all mappings for a connector. DEPRECATED: use endpoint-scoped routes."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use endpoint-scoped routes: /connectors/{connector_id}/endpoints/{endpoint_id}/mappings"),
    )


# DEPRECATED: v1.1 connector-scoped route — remove after v1.2 migration
@router.put("/connectors/{connector_id}/mappings", response_model=BatchReplaceResponse)
def batch_replace_mappings(
    connector_id: str,
    payload: BatchReplaceRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Atomically replace all field mappings for a connector. DEPRECATED: use endpoint-scoped routes."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use endpoint-scoped routes: /connectors/{connector_id}/endpoints/{endpoint_id}/mappings"),
    )


@router.patch("/connectors/{connector_id}/mappings/{mapping_id}", response_model=FieldMappingResponse)
def update_mapping(
    connector_id: str,
    mapping_id: str,
    mapping: FieldMappingCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Update a field mapping. DEPRECATED: use endpoint-scoped routes."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use endpoint-scoped routes: /connectors/{connector_id}/endpoints/{endpoint_id}/mappings"),
    )


@router.delete("/connectors/{connector_id}/mappings/{mapping_id}")
def delete_mapping(
    connector_id: str,
    mapping_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Delete a mapping. DEPRECATED: use endpoint-scoped routes."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use endpoint-scoped routes: /connectors/{connector_id}/endpoints/{endpoint_id}/mappings"),
    )


@router.post("/connectors/{connector_id}/mappings/preview")
async def preview_mapping_transform(
    connector_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Preview mapping transformation on live sample. DEPRECATED: use endpoint-scoped routes."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use endpoint-scoped routes: /connectors/{connector_id}/endpoints/{endpoint_id}/mappings"),
    )
