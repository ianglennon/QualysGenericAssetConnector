"""Field mapping CRUD and preview endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import require_role
from app.models.field_mapping import FieldMapping
from app.models.connector import Connector
from app.schemas.field_mapping import FieldMappingCreate, FieldMappingResponse
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
