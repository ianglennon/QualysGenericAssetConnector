from typing import Optional

from pydantic import BaseModel


class QualysConfigCreate(BaseModel):
    """Accepts plaintext credentials from admin. Never stored as-is."""

    username: str
    password: Optional[str] = None   # Optional on update; required on first save (enforced in router)
    connector_uuid: str


class QualysConfigResponse(BaseModel):
    """Safe response -- NEVER includes encrypted_password."""

    id: str
    username: str
    connector_uuid: str
    has_password: bool
    platform_name: str       # Computed from username, not stored
    api_server_url: str      # Computed from username, not stored
    api_gateway_url: str     # Computed from username, not stored

    class Config:
        from_attributes = True
