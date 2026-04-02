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
