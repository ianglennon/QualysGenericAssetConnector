"""Canvas CRUD router.

Routes mounted at /api/v1/connectors/{connector_id}/canvases.
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_role
from app.core.errors import make_error
from app.models.connector import Connector
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.run_history import EndpointRunLog
from app.schemas.canvas import CanvasCreate, CanvasUpdate, CanvasResponse, CanvasListResponse

router = APIRouter(tags=["canvases"])


@router.get(
    "/connectors/{connector_id}/canvases",
    response_model=list[CanvasListResponse],
)
def list_canvases(
    connector_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """List all canvases for a connector with aggregation fields."""
    canvases = (
        db.query(Canvas)
        .filter_by(connector_id=connector_id)
        .order_by(Canvas.name.asc())
        .all()
    )

    canvas_ids = [c.id for c in canvases]

    # Endpoint counts per canvas
    ep_counts = dict(
        db.query(CanvasEndpoint.canvas_id, func.count(CanvasEndpoint.id))
        .filter(CanvasEndpoint.canvas_id.in_(canvas_ids))
        .group_by(CanvasEndpoint.canvas_id)
        .all()
    ) if canvas_ids else {}

    # Field mapping counts per canvas
    fm_counts = dict(
        db.query(FieldMapping.canvas_id, func.count(FieldMapping.id))
        .filter(FieldMapping.canvas_id.in_(canvas_ids))
        .group_by(FieldMapping.canvas_id)
        .all()
    ) if canvas_ids else {}

    # Last run status per canvas (most recent EndpointRunLog)
    last_runs: dict[str, tuple] = {}
    if canvas_ids:
        for cid in canvas_ids:
            last_log = (
                db.query(EndpointRunLog)
                .filter(EndpointRunLog.canvas_id == cid)
                .order_by(desc(EndpointRunLog.created_at))
                .first()
            )
            if last_log:
                last_runs[cid] = (last_log.status, last_log.created_at)

    return [
        CanvasListResponse(
            id=c.id,
            connector_id=c.connector_id,
            name=c.name,
            description=c.description,
            is_enabled=c.is_enabled,
            endpoint_count=ep_counts.get(c.id, 0),
            field_mapping_count=fm_counts.get(c.id, 0),
            last_run_status=last_runs.get(c.id, (None, None))[0],
            last_run_at=last_runs.get(c.id, (None, None))[1],
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in canvases
    ]


@router.get(
    "/connectors/{connector_id}/canvases/{canvas_id}",
    response_model=CanvasResponse,
)
def get_canvas(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Retrieve a single canvas by ID scoped to connector."""
    canvas = (
        db.query(Canvas)
        .filter_by(id=canvas_id, connector_id=connector_id)
        .first()
    )
    if not canvas:
        raise HTTPException(
            status_code=404,
            detail=make_error("CANVAS_NOT_FOUND", "Canvas not found", {"canvas_id": canvas_id}),
        )
    return canvas


@router.post(
    "/connectors/{connector_id}/canvases",
    response_model=CanvasResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_canvas(
    connector_id: str,
    payload: CanvasCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Create a new canvas under a connector. 404 if connector not found."""
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )
    canvas = Canvas(
        id=str(_uuid.uuid4()),
        connector_id=connector_id,
        name=payload.name,
        description=payload.description,
        is_enabled=payload.is_enabled,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.patch(
    "/connectors/{connector_id}/canvases/{canvas_id}",
    response_model=CanvasResponse,
)
def update_canvas(
    connector_id: str,
    canvas_id: str,
    payload: CanvasUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Partially update a canvas. Only provided fields are updated."""
    canvas = (
        db.query(Canvas)
        .filter_by(id=canvas_id, connector_id=connector_id)
        .first()
    )
    if not canvas:
        raise HTTPException(
            status_code=404,
            detail=make_error("CANVAS_NOT_FOUND", "Canvas not found", {"canvas_id": canvas_id}),
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(canvas, field, value)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.delete(
    "/connectors/{connector_id}/canvases/{canvas_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_canvas(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Delete a canvas. Returns 204 No Content."""
    canvas = (
        db.query(Canvas)
        .filter_by(id=canvas_id, connector_id=connector_id)
        .first()
    )
    if not canvas:
        raise HTTPException(
            status_code=404,
            detail=make_error("CANVAS_NOT_FOUND", "Canvas not found", {"canvas_id": canvas_id}),
        )

    # -- Explicit cleanup (belt-and-suspenders over CASCADE) --

    # 1. Collect endpoint IDs assigned to this canvas
    canvas_eps = db.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).all()
    endpoint_ids = [ce.endpoint_id for ce in canvas_eps]

    # 2. Delete field mappings scoped to this canvas
    db.query(FieldMapping).filter_by(canvas_id=canvas_id).delete(synchronize_session="fetch")

    # 3. Delete canvas_endpoint join records for this canvas
    db.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).delete(synchronize_session="fetch")

    # 4. Delete unshared ConnectorEndpoints (not referenced by other canvases)
    for ep_id in endpoint_ids:
        remaining = db.query(CanvasEndpoint).filter_by(endpoint_id=ep_id).count()
        if remaining == 0:
            db.query(EndpointRunLog).filter_by(endpoint_id=ep_id).delete(synchronize_session="fetch")
            db.query(FieldMapping).filter_by(endpoint_id=ep_id).delete(synchronize_session="fetch")
            ep = db.query(ConnectorEndpoint).get(ep_id)
            if ep:
                db.delete(ep)

    # 5. Delete the canvas itself
    db.delete(canvas)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
