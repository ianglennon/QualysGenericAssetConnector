"""Validation service for field mappings."""

from sqlalchemy.orm import Session
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping

IDENTITY_ATTRIBUTES = {
    "qualysAssetId", "sourceNativeKey", "instanceUuid", "hostName",
    "netBiosName", "fqdn", "macAddress", "ipAddress",
    "serialNumber", "hardwareUuid", "networkUuid"
}


def validate_endpoint_mappings(
    connector_id: str,
    db: Session,
) -> tuple[bool, list[dict]]:
    """Validate that every enabled endpoint has at least one identity attribute mapped.

    Returns: (is_valid, invalid_endpoints)
        is_valid — True if all enabled endpoints have an identity mapping.
        invalid_endpoints — list of {id, name} dicts for each broken enabled endpoint.
    """
    enabled_endpoints = (
        db.query(ConnectorEndpoint)
        .filter(
            ConnectorEndpoint.connector_id == connector_id,
            ConnectorEndpoint.is_enabled == True,
        )
        .all()
    )

    invalid_endpoints = []
    for endpoint in enabled_endpoints:
        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.endpoint_id == endpoint.id)
            .all()
        )
        mapped_targets = {m.target_field for m in mappings}
        if not (mapped_targets & IDENTITY_ATTRIBUTES):
            invalid_endpoints.append({"id": endpoint.id, "name": endpoint.name})

    is_valid = len(invalid_endpoints) == 0
    return is_valid, invalid_endpoints
