from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.qualys_config import QualysConfig
from app.schemas.qualys import QualysConfigCreate, QualysConfigResponse
from app.schemas.field_mapping import QualysSchemaField, QualysSchemaResponse
from app.services.credential_crypto import get_crypto
from app.core.security import require_role

router = APIRouter(prefix="/qualys", tags=["qualys"])

# ---------------------------------------------------------------------------
# Qualys CSAM target field constants
# Derived from qualys_formatter.identity_mappings (lines 87-99)
# ---------------------------------------------------------------------------
_IDENTITY_FIELDS = frozenset({
    "qualysAssetId", "sourceNativeKey", "instanceUuid", "instanceUuidSource",
    "hostName", "netBiosName", "fqdn", "macAddress", "ipAddress",
    "serialNumber", "hardwareUuid", "networkUuid",
})
# NOTE: instanceUuidSource appears in qualys_formatter.identity_mappings but NOT in
# validation.py IDENTITY_ATTRIBUTES (which has 11 fields). This is a pre-existing
# discrepancy. The schema endpoint uses the formatter as the authoritative source. A
# mapping targeting instanceUuidSource will show is_identity=true here but will NOT
# make is_valid_mappings=true. Track in Phase 9 or a follow-up.

# Core-only fields: keys from qualys_formatter.core_mappings minus those already
# in _IDENTITY_FIELDS (hostName, netBiosName, fqdn overlap — identity wins).
_CORE_ONLY_FIELDS = frozenset({
    "lastLoggedOnUser", "operatingSystem", "address", "dnsName",
    "isContainer", "domain", "osVersion", "osArchitecture", "domainRole",
})


def _to_response(config: QualysConfig) -> QualysConfigResponse:
    return QualysConfigResponse(
        id=config.id,
        api_url=config.api_url,
        username=config.username,
        connector_uuid=config.connector_uuid,
        has_password=bool(config.encrypted_password),
        has_token=bool(config.encrypted_token),
    )


@router.put("/config", response_model=QualysConfigResponse)
def upsert_qualys_config(
    payload: QualysConfigCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Create or replace Qualys subscription credentials. Credentials are encrypted before storage."""
    if not payload.password and not payload.token:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "QUALYS_MISSING_CREDENTIAL",
                    "message": "Either password or token must be provided",
                    "details": {},
                }
            },
        )

    crypto = get_crypto()

    # Upsert: only one config row allowed (singleton pattern)
    config = db.query(QualysConfig).first()
    if not config:
        config = QualysConfig()
        db.add(config)

    config.api_url = payload.api_url
    config.username = payload.username
    config.connector_uuid = payload.connector_uuid
    config.encrypted_password = crypto.encrypt(payload.password) if payload.password else None
    config.encrypted_token = crypto.encrypt(payload.token) if payload.token else None

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
    Total: 21 fields (12 identity + 9 core-only).
    """
    fields = (
        [QualysSchemaField(field=f, is_identity=True) for f in sorted(_IDENTITY_FIELDS)]
        + [QualysSchemaField(field=f, is_identity=False) for f in sorted(_CORE_ONLY_FIELDS)]
    )
    return QualysSchemaResponse(fields=fields)
