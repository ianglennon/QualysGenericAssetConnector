import secrets
import string
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.role import Role, RolePermission
from app.core.security import hash_password, validate_password_policy
from app.core.errors import make_error
from app.core.permissions import VALID_PERMISSIONS


def generate_temp_password(length: int = 16) -> str:
    """Generate a cryptographically secure password meeting policy requirements."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not validate_password_policy(password):
            return password


def check_last_admin_guard(db: Session, user_id: str, new_role_id: str | None = None) -> None:
    """Raises 409 if operation would leave zero active system admins (per D-14, D-15, D-16)."""
    admin_count = (
        db.query(User)
        .join(Role)
        .filter(Role.is_system == True, User.is_active == True, User.id != user_id)
        .with_for_update()
        .count()
    )
    if admin_count == 0:
        if new_role_id:
            target_role = db.query(Role).filter(Role.id == new_role_id).first()
            if target_role and target_role.is_system:
                return  # Reassigning to another system role is fine
        raise HTTPException(
            status_code=409,
            detail=make_error("USER_LAST_ADMIN", "Cannot remove the last Administrator"),
        )


def create_user_account(db: Session, email: str, role_id: str) -> tuple[User, str]:
    """Create user with system-generated temp password (per D-06). Returns (user, temp_password)."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=make_error("USER_EMAIL_EXISTS", "A user with this email already exists"),
        )
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=404,
            detail=make_error("ROLE_NOT_FOUND", "Role not found"),
        )
    temp_password = generate_temp_password()
    user = User(
        email=email,
        hashed_password=hash_password(temp_password),
        role_id=role_id,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, temp_password


def update_user_account(db: Session, user_id: str, current_user_id: str, **updates) -> User:
    """Update user with lockout guards (per D-08, D-09, D-14, D-15)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=make_error("USER_NOT_FOUND", "User not found"))

    # D-09: self-deactivation check
    if updates.get("is_active") is False and user_id == current_user_id:
        raise HTTPException(
            status_code=409,
            detail=make_error("USER_SELF_DEACTIVATE", "Cannot deactivate your own account"),
        )

    # D-14/D-15: last admin guard on deactivation
    if updates.get("is_active") is False:
        check_last_admin_guard(db, user_id)

    # D-15: last admin guard on role reassignment
    if "role_id" in updates and updates["role_id"] is not None and updates["role_id"] != user.role_id:
        check_last_admin_guard(db, user_id, new_role_id=updates["role_id"])
        role = db.query(Role).filter(Role.id == updates["role_id"]).first()
        if not role:
            raise HTTPException(status_code=404, detail=make_error("ROLE_NOT_FOUND", "Role not found"))

    if "email" in updates and updates["email"] is not None:
        existing = db.query(User).filter(User.email == updates["email"], User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=make_error("USER_EMAIL_EXISTS", "A user with this email already exists"),
            )
        user.email = updates["email"]

    if "role_id" in updates and updates["role_id"] is not None:
        user.role_id = updates["role_id"]

    if "is_active" in updates and updates["is_active"] is not None:
        user.is_active = updates["is_active"]
        # D-08: clear refresh token on deactivation
        if not updates["is_active"]:
            user.refresh_token = None
            user.refresh_token_expires_at = None

    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: str, current_user_id: str) -> User:
    """Dedicated deactivation path (per D-08, D-09)."""
    return update_user_account(db, user_id, current_user_id, is_active=False)
