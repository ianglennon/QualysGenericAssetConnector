"""Preview service for field mappings."""

import httpx
from sqlalchemy.orm import Session
from app.models.connector import Connector
from app.models.field_mapping import FieldMapping
from app.services.connector_service import _build_headers
from app.services.transform_engine import apply_mappings
from app.schemas.field_mapping import (
    FieldMappingDirectCopy,
    FieldMappingStaticDefault,
    FieldMappingConditional,
    ConditionalMappingConfig,
    ConditionRule,
)
from app.services.validation import IDENTITY_ATTRIBUTES


def _convert_db_mapping_to_schema(db_mapping: FieldMapping):
    """Convert SQLAlchemy FieldMapping to Pydantic schema for apply_mappings."""
    if db_mapping.mapping_type == "direct_copy":
        return FieldMappingDirectCopy(
            target_field=db_mapping.target_field,
            source_field=db_mapping.source_field or "",
        )
    elif db_mapping.mapping_type == "static_default":
        return FieldMappingStaticDefault(
            target_field=db_mapping.target_field,
            static_value=db_mapping.static_value or "",
        )
    elif db_mapping.mapping_type == "conditional":
        # Build conditional config from JSON
        conditions_data = db_mapping.conditions or {"conditions": []}
        condition_rules = [
            ConditionRule(**c) for c in conditions_data.get("conditions", [])
        ]
        return FieldMappingConditional(
            target_field=db_mapping.target_field,
            conditional_config=ConditionalMappingConfig(
                conditions=condition_rules,
                fallback=db_mapping.fallback,
            ),
        )
    else:
        raise ValueError(f"Unknown mapping type: {db_mapping.mapping_type}")


async def preview_mappings(connector_id: str, db: Session) -> dict:
    """Fetch live sample from source and show 3-stage transformation.
    
    Returns:
    {
        "source": [...],  # Up to 10 raw source records
        "transformed": [...],  # After apply_mappings
        "qualys": [...],  # Qualys CSAM format
        "errors": [...]  # Per-record transformation errors
    }
    """
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if not connector:
        raise ValueError("Connector not found")
    
    mappings_db = db.query(FieldMapping).filter_by(connector_id=connector_id).order_by(FieldMapping.order).all()
    
    # Convert DB mappings to Pydantic schemas
    mappings = [_convert_db_mapping_to_schema(m) for m in mappings_db]
    
    # Fetch live sample (limit to 10 records per CONTEXT.md)
    headers = _build_headers(connector)
    test_url = f"{connector.base_url}/{connector.test_path or ''}"
    
    async with httpx.AsyncClient(timeout=30.0, verify=connector.verify_ssl) as client:
        response = await client.get(test_url, headers=headers)
        response.raise_for_status()
        source_data = response.json()
    
    # Extract records (assume list or {data: [...]} structure)
    if isinstance(source_data, list):
        source_records = source_data[:10]
    elif isinstance(source_data, dict) and "data" in source_data:
        source_records = source_data["data"][:10]
    else:
        source_records = [source_data]
    
    # Transform each record
    transformed_records = []
    qualys_records = []
    errors = []
    
    for idx, record in enumerate(source_records):
        try:
            transformed = apply_mappings(record, mappings)
            transformed_records.append(transformed)
            
            # Build Qualys CSAM format (simplified)
            qualys_record = {
                "identityAttributes": {},
                "coreAttributes": {}
            }
            for field, value in transformed.items():
                if field in IDENTITY_ATTRIBUTES:
                    qualys_record["identityAttributes"][field] = value
                qualys_record["coreAttributes"][field] = value
            
            qualys_records.append(qualys_record)
        except Exception as e:
            errors.append({
                "record_index": idx,
                "error": str(e)
            })
            transformed_records.append(None)
            qualys_records.append(None)
    
    return {
        "source": source_records,
        "transformed": transformed_records,
        "qualys": qualys_records,
        "errors": errors
    }
