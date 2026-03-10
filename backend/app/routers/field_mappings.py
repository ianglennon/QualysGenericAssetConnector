"""Field mapping CRUD and preview endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import require_role
from app.models.field_mapping import FieldMapping
from app.models.connector import Connector
from app.core.errors import make_error
from app.schemas.field_mapping import (
    BatchReplaceRequest,
    BatchReplaceResponse,
    FieldMappingCreate,
    FieldMappingResponse,
)
from app.services.validation import validate_connector_mappings
from app.services.preview import preview_mappings
import uuid

router = APIRouter()


@router.post("/connectors/{connector_id}/mappings", response_model=FieldMappingResponse)
def create_mapping(
    connector_id: str,
    mapping: FieldMappingCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Create a field mapping and validate connector."""
    # Create mapping
    new_mapping = FieldMapping(
        id=str(uuid.uuid4()),
        connector_id=connector_id,
        mapping_type=mapping.mapping_type,
        target_field=mapping.target_field,
        source_field=mapping.source_field,
        static_value=mapping.static_value,
        conditions=mapping.conditions,
        fallback=mapping.fallback,
        order=mapping.order,
    )
    db.add(new_mapping)
    
    # Validate and update connector
    is_valid, errors = validate_connector_mappings(connector_id, db)
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if connector:
        connector.is_valid_mappings = is_valid
    
    db.commit()
    db.refresh(new_mapping)
    return new_mapping


@router.get("/connectors/{connector_id}/mappings", response_model=list[FieldMappingResponse])
def list_mappings(
    connector_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin", "operator"))
):
    """List all mappings for a connector."""
    return db.query(FieldMapping).filter_by(connector_id=connector_id).order_by(FieldMapping.order).all()


@router.put("/connectors/{connector_id}/mappings", response_model=BatchReplaceResponse)
def batch_replace_mappings(
    connector_id: str,
    payload: BatchReplaceRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Atomically replace all field mappings for a connector.

    Deletes all existing mappings and inserts the provided set in a single
    transaction. Validates the new mapping set and updates is_valid_mappings
    on the connector before committing.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    # Transactional replace: delete all then insert all
    db.query(FieldMapping).filter_by(connector_id=connector_id).delete()
    for m in payload.mappings:
        db.add(FieldMapping(
            id=str(uuid.uuid4()),
            connector_id=connector_id,
            mapping_type=m.mapping_type,
            target_field=m.target_field,
            source_field=m.source_field,
            static_value=m.static_value,
            conditions=m.conditions,
            fallback=m.fallback,
            order=m.order,
        ))

    # Flush pending changes so the new rows are visible to the validation query
    # (session has autoflush=False so explicit flush is required before SELECT)
    db.flush()
    is_valid, errors = validate_connector_mappings(connector_id, db)
    connector.is_valid_mappings = is_valid

    # Single commit — if any prior step raised, nothing is persisted
    db.commit()

    return BatchReplaceResponse(
        replaced=len(payload.mappings),
        is_valid_mappings=is_valid,
        validation_errors=errors,
    )


@router.patch("/connectors/{connector_id}/mappings/{mapping_id}", response_model=FieldMappingResponse)
def update_mapping(
    connector_id: str,
    mapping_id: str,
    mapping: FieldMappingCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("admin"))
):
    """Update a field mapping."""
    db_mapping = db.query(FieldMapping).filter_by(id=mapping_id, connector_id=connector_id).first()
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
    
    # Revalidate connector
    is_valid, _ = validate_connector_mappings(connector_id, db)
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if connector:
        connector.is_valid_mappings = is_valid
    
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
    """Delete a mapping and revalidate connector."""
    mapping = db.query(FieldMapping).filter_by(id=mapping_id, connector_id=connector_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    db.delete(mapping)
    
    # Revalidate
    is_valid, _ = validate_connector_mappings(connector_id, db)
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if connector:
        connector.is_valid_mappings = is_valid
    
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
