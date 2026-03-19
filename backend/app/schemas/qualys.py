from pydantic import BaseModel


class QualysConfigCreate(BaseModel):
    """Accepts plaintext credentials from admin. Never stored as-is."""

    username: str
    password: str          # now required (not optional)
    connector_uuid: str    # now required (not optional)


class QualysConfigResponse(BaseModel):
    """Safe response -- NEVER includes encrypted_password."""

    id: str
    username: str
    connector_uuid: str    # now required (not Optional)
    has_password: bool

    class Config:
        from_attributes = True
