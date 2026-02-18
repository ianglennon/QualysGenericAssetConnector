from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse
from app.services.auth_service import authenticate_user
from app.core.security import (
    create_access_token, create_refresh_token, decode_token, require_role
)
from app.models.user import User
from app.core.errors import make_error

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def get_me(_admin=Depends(require_role("admin", "operator"))):
    """Returns current user. Both admin and operator can access.
    Used as a health-check for valid tokens and for RBAC testing."""
    return {"id": _admin.id, "email": _admin.email, "role": _admin.role}


@router.get("/admin-only")
def admin_only_endpoint(_admin=Depends(require_role("admin"))):
    """Admin-only test endpoint. Used in tests to verify RBAC blocks operators."""
    return {"status": "ok", "role": "admin"}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail=make_error("AUTH_INVALID_CREDENTIALS", "Invalid email or password"),
        )
    access_token = create_access_token(user.id, user.role)
    refresh_token, refresh_expires = create_refresh_token(user.id)
    # Store refresh token in DB (rotate on use)
    user.refresh_token = refresh_token
    user.refresh_token_expires_at = refresh_expires
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except HTTPException:
        raise HTTPException(status_code=401, detail=make_error("AUTH_INVALID_TOKEN", "Invalid or expired refresh token"))

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail=make_error("AUTH_INVALID_TOKEN", "Not a refresh token"))

    user = db.query(User).filter(User.id == decoded["sub"], User.is_active == True).first()
    if not user or user.refresh_token != payload.refresh_token:
        raise HTTPException(status_code=401, detail=make_error("AUTH_INVALID_TOKEN", "Refresh token revoked or not found"))

    if user.refresh_token_expires_at and user.refresh_token_expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail=make_error("AUTH_TOKEN_EXPIRED", "Refresh token expired"))

    access_token = create_access_token(user.id, user.role)
    return AccessTokenResponse(access_token=access_token)
