"""Validation service for field mappings."""

from sqlalchemy.orm import Session
from app.models.field_mapping import FieldMapping

IDENTITY_ATTRIBUTES = {
    "qualysAssetId", "sourceNativeKey", "instanceUuid", "hostName",
    "netBiosName", "fqdn", "macAddress", "ipAddress", 
    "serialNumber", "hardwareUuid", "networkUuid"
}


def validate_connector_mappings(connector_id: str, db: Session) -> tuple[bool, list[str]]:
    """Validate connector has at least one identity attribute mapped.
    
    Returns: (is_valid, error_messages)
    
    Per CONTEXT.md:
    - At least ONE of 11 identity attributes must be mapped
    - Identity attributes must also appear in Core attributes
    - Error message includes full list of valid identity attributes
    """
    mappings = db.query(FieldMapping).filter_by(connector_id=connector_id).all()
    
    mapped_targets = {m.target_field for m in mappings}
    identity_mapped = mapped_targets & IDENTITY_ATTRIBUTES
    
    if not identity_mapped:
        attr_list = ", ".join(sorted(IDENTITY_ATTRIBUTES))
        return False, [f"Missing identity attribute. Valid identity attributes are: {attr_list}"]
    
    return True, []
