"""ConnectorEndpoint CRUD router.

Routes mounted at /api/v1/connectors/{connector_id}/endpoints.
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_role
from app.core.errors import make_error
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.schemas.endpoints import (
    EndpointCreate,
    EndpointUpdate,
    EndpointResponse,
    ReorderRequest,
)

router = APIRouter(tags=["endpoints"])


@router.get(
    "/connectors/{connector_id}/endpoints",
    response_model=list[EndpointResponse],
)
def list_endpoints(
    connector_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """List all endpoints for a connector ordered by display_order asc."""
    return (
        db.query(ConnectorEndpoint)
        .filter_by(connector_id=connector_id)
        .order_by(ConnectorEndpoint.display_order.asc())
        .all()
    )


@router.get(
    "/connectors/{connector_id}/endpoints/{endpoint_id}",
    response_model=EndpointResponse,
)
def get_endpoint(
    connector_id: str,
    endpoint_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Retrieve a single endpoint by ID scoped to connector."""
    endpoint = (
        db.query(ConnectorEndpoint)
        .filter_by(id=endpoint_id, connector_id=connector_id)
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=make_error("ENDPOINT_NOT_FOUND", "Endpoint not found", {"endpoint_id": endpoint_id}),
        )
    return endpoint


@router.post(
    "/connectors/{connector_id}/endpoints",
    response_model=EndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_endpoint(
    connector_id: str,
    payload: EndpointCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Create a new endpoint under a connector. 404 if connector not found."""
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )
    endpoint = ConnectorEndpoint(
        id=str(_uuid.uuid4()),
        connector_id=connector_id,
        name=payload.name,
        path=payload.path,
        pagination_config=payload.pagination_config,
        is_enabled=payload.is_enabled,
        display_order=payload.display_order,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.patch(
    "/connectors/{connector_id}/endpoints/{endpoint_id}",
    response_model=EndpointResponse,
)
def update_endpoint(
    connector_id: str,
    endpoint_id: str,
    payload: EndpointUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Partially update an endpoint. Only provided fields are updated."""
    endpoint = (
        db.query(ConnectorEndpoint)
        .filter_by(id=endpoint_id, connector_id=connector_id)
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=make_error("ENDPOINT_NOT_FOUND", "Endpoint not found", {"endpoint_id": endpoint_id}),
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(endpoint, field, value)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.delete(
    "/connectors/{connector_id}/endpoints/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_endpoint(
    connector_id: str,
    endpoint_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Delete an endpoint. Returns 204 No Content."""
    endpoint = (
        db.query(ConnectorEndpoint)
        .filter_by(id=endpoint_id, connector_id=connector_id)
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=make_error("ENDPOINT_NOT_FOUND", "Endpoint not found", {"endpoint_id": endpoint_id}),
        )
    db.delete(endpoint)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/connectors/{connector_id}/endpoints/reorder",
    response_model=list[EndpointResponse],
)
def reorder_endpoints(
    connector_id: str,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Bulk-update display_order for endpoints by ID list order.

    Iterates payload.order, sets display_order=idx (0-based) for each endpoint
    scoped to connector_id. IDs not found in this connector are silently skipped.
    Returns the updated list ordered by display_order.
    """
    for idx, endpoint_id in enumerate(payload.order):
        endpoint = (
            db.query(ConnectorEndpoint)
            .filter_by(id=endpoint_id, connector_id=connector_id)
            .first()
        )
        if endpoint:
            endpoint.display_order = idx
    db.commit()
    return (
        db.query(ConnectorEndpoint)
        .filter_by(connector_id=connector_id)
        .order_by(ConnectorEndpoint.display_order.asc())
        .all()
    )
