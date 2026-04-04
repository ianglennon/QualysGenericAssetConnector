from datetime import datetime
from pydantic import BaseModel


class UserRoleInfo(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    role_id: str


class UserCreateResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    must_change_password: bool
    temporary_password: str
    role: UserRoleInfo

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    created_at: datetime
    role: UserRoleInfo

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None
    role_id: str | None = None
    is_active: bool | None = None
