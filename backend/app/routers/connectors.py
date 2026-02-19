from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.connector import Connector
from app.schemas.connector import ConnectorCreate, ConnectorUpdate, ConnectorResponse
from app.schemas.pagination import PaginationStrategy
from app.services.credential_crypto import get_crypto
from app.core.security import require_role
from app.core.errors import make_error

router = APIRouter(prefix="/connectors", tags=["connectors"])


def _to_response(connector: Connector) -> ConnectorResponse:
    """Map a Connector ORM row to a safe ConnectorResponse (no plaintext credentials)."""
    pagination_strategies = [
        PaginationStrategy.model_validate(s)
        for s in (connector.pagination_config or [])
    ]
    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        base_url=connector.base_url,
        test_path=connector.test_path,
        auth_method=connector.auth_method,
        has_token=bool(connector.encrypted_token),
        has_username=bool(connector.encrypted_username),
        has_password=bool(connector.encrypted_password),
        has_api_key=bool(connector.encrypted_api_key),
        api_key_name=connector.api_key_name,
        pagination_strategies=pagination_strategies,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


@router.post("/", response_model=ConnectorResponse, status_code=201)
def create_connector(
    payload: ConnectorCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Create a new connector. Credentials are encrypted before storage."""
    crypto = get_crypto()

    connector = Connector(
        name=payload.name,
        base_url=payload.base_url,
        test_path=payload.test_path,
        auth_method=payload.auth_method,
        pagination_config=[s.model_dump() for s in payload.pagination_strategies],
    )

    if payload.credentials:
        creds = payload.credentials
        if creds.token is not None:
            connector.encrypted_token = crypto.encrypt(creds.token)
        if creds.username is not None:
            connector.encrypted_username = crypto.encrypt(creds.username)
        if creds.password is not None:
            connector.encrypted_password = crypto.encrypt(creds.password)
        if creds.api_key_name is not None:
            connector.api_key_name = creds.api_key_name
        if creds.api_key is not None:
            connector.encrypted_api_key = crypto.encrypt(creds.api_key)

    db.add(connector)
    db.commit()
    db.refresh(connector)
    return _to_response(connector)


@router.get("/", response_model=list[ConnectorResponse])
def list_connectors(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """List all connectors. Never returns raw credentials."""
    connectors = db.query(Connector).all()
    return [_to_response(c) for c in connectors]


@router.get("/{connector_id}", response_model=ConnectorResponse)
def get_connector(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Get a single connector by ID. Returns 404 if not found."""
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )
    return _to_response(connector)


@router.patch("/{connector_id}", response_model=ConnectorResponse)
def update_connector(
    connector_id: str,
    payload: ConnectorUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Partially update a connector. Omitted credential fields preserve existing encrypted values."""
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    if payload.name is not None:
        connector.name = payload.name
    if payload.base_url is not None:
        connector.base_url = payload.base_url
    if payload.test_path is not None:
        connector.test_path = payload.test_path
    if payload.auth_method is not None:
        connector.auth_method = payload.auth_method
    if payload.pagination_strategies is not None:
        connector.pagination_config = [s.model_dump() for s in payload.pagination_strategies]

    if payload.credentials is not None:
        crypto = get_crypto()
        creds = payload.credentials
        # Only overwrite if the field value is not None — preserves existing encrypted values
        if creds.token is not None:
            connector.encrypted_token = crypto.encrypt(creds.token)
        if creds.username is not None:
            connector.encrypted_username = crypto.encrypt(creds.username)
        if creds.password is not None:
            connector.encrypted_password = crypto.encrypt(creds.password)
        if creds.api_key_name is not None:
            connector.api_key_name = creds.api_key_name
        if creds.api_key is not None:
            connector.encrypted_api_key = crypto.encrypt(creds.api_key)

    db.commit()
    db.refresh(connector)
    return _to_response(connector)


@router.delete("/{connector_id}", status_code=204)
def delete_connector(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Delete a connector. field_mappings for this connector are cascade-deleted at DB level."""
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    # TODO Phase 3: Activate this guard when RunHistory model exists
    # from app.models.run_history import RunHistory
    # active_run = db.query(RunHistory).filter(
    #     RunHistory.connector_id == connector_id,
    #     RunHistory.status == "running"
    # ).first()
    # if active_run:
    #     raise HTTPException(status_code=409, detail=make_error("CONNECTOR_RUN_IN_PROGRESS", "Cannot delete connector while a run is active", {}))

    db.delete(connector)
    db.commit()
