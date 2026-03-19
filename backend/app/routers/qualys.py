from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.qualys_config import QualysConfig
from app.schemas.qualys import QualysConfigCreate, QualysConfigResponse
from app.schemas.field_mapping import QualysSchemaField, QualysSchemaResponse
from app.services.credential_crypto import get_crypto
from app.core.security import require_role
from app.core.errors import make_error
from qualys_client.platform import detect_platform, derive_urls

router = APIRouter(prefix="/qualys", tags=["qualys"])

# ---------------------------------------------------------------------------
# Qualys CSAM target field constants
# Derived from qualys_formatter.identity_mappings (lines 87-99)
# ---------------------------------------------------------------------------
_IDENTITY_FIELDS = frozenset({
    "qualysAssetId", "sourceNativeKey", "instanceUuid",
    "hostName", "netBiosName", "fqdn", "macAddress", "ipAddress",
    "serialNumber", "hardwareUuid", "networkUuid",
})

# Core-only fields: keys from qualys_formatter.core_mappings minus those already
# in _IDENTITY_FIELDS (hostName, netBiosName, fqdn overlap — identity wins).
_CORE_ONLY_FIELDS = frozenset({
    "instanceUuidSource",
    "lastLoggedOnUser", "operatingSystem", "address", "dnsName",
    "isContainer", "domain", "osVersion", "osArchitecture", "domainRole",
})


def _to_response(config: QualysConfig) -> QualysConfigResponse:
    platform = detect_platform(config.username)
    api_server, api_gateway = derive_urls(platform)
    return QualysConfigResponse(
        id=config.id,
        username=config.username,
        connector_uuid=config.connector_uuid,
        has_password=bool(config.encrypted_password),
        platform_name=platform,
        api_server_url=api_server,
        api_gateway_url=api_gateway,
    )


@router.put("/config", response_model=QualysConfigResponse)
def upsert_qualys_config(
    payload: QualysConfigCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Create or replace Qualys subscription credentials. Credentials are encrypted before storage."""
    # Validate platform from username (CFG-01)
    try:
        detect_platform(payload.username)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=make_error(
                "QUALYS_INVALID_USERNAME",
                "Username does not contain a valid Qualys platform identifier",
            ),
        )

    crypto = get_crypto()

    # Upsert: only one config row allowed (singleton pattern)
    config = db.query(QualysConfig).first()
    if not config:
        config = QualysConfig()
        db.add(config)

    config.username = payload.username
    config.connector_uuid = payload.connector_uuid

    # Password required on first save (new config), optional on update
    if not config.encrypted_password and not payload.password:
        raise HTTPException(
            status_code=422,
            detail=make_error(
                "QUALYS_PASSWORD_REQUIRED",
                "Password is required for initial configuration",
            ),
        )
    if payload.password:
        config.encrypted_password = crypto.encrypt(payload.password)
    # else: keep existing encrypted_password

    db.commit()
    db.refresh(config)
    return _to_response(config)


@router.get("/config", response_model=QualysConfigResponse)
def get_qualys_config(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Retrieve current Qualys config. Never returns raw credentials."""
    config = db.query(QualysConfig).first()
    if not config:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "QUALYS_NOT_CONFIGURED",
                    "message": "Qualys credentials not configured",
                    "details": {},
                }
            },
        )
    return _to_response(config)


@router.get("/schema", response_model=QualysSchemaResponse)
def get_qualys_schema(_user=Depends(require_role("admin", "operator"))):
    """Return all Qualys CSAM target fields with is_identity flags.

    Identity fields are surfaced at the top of the visual canvas field panel
    and must be present for is_valid_mappings=true. Core-only fields follow.
    Total: 21 fields (11 identity + 10 core-only).
    """
    fields = (
        [QualysSchemaField(field=f, is_identity=True) for f in sorted(_IDENTITY_FIELDS)]
        + [QualysSchemaField(field=f, is_identity=False) for f in sorted(_CORE_ONLY_FIELDS)]
    )
    return QualysSchemaResponse(fields=fields)
