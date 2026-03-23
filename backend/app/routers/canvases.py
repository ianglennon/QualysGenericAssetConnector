"""Canvas CRUD router.

Routes mounted at /api/v1/connectors/{connector_id}/canvases.
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_role
from app.core.errors import make_error
from app.models.connector import Connector
from app.models.canvas import Canvas
from app.schemas.canvas import CanvasCreate, CanvasUpdate, CanvasResponse

router = APIRouter(tags=["canvases"])


@router.get(
    "/connectors/{connector_id}/canvases",
    response_model=list[CanvasResponse],
)
def list_canvases(
    connector_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """List all canvases for a connector ordered by name asc."""
    return (
        db.query(Canvas)
        .filter_by(connector_id=connector_id)
        .order_by(Canvas.name.asc())
        .all()
    )


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
    db.delete(canvas)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
