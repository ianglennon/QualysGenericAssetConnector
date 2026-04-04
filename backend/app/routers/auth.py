from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse,
    MeResponse, RoleResponse,
)
from app.services.auth_service import authenticate_user, get_user_permissions
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    require_role, get_current_user,
)
from app.models.user import User
from app.models.role import Role
from app.core.errors import make_error

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
def get_me(
    user=Depends(require_role("admin", "operator")),
    db: Session = Depends(get_db),
):
    """Returns current user with role and permissions."""
    role = db.query(Role).filter(Role.id == user.role_id).first()
    permissions = [rp.permission for rp in role.permissions] if role else []
    return MeResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=RoleResponse(
            id=role.id,
            name=role.name,
            is_system=role.is_system,
            permissions=permissions,
        ) if role else RoleResponse(id="", name="Unknown", is_system=False, permissions=[]),
    )


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
    permissions = get_user_permissions(db, user)
    access_token = create_access_token(user.id, user.role.name, permissions)
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

    permissions = get_user_permissions(db, user)
    access_token = create_access_token(user.id, user.role.name, permissions)
    return AccessTokenResponse(access_token=access_token)
