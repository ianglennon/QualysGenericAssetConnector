from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_password, verify_password, validate_password_policy
from fastapi import HTTPException


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, email: str, password: str, role_id: str) -> User:
    policy_errors = validate_password_policy(password)
    if policy_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AUTH_PASSWORD_POLICY",
                "message": "Password does not meet requirements",
                "details": {"errors": policy_errors},
            },
        )
    user = User(email=email, hashed_password=hash_password(password), role_id=role_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_permissions(db: Session, user: User) -> list[str]:
    """Get the effective permission strings for a user via their role."""
    from app.models.role import Role
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if not role:
        return []
    return [rp.permission for rp in role.permissions]
