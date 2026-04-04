from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleResponse(BaseModel):
    id: str
    name: str
    is_system: bool
    permissions: list[str]


class MeResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    role: RoleResponse


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordChangeResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
