import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.schemas.connector import ConnectorCreate, ConnectorUpdate, ConnectorResponse
from app.schemas.field_mapping import DiscoverResponse
from app.services import source_client as _source_client
from app.services.connector_service import _build_headers, HTTPX_TIMEOUT, test_connector_connection
from app.services.credential_crypto import get_crypto
from app.services.field_discovery import auto_detect_data_root, merge_fields_across_records
from app.services.path_resolver import resolve_path as path_resolve
from app.core.security import require_role
from app.core.errors import make_error

router = APIRouter(prefix="/connectors", tags=["connectors"])


def _to_response(connector: Connector) -> ConnectorResponse:
    """Map a Connector ORM row to a safe ConnectorResponse (no plaintext credentials)."""
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
        source_retry_limit=connector.source_retry_limit,
        qualys_retry_limit=connector.qualys_retry_limit,
        has_valid_endpoints=bool(connector.is_valid_mappings),
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
        source_retry_limit=payload.source_retry_limit,
        qualys_retry_limit=payload.qualys_retry_limit,
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
    if payload.source_retry_limit is not None:
        connector.source_retry_limit = payload.source_retry_limit
    if payload.qualys_retry_limit is not None:
        connector.qualys_retry_limit = payload.qualys_retry_limit

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

    db.delete(connector)
    db.commit()


@router.post("/{connector_id}/test")
def run_test_connection(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Test connectivity to the source API for this connector. Returns metadata only — no body inspection."""
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {}),
        )
    return test_connector_connection(connector)


async def _discover_fields_from_url(
    connector: Connector,
    url: str,
    data_root: str | None = None,
) -> DiscoverResponse:
    """Shared helper: fetch first page from url and return discovered fields.

    When data_root is set, uses it to unwrap the response before flattening.
    When not set, auto-detects single-key wrapper objects containing arrays.
    """
    headers = _build_headers(connector)

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        fetch_result = await _source_client._fetch_with_retries(
            client,
            url,
            headers,
            None,
            retry_limit=1,
        )

    # _fetch_with_retries returns a FetchResult dataclass.
    # A None .response means the source API was unreachable / all retries failed.
    if fetch_result.response is None:
        raise HTTPException(
            status_code=502,
            detail=make_error("SOURCE_UNREACHABLE", "Source API did not respond", {}),
        )

    payload = fetch_result.response.json()

    # Apply data_root unwrapping or auto-detection (D-01, D-02, D-03)
    detected_data_root = None
    if data_root:
        unwrapped = path_resolve(payload, data_root) if isinstance(payload, dict) else None
        if isinstance(unwrapped, list):
            records = unwrapped
        else:
            records = _source_client._extract_records(payload)
    else:
        detected_data_root = auto_detect_data_root(payload)
        if detected_data_root:
            records = payload[detected_data_root]
        else:
            records = _source_client._extract_records(payload)

    if not records and isinstance(payload, dict):
        # Single-object response — treat the dict as one record
        records = [payload]

    if not records:
        return DiscoverResponse(fields=[], record_count=0)

    raw_fields = merge_fields_across_records(records)
    fields = [
        {
            "path": f["path"], "type": f["type"], "sample_value": f["sample_value"],
            "is_array_child": f.get("is_array_child"),
            "parent_array_path": f.get("parent_array_path"),
            "is_array_parent": f.get("is_array_parent"),
        }
        for f in raw_fields
    ]

    return DiscoverResponse(
        fields=fields,
        record_count=len(records),
        auto_detected_data_root=detected_data_root,
    )


@router.get("/{connector_id}/endpoints/{endpoint_id}/fields/discover", response_model=DiscoverResponse)
async def discover_endpoint_fields(
    connector_id: str,
    endpoint_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Discover available source fields for a specific endpoint.

    Fetches the first page of base_url + endpoint.path and returns a flat,
    typed field list with dot-notation paths. Supports nested objects (a.b.c),
    arrays of objects (items[0].ip), and arrays of primitives (tags: array).
    Recursion is capped at depth 5.

    Requires admin role. Returns 502 if the source API is unreachable.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

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

    # Compose full URL: base_url + endpoint.path
    url = connector.base_url.rstrip("/") + "/" + endpoint.path.lstrip("/")
    return await _discover_fields_from_url(connector, url, data_root=endpoint.data_root)


# DEPRECATED: v1.1 connector-level discover route — remove after v1.2 migration
# Use GET /connectors/{id}/endpoints/{endpoint_id}/fields/discover instead
@router.get("/{connector_id}/fields/discover", response_model=DiscoverResponse)
async def discover_fields(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """DEPRECATED: use endpoint-scoped GET /connectors/{id}/endpoints/{endpoint_id}/fields/discover."""
    raise HTTPException(
        status_code=410,
        detail=make_error("ROUTE_DEPRECATED", "This route has been removed. Use GET /connectors/{connector_id}/endpoints/{endpoint_id}/fields/discover"),
    )
