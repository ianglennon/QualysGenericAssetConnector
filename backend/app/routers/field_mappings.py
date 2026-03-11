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

    return BatchReplaceResponse(
        replaced=len(payload.mappings),
        is_valid_mappings=False,
        validation_errors=[],
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
    # Create mapping
    new_mapping = FieldMapping(
        id=str(uuid.uuid4()),
        mapping_type=mapping.mapping_type,
        target_field=mapping.target_field,
        source_field=mapping.source_field,
        static_value=mapping.static_value,
        conditions=mapping.conditions,
        fallback=mapping.fallback,
        order=mapping.order,
    )
    db.add(new_mapping)
    db.commit()
    db.refresh(new_mapping)
    return new_mapping


# DEPRECATED: v1.1 connector-scoped route — remove after v1.2 migration
@router.get("/connectors/{connector_id}/mappings", response_model=list[FieldMappingResponse])
def list_mappings(
    connector_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin", "operator"))
):
    """List all mappings for a connector. DEPRECATED: use endpoint-scoped routes."""
    return []


# DEPRECATED: v1.1 connector-scoped route — remove after v1.2 migration
@router.put("/connectors/{connector_id}/mappings", response_model=BatchReplaceResponse)
def batch_replace_mappings(
    connector_id: str,
    payload: BatchReplaceRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Atomically replace all field mappings for a connector. DEPRECATED: use endpoint-scoped routes."""
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    return BatchReplaceResponse(
        replaced=0,
        is_valid_mappings=False,
        validation_errors=["DEPRECATED: use endpoint-scoped PUT route"],
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
    db_mapping = db.query(FieldMapping).filter_by(id=mapping_id).first()
    if not db_mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    # Update fields
    db_mapping.mapping_type = mapping.mapping_type
    db_mapping.target_field = mapping.target_field
    db_mapping.source_field = mapping.source_field
    db_mapping.static_value = mapping.static_value
    db_mapping.conditions = mapping.conditions
    db_mapping.fallback = mapping.fallback
    db_mapping.order = mapping.order

    db.commit()
    db.refresh(db_mapping)
    return db_mapping


@router.delete("/connectors/{connector_id}/mappings/{mapping_id}")
def delete_mapping(
    connector_id: str,
    mapping_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Delete a mapping. DEPRECATED: use endpoint-scoped routes."""
    mapping = db.query(FieldMapping).filter_by(id=mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    db.delete(mapping)
    db.commit()
    return {"status": "deleted"}


@router.post("/connectors/{connector_id}/mappings/preview")
async def preview_mapping_transform(
    connector_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Preview mapping transformation on live sample."""
    return await preview_mappings(connector_id, db)
