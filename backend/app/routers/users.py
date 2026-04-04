from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_permission
from app.core.errors import make_error
from app.schemas.user import UserCreate, UserCreateResponse, UserResponse, UserUpdate, UserRoleInfo
from app.services.user_service import create_user_account, update_user_account, deactivate_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("users:read")),
):
    users = db.query(User).all()
    return [
        UserResponse(
            id=u.id, email=u.email, is_active=u.is_active,
            created_at=u.created_at,
            role=UserRoleInfo(id=u.role.id, name=u.role.name),
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("users:read")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=make_error("USER_NOT_FOUND", "User not found"))
    return UserResponse(
        id=user.id, email=user.email, is_active=user.is_active,
        created_at=user.created_at,
        role=UserRoleInfo(id=user.role.id, name=user.role.name),
    )


@router.post("/", response_model=UserCreateResponse, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("users:create")),
):
    user, temp_password = create_user_account(db, payload.email, payload.role_id)
    return UserCreateResponse(
        id=user.id, email=user.email, is_active=user.is_active,
        must_change_password=user.must_change_password,
        temporary_password=temp_password,
        role=UserRoleInfo(id=user.role.id, name=user.role.name),
    )


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("users:update")),
):
    updates = payload.model_dump(exclude_unset=True)
    user = update_user_account(db, user_id, current_user.id, **updates)
    return UserResponse(
        id=user.id, email=user.email, is_active=user.is_active,
        created_at=user.created_at,
        role=UserRoleInfo(id=user.role.id, name=user.role.name),
    )


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user_endpoint(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("users:update")),
):
    user = deactivate_user(db, user_id, current_user.id)
    return UserResponse(
        id=user.id, email=user.email, is_active=user.is_active,
        created_at=user.created_at,
        role=UserRoleInfo(id=user.role.id, name=user.role.name),
    )
