"""CanvasEndpoint CRUD router with tree validation.

Routes mounted at /api/v1/connectors/{connector_id}/canvases/{canvas_id}/endpoints.
Provides cycle detection (D-11) and orphan detection (D-12).
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_role
from app.core.errors import make_error
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector_endpoint import ConnectorEndpoint
from app.schemas.canvas_endpoint import (
    CanvasEndpointCreate,
    CanvasEndpointUpdate,
    CanvasEndpointResponse,
)

router = APIRouter(tags=["canvas-endpoints"])

BASE = "/connectors/{connector_id}/canvases/{canvas_id}/endpoints"


def detect_cycle(
    canvas_endpoints: list[CanvasEndpoint],
    new_ref_id: str,
    new_parent_id: str,
) -> bool:
    """Walk up parent chain from new_ref_id using the proposed parent change.

    If we revisit a node, a cycle exists. Returns True if cycle detected.
    """
    parent_map = {ce.id: ce.parent_ref_id for ce in canvas_endpoints}
    parent_map[new_ref_id] = new_parent_id
    visited: set[str] = set()
    current: str | None = new_ref_id
    while current is not None:
        if current in visited:
            return True
        visited.add(current)
        current = parent_map.get(current)
    return False


def find_orphans(canvas_endpoints: list[CanvasEndpoint]) -> list[str]:
    """Find canvas-endpoint IDs that are disconnected from any tree root.

    A root is a canvas-endpoint with parent_ref_id=None.
    An orphan is a node not reachable from any root via parent chain traversal.
    """
    if not canvas_endpoints:
        return []

    # Build child map: parent_id -> list of child ids
    child_map: dict[str | None, list[str]] = {}
    all_ids: set[str] = set()
    for ce in canvas_endpoints:
        all_ids.add(ce.id)
        child_map.setdefault(ce.parent_ref_id, []).append(ce.id)

    # BFS from all roots (parent_ref_id=None)
    reachable: set[str] = set()
    roots = child_map.get(None, [])
    queue = list(roots)
    while queue:
        node = queue.pop(0)
        if node in reachable:
            continue
        reachable.add(node)
        for child in child_map.get(node, []):
            queue.append(child)

    return sorted(all_ids - reachable)


def _get_canvas_or_404(
    db: Session, connector_id: str, canvas_id: str
) -> Canvas:
    """Fetch canvas scoped to connector, raise 404 if not found."""
    canvas = (
        db.query(Canvas)
        .filter_by(id=canvas_id, connector_id=connector_id)
        .first()
    )
    if not canvas:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_NOT_FOUND",
                "Canvas not found",
                {"canvas_id": canvas_id},
            ),
        )
    return canvas


@router.get(BASE + "/validate")
def validate_canvas_tree(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Validate the endpoint tree for a canvas.

    Returns whether the tree is valid (exactly 1 root, no orphans).
    """
    _get_canvas_or_404(db, connector_id, canvas_id)
    refs = (
        db.query(CanvasEndpoint)
        .filter_by(canvas_id=canvas_id)
        .all()
    )
    roots = [ce for ce in refs if ce.parent_ref_id is None]
    orphans = find_orphans(refs)
    return {
        "valid": len(roots) == 1 and len(orphans) == 0,
        "orphaned_refs": orphans,
        "root_count": len(roots),
    }


@router.get(BASE, response_model=list[CanvasEndpointResponse])
def list_canvas_endpoints(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """List all canvas-endpoint references for a canvas, ordered by tree_order."""
    _get_canvas_or_404(db, connector_id, canvas_id)
    return (
        db.query(CanvasEndpoint)
        .filter_by(canvas_id=canvas_id)
        .order_by(CanvasEndpoint.tree_order.asc())
        .all()
    )


@router.get(BASE + "/{ref_id}", response_model=CanvasEndpointResponse)
def get_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Retrieve a single canvas-endpoint reference."""
    _get_canvas_or_404(db, connector_id, canvas_id)
    ref = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )
    return ref


@router.post(
    BASE,
    response_model=CanvasEndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    payload: CanvasEndpointCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Add an endpoint reference to a canvas.

    Validates: canvas exists, endpoint exists for this connector,
    parent_ref_id exists in same canvas, no circular reference.
    """
    canvas = _get_canvas_or_404(db, connector_id, canvas_id)

    # Validate endpoint belongs to this connector
    endpoint = (
        db.query(ConnectorEndpoint)
        .filter_by(id=payload.endpoint_id, connector_id=connector_id)
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "ENDPOINT_NOT_FOUND",
                "Connector endpoint not found or does not belong to this connector",
                {"endpoint_id": payload.endpoint_id},
            ),
        )

    # Validate parent_ref_id if specified
    if payload.parent_ref_id is not None:
        parent_ref = (
            db.query(CanvasEndpoint)
            .filter_by(id=payload.parent_ref_id, canvas_id=canvas_id)
            .first()
        )
        if not parent_ref:
            raise HTTPException(
                status_code=404,
                detail=make_error(
                    "PARENT_REF_NOT_FOUND",
                    "Parent canvas endpoint reference not found in this canvas",
                    {"parent_ref_id": payload.parent_ref_id},
                ),
            )

    new_id = str(_uuid.uuid4())

    # Check for circular reference if parent is set
    if payload.parent_ref_id is not None:
        existing_refs = (
            db.query(CanvasEndpoint)
            .filter_by(canvas_id=canvas_id)
            .all()
        )
        if detect_cycle(existing_refs, new_id, payload.parent_ref_id):
            raise HTTPException(
                status_code=409,
                detail=make_error(
                    "CIRCULAR_REFERENCE",
                    "Adding this parent reference would create a circular dependency",
                ),
            )

    ref = CanvasEndpoint(
        id=new_id,
        canvas_id=canvas_id,
        endpoint_id=payload.endpoint_id,
        parent_ref_id=payload.parent_ref_id,
        field_role=payload.field_role,
        variable_extractions=payload.variable_extractions,
        max_concurrency=payload.max_concurrency,
        tree_order=payload.tree_order,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    # Check for orphans after creation and include warning if found
    all_refs = (
        db.query(CanvasEndpoint)
        .filter_by(canvas_id=canvas_id)
        .all()
    )
    orphans = find_orphans(all_refs)
    if orphans:
        response_data = CanvasEndpointResponse.model_validate(ref).model_dump()
        response_data["warnings"] = {"orphaned_refs": orphans}
        return response_data

    return ref


@router.patch(
    BASE + "/{ref_id}",
    response_model=CanvasEndpointResponse,
)
def update_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    payload: CanvasEndpointUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Update a canvas-endpoint reference. Cycle detection on parent change."""
    _get_canvas_or_404(db, connector_id, canvas_id)
    ref = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )

    updates = payload.model_dump(exclude_unset=True)

    # If parent_ref_id is changing, validate and check cycle
    if "parent_ref_id" in updates and updates["parent_ref_id"] is not None:
        parent_ref = (
            db.query(CanvasEndpoint)
            .filter_by(id=updates["parent_ref_id"], canvas_id=canvas_id)
            .first()
        )
        if not parent_ref:
            raise HTTPException(
                status_code=404,
                detail=make_error(
                    "PARENT_REF_NOT_FOUND",
                    "Parent canvas endpoint reference not found in this canvas",
                    {"parent_ref_id": updates["parent_ref_id"]},
                ),
            )

        existing_refs = (
            db.query(CanvasEndpoint)
            .filter_by(canvas_id=canvas_id)
            .all()
        )
        if detect_cycle(existing_refs, ref_id, updates["parent_ref_id"]):
            raise HTTPException(
                status_code=409,
                detail=make_error(
                    "CIRCULAR_REFERENCE",
                    "Adding this parent reference would create a circular dependency",
                ),
            )

    for field, value in updates.items():
        setattr(ref, field, value)
    db.commit()
    db.refresh(ref)
    return ref


@router.delete(
    BASE + "/{ref_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Remove an endpoint reference from a canvas.

    Children are orphaned (parent_ref_id SET NULL) by the FK constraint.
    """
    _get_canvas_or_404(db, connector_id, canvas_id)
    ref = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )
    db.delete(ref)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
