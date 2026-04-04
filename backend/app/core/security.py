import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from pwdlib import PasswordHash

from app.core.settings import get_settings
from app.core.errors import make_error
from app.db.session import get_db

pwd_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# --- Password policy ---


def validate_password_policy(password: str) -> list[str]:
    """Returns list of failing rule descriptions. Empty list = valid."""
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters")
    if len(re.findall(r'\d', password)) < 2:
        errors.append("Password must contain at least 2 numbers")
    if not re.search(r'[^a-zA-Z0-9]', password):
        errors.append("Password must contain at least 1 non-alphanumeric character")
    return errors


# --- Password hashing ---


def hash_password(password: str) -> str:
    return pwd_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_hash.verify(plain, hashed)


# --- JWT ---


def create_access_token(subject: str, role: str, permissions: list[str]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "permissions": permissions, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, expire


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="AUTH_TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="AUTH_INVALID_TOKEN")


# --- RBAC dependency ---


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models.user import User
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="AUTH_INVALID_TOKEN")
    user = db.query(User).filter(User.id == payload["sub"], User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="AUTH_USER_NOT_FOUND")
    user.permissions = payload.get("permissions", [])
    return user


def require_role(*allowed_roles: str):
    """Returns a FastAPI dependency that enforces role membership.

    DEPRECATED: Phase 67 will replace with require_permission().
    Backward compat: 'admin' matches 'Administrator' role name.
    """
    def _inner(user=Depends(get_current_user)):
        role_name = user.role.name if hasattr(user.role, 'name') else str(user.role)
        # Backward compat mapping for Phase 66 transition
        effective_roles = set(allowed_roles)
        if "admin" in effective_roles:
            effective_roles.add("Administrator")
        if "operator" in effective_roles:
            effective_roles.add("Operator")
        if role_name not in effective_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AUTH_FORBIDDEN",
            )
        return user
    return _inner


def require_permission(permission: str):
    """FastAPI dependency enforcing a specific permission from JWT."""
    def _inner(user=Depends(get_current_user)):
        if permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=make_error("AUTH_FORBIDDEN", f"Missing permission: {permission}"),
            )
        return user
    _inner._permission_required = permission  # Tag for route introspection test (D-04)
    return _inner
