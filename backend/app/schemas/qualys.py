from pydantic import BaseModel
from typing import Optional


class QualysConfigCreate(BaseModel):
    """Accepts plaintext credentials from admin. Never stored as-is."""

    api_url: str  # e.g. https://qualysapi.qg2.apps.qualys.com
    username: str
    connector_uuid: Optional[str] = None  # Qualys CSAM connector UUID
    password: Optional[str] = None  # Qualys password OR token (one required)
    token: Optional[str] = None


class QualysConfigResponse(BaseModel):
    """Safe response — NEVER includes encrypted_password or encrypted_token."""

    id: str
    api_url: str
    username: str
    connector_uuid: Optional[str]  # Qualys CSAM connector UUID
    has_password: bool  # True if a password is configured (without revealing it)
    has_token: bool  # True if a token is configured (without revealing it)

    class Config:
        from_attributes = True
