"""Base endpoint detection for canvas trees.

Determines which canvas endpoint is the "base" — the first endpoint with
identity-mapped fields found via BFS traversal ordered by tree_order.
The base endpoint determines Qualys record granularity.
"""

from collections import deque
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.services.validation import IDENTITY_ATTRIBUTES


@dataclass
class BaseDetectionResult:
    """Result of base endpoint detection."""
    base_canvas_endpoint_id: str | None = None
    is_valid: bool = False
    error_message: str | None = None
    ambiguous_endpoints: list[dict] = field(default_factory=list)


def find_base_endpoint(canvas_id: str, db: Session) -> BaseDetectionResult:
    """Find the base endpoint in a canvas tree via BFS by tree_order.

    The base endpoint is the first endpoint (BFS level-by-level) that has
    at least one identity attribute mapped. If multiple endpoints at the
    same BFS level have identity fields, an ambiguity error is returned.

    Returns a BaseDetectionResult with detection outcome.
    """
    # Query all canvas endpoints for this canvas
    canvas_endpoints = (
        db.query(CanvasEndpoint)
        .filter(CanvasEndpoint.canvas_id == canvas_id)
        .all()
    )

    if not canvas_endpoints:
        return BaseDetectionResult(
            is_valid=False,
            error_message=_no_identity_message(),
        )

    # Build children_map: parent_ref_id -> list of CanvasEndpoint sorted by tree_order
    children_map: dict[str | None, list[CanvasEndpoint]] = {}
    for ce in canvas_endpoints:
        children_map.setdefault(ce.parent_ref_id, []).append(ce)
    for key in children_map:
        children_map[key].sort(key=lambda ce: ce.tree_order)

    # BFS level-by-level starting from roots (parent_ref_id IS NULL)
    roots = children_map.get(None, [])
    if not roots:
        return BaseDetectionResult(
            is_valid=False,
            error_message=_no_identity_message(),
        )

    current_level: deque[CanvasEndpoint] = deque(roots)

    while current_level:
        # Check all endpoints at this level for identity mappings
        identity_endpoints: list[CanvasEndpoint] = []
        for ce in current_level:
            if _has_identity_mappings(ce.endpoint_id, db):
                identity_endpoints.append(ce)

        if len(identity_endpoints) == 1:
            # Exactly one endpoint at this level has identity mappings
            return BaseDetectionResult(
                base_canvas_endpoint_id=identity_endpoints[0].id,
                is_valid=True,
            )

        if len(identity_endpoints) > 1:
            # Same-level ambiguity (D-03)
            return BaseDetectionResult(
                is_valid=False,
                error_message=(
                    "Multiple endpoints at the same tree level have identity "
                    "fields mapped. Select which endpoint is the identity anchor."
                ),
                ambiguous_endpoints=[
                    {
                        "canvas_endpoint_id": ce.id,
                        "endpoint_id": ce.endpoint_id,
                    }
                    for ce in identity_endpoints
                ],
            )

        # No identity endpoints at this level — enqueue children
        next_level: deque[CanvasEndpoint] = deque()
        for ce in current_level:
            children = children_map.get(ce.id, [])
            next_level.extend(children)
        current_level = next_level

    # BFS exhausted all levels with no identity
    return BaseDetectionResult(
        is_valid=False,
        error_message=_no_identity_message(),
    )


def _has_identity_mappings(endpoint_id: str, db: Session) -> bool:
    """Check if an endpoint has at least one identity attribute mapped."""
    target_fields = (
        db.query(FieldMapping.target_field)
        .filter(FieldMapping.endpoint_id == endpoint_id)
        .all()
    )
    mapped_targets = {row[0] for row in target_fields}
    return bool(mapped_targets & IDENTITY_ATTRIBUTES)


def _no_identity_message() -> str:
    """Generate actionable error message for missing identity mappings."""
    fields = ", ".join(sorted(IDENTITY_ATTRIBUTES))
    return (
        f"Canvas cannot execute: no endpoint has identity fields mapped. "
        f"Map at least one of: {fields} to enable submission."
    )
