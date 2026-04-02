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
    canvas_id: str | None = None,
) -> tuple[bool, list[dict]]:
    """Validate that every leaf endpoint has at least one identity attribute mapped.

    When canvas_id is provided, only validates leaf endpoints within that canvas.
    When canvas_id is None (full connector sync), validates all enabled canvases
    plus orphan endpoints not in any canvas.

    Returns: (is_valid, invalid_endpoints)
        is_valid -- True if all relevant endpoints have an identity mapping.
        invalid_endpoints -- list of {id, name} dicts for each broken endpoint.
    """
    from app.models.canvas import Canvas
    from app.models.canvas_endpoint import CanvasEndpoint

    invalid_endpoints: list[dict] = []

    def _validate_leaf_endpoints(canvas_id_val: str) -> list[dict]:
        """Find leaf endpoints in a canvas and validate their identity mappings."""
        ces = db.query(CanvasEndpoint).filter(CanvasEndpoint.canvas_id == canvas_id_val).all()
        if not ces:
            return []
        # Build set of IDs that have children
        parent_ids = {ce.id for ce in ces if any(c.parent_ref_id == ce.id for c in ces)}
        leaf_ces = [ce for ce in ces if ce.id not in parent_ids]

        invalid: list[dict] = []
        for ce in leaf_ces:
            ep = db.query(ConnectorEndpoint).filter_by(id=ce.endpoint_id).first()
            if not ep:
                continue
            mappings = db.query(FieldMapping).filter(FieldMapping.endpoint_id == ep.id).all()
            mapped_targets = {m.target_field for m in mappings}
            if not (mapped_targets & IDENTITY_ATTRIBUTES):
                invalid.append({"id": ep.id, "name": ep.name})
        return invalid

    if canvas_id:
        # Single-canvas validation
        invalid_endpoints = _validate_leaf_endpoints(canvas_id)
    else:
        # Full connector: validate all enabled canvases + orphan endpoints
        canvases = (
            db.query(Canvas)
            .filter(Canvas.connector_id == connector_id, Canvas.is_enabled == True)
            .all()
        )
        for canvas in canvases:
            invalid_endpoints.extend(_validate_leaf_endpoints(canvas.id))

        # Also validate orphan endpoints (not in any canvas)
        canvas_ep_ids_q = (
            db.query(CanvasEndpoint.endpoint_id)
            .join(Canvas, CanvasEndpoint.canvas_id == Canvas.id)
            .filter(Canvas.connector_id == connector_id)
            .distinct()
        )
        referenced_ids = {row[0] for row in canvas_ep_ids_q.all()}

        orphan_endpoints = (
            db.query(ConnectorEndpoint)
            .filter(
                ConnectorEndpoint.connector_id == connector_id,
                ConnectorEndpoint.is_enabled == True,
                ~ConnectorEndpoint.id.in_(referenced_ids) if referenced_ids else True,
            )
            .all()
        )
        for ep in orphan_endpoints:
            mappings = db.query(FieldMapping).filter(FieldMapping.endpoint_id == ep.id).all()
            mapped_targets = {m.target_field for m in mappings}
            if not (mapped_targets & IDENTITY_ATTRIBUTES):
                invalid_endpoints.append({"id": ep.id, "name": ep.name})

    is_valid = len(invalid_endpoints) == 0
    return is_valid, invalid_endpoints


def validate_no_target_collisions(canvas_id: str, db: Session) -> list[dict]:
    """Check all endpoints in a canvas for duplicate Qualys target fields.

    Per D-01/D-03: duplicate target field mappings across endpoints in the
    same canvas are errors. Per D-02: identity fields follow the same rule.

    Returns list of collision dicts:
        [{"field": "hostName", "endpoints": ["Nodes", "VMs"]}]
    Empty list means no collisions.
    """
    from app.models.canvas_endpoint import CanvasEndpoint

    ces = db.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).all()
    if not ces:
        return []

    # Build: target_field -> set of connector_endpoint names
    target_sources: dict[str, list[str]] = {}
    for ce in ces:
        mappings = db.query(FieldMapping).filter_by(endpoint_id=ce.endpoint_id).all()
        ep = db.query(ConnectorEndpoint).filter_by(id=ce.endpoint_id).first()
        ep_label = ep.name if ep else str(ce.endpoint_id)
        for m in mappings:
            target_sources.setdefault(m.target_field, []).append(ep_label)

    return [
        {"field": field, "endpoints": sorted(set(sources))}
        for field, sources in target_sources.items()
        if len(set(sources)) > 1
    ]
