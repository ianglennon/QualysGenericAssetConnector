from datetime import datetime
from pydantic import BaseModel


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class PermissionAdd(BaseModel):
    permissions: list[str]


class RolePermissionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    is_system: bool
    created_at: datetime
    permissions: list[str]

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    id: str
    name: str
    description: str | None
    is_system: bool
    created_at: datetime
    user_count: int

    model_config = {"from_attributes": True}
