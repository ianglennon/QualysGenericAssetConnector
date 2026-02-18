from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.qualys_config import QualysConfig
from app.schemas.qualys import QualysConfigCreate, QualysConfigResponse
from app.services.credential_crypto import get_crypto
from app.core.security import require_role

router = APIRouter(prefix="/qualys", tags=["qualys"])


def _to_response(config: QualysConfig) -> QualysConfigResponse:
    return QualysConfigResponse(
        id=config.id,
        api_url=config.api_url,
        username=config.username,
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
