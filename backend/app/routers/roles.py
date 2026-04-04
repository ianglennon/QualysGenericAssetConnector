from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.security import require_permission
from app.core.errors import make_error
from app.core.permissions import VALID_PERMISSIONS
from app.schemas.role import RoleCreate, RoleUpdate, PermissionAdd, RolePermissionResponse, RoleListResponse
from app.models.role import Role, RolePermission
from app.models.user import User

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", response_model=list[RoleListResponse])
def list_roles(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:read")),
):
    roles = db.query(Role).all()
    result = []
    for role in roles:
        user_count = db.query(func.count(User.id)).filter(User.role_id == role.id).scalar()
        result.append(RoleListResponse(
            id=role.id, name=role.name, description=role.description,
            is_system=role.is_system, created_at=role.created_at,
            user_count=user_count,
        ))
    return result


@router.get("/{role_id}", response_model=RolePermissionResponse)
def get_role(
    role_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:read")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=make_error("ROLE_NOT_FOUND", "Role not found"))
    return RolePermissionResponse(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, created_at=role.created_at,
        permissions=[rp.permission for rp in role.permissions],
    )


@router.post("/", response_model=RolePermissionResponse, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:create")),
):
    existing = db.query(Role).filter(Role.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=make_error("ROLE_NAME_EXISTS", "A role with this name already exists"))
    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    return RolePermissionResponse(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, created_at=role.created_at,
        permissions=[],
    )


@router.patch("/{role_id}", response_model=RolePermissionResponse)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:update")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=make_error("ROLE_NOT_FOUND", "Role not found"))
    if role.is_system:
        raise HTTPException(status_code=403, detail=make_error("ROLE_SYSTEM_PROTECTED", "Cannot modify a built-in system role"))
    if payload.name is not None:
        existing = db.query(Role).filter(Role.name == payload.name, Role.id != role_id).first()
        if existing:
            raise HTTPException(status_code=409, detail=make_error("ROLE_NAME_EXISTS", "A role with this name already exists"))
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    db.commit()
    db.refresh(role)
    return RolePermissionResponse(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, created_at=role.created_at,
        permissions=[rp.permission for rp in role.permissions],
    )


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:delete")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=make_error("ROLE_NOT_FOUND", "Role not found"))
    if role.is_system:
        raise HTTPException(status_code=403, detail=make_error("ROLE_SYSTEM_PROTECTED", "Cannot modify a built-in system role"))
    assigned_users = db.query(User.id).filter(User.role_id == role_id).all()
    if assigned_users:
        raise HTTPException(
            status_code=409,
            detail=make_error("ROLE_HAS_USERS", "Cannot delete role with assigned users",
                              {"user_ids": [u.id for u in assigned_users]}),
        )
    db.delete(role)
    db.commit()


@router.post("/{role_id}/permissions", response_model=RolePermissionResponse)
def add_permissions(
    role_id: str,
    payload: PermissionAdd,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:update")),
):
    """Add permission(s) to a role (per D-10 incremental add)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=make_error("ROLE_NOT_FOUND", "Role not found"))
    if role.is_system:
        raise HTTPException(status_code=403, detail=make_error("ROLE_SYSTEM_PROTECTED", "Cannot modify a built-in system role"))
    for perm in payload.permissions:
        if perm not in VALID_PERMISSIONS:
            raise HTTPException(
                status_code=422,
                detail=make_error("PERMISSION_INVALID", f"Invalid permission: {perm}",
                                  {"valid_permissions": sorted(VALID_PERMISSIONS)}),
            )
    existing_perms = {rp.permission for rp in role.permissions}
    for perm in payload.permissions:
        if perm not in existing_perms:
            db.add(RolePermission(role_id=role_id, permission=perm))
    db.commit()
    db.refresh(role)
    return RolePermissionResponse(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, created_at=role.created_at,
        permissions=[rp.permission for rp in role.permissions],
    )


@router.delete("/{role_id}/permissions/{permission}", response_model=RolePermissionResponse)
def remove_permission(
    role_id: str,
    permission: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("roles:update")),
):
    """Remove a single permission from a role (per D-10 incremental remove)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=make_error("ROLE_NOT_FOUND", "Role not found"))
    if role.is_system:
        raise HTTPException(status_code=403, detail=make_error("ROLE_SYSTEM_PROTECTED", "Cannot modify a built-in system role"))
    rp = db.query(RolePermission).filter(
        RolePermission.role_id == role_id, RolePermission.permission == permission
    ).first()
    if rp:
        db.delete(rp)
        db.commit()
    db.refresh(role)
    return RolePermissionResponse(
        id=role.id, name=role.name, description=role.description,
        is_system=role.is_system, created_at=role.created_at,
        permissions=[rp.permission for rp in role.permissions],
    )
