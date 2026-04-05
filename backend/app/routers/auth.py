from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse,
    MeResponse, RoleResponse, PasswordChangeRequest, PasswordChangeResponse,
)
from app.services.auth_service import authenticate_user, get_user_permissions
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    get_current_user, verify_password, hash_password, validate_password_policy,
)
from app.models.user import User
from app.models.role import Role
from app.core.errors import make_error

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
def get_me(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns current user with role and permissions."""
    role = db.query(Role).filter(Role.id == user.role_id).first()
    permissions = [rp.permission for rp in role.permissions] if role else []
    return MeResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        role=RoleResponse(
            id=role.id,
            name=role.name,
            is_system=role.is_system,
            permissions=permissions,
        ) if role else RoleResponse(id="", name="Unknown", is_system=False, permissions=[]),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail=make_error("AUTH_INVALID_CREDENTIALS", "Invalid email or password"),
        )
    permissions = get_user_permissions(db, user)
    access_token = create_access_token(user.id, user.role.name, permissions, must_change_password=user.must_change_password)
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
    access_token = create_access_token(user.id, user.role.name, permissions, must_change_password=user.must_change_password)
    return AccessTokenResponse(access_token=access_token)


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change own password. Requires current password verification (per D-06, USER-06)."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail=make_error("AUTH_WRONG_PASSWORD", "Current password is incorrect"),
        )
    policy_errors = validate_password_policy(payload.new_password)
    if policy_errors:
        raise HTTPException(
            status_code=422,
            detail=make_error("AUTH_PASSWORD_POLICY", "Password does not meet policy requirements",
                              {"violations": policy_errors}),
        )
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()

    # Issue new token pair with must_change_password=false
    permissions = get_user_permissions(db, user)
    access_token = create_access_token(user.id, user.role.name, permissions, must_change_password=False)
    refresh_token, refresh_expires = create_refresh_token(user.id)
    user.refresh_token = refresh_token
    user.refresh_token_expires_at = refresh_expires
    db.commit()

    return PasswordChangeResponse(access_token=access_token, refresh_token=refresh_token)
