"""Validation service for field mappings.

Delegates to find_base_endpoint() for canvas-based validation.
A canvas is valid if it has a detectable base endpoint (an endpoint with
at least one identity attribute mapped). Full-connector validation checks
all enabled canvases.
"""

from sqlalchemy.orm import Session

from app.services.detection import find_base_endpoint, IDENTITY_ATTRIBUTES  # noqa: F401


def validate_endpoint_mappings(
    connector_id: str,
    db: Session,
    canvas_id: str | None = None,
) -> tuple[bool, list[dict]]:
    """Validate that canvases have a detectable base endpoint.

    When canvas_id is provided, only validates that single canvas.
    When canvas_id is None (full connector sync), validates all enabled canvases.

    Returns: (is_valid, invalid_endpoints)
        is_valid -- True if all relevant canvases have a valid base endpoint.
        invalid_endpoints -- list of {canvas_id, error} dicts for each invalid canvas.
    """
    from app.models.canvas import Canvas

    invalid_endpoints: list[dict] = []

    if canvas_id:
        # Single-canvas validation
        result = find_base_endpoint(canvas_id, db)
        if not result.is_valid:
            invalid_endpoints.append({
                "canvas_id": canvas_id,
                "error": result.error_message,
            })
    else:
        # Full connector: validate all enabled canvases
        canvases = (
            db.query(Canvas)
            .filter(Canvas.connector_id == connector_id, Canvas.is_enabled == True)
            .all()
        )
        for canvas in canvases:
            result = find_base_endpoint(canvas.id, db)
            if not result.is_valid:
                invalid_endpoints.append({
                    "canvas_id": canvas.id,
                    "error": result.error_message,
                })

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
