from typing import Optional, Literal
from pydantic import BaseModel
from datetime import datetime


class ConnectorCredentialsCreate(BaseModel):
    """Plaintext credentials for connector creation. Never stored as-is."""
    token: Optional[str] = None         # for bearer_token
    username: Optional[str] = None      # for basic_auth
    password: Optional[str] = None      # for basic_auth
    api_key_name: Optional[str] = None  # header name (plaintext, not a secret)
    api_key: Optional[str] = None       # for api_key_header


class ConnectorCredentialsUpdate(BaseModel):
    """Plaintext credentials for partial update. Only provided fields overwrite."""
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key_name: Optional[str] = None
    api_key: Optional[str] = None


class ConnectorCreate(BaseModel):
    name: str
    base_url: str
    test_path: Optional[str] = None
    auth_method: Literal["bearer_token", "basic_auth", "api_key_header"]
    credentials: Optional[ConnectorCredentialsCreate] = None
    source_retry_limit: Optional[int] = None
    qualys_retry_limit: Optional[int] = None
    verify_ssl: Optional[bool] = True


class ConnectorUpdate(BaseModel):
    """All optional for PATCH — omitted fields preserve existing values."""
    name: Optional[str] = None
    base_url: Optional[str] = None
    test_path: Optional[str] = None
    auth_method: Optional[Literal["bearer_token", "basic_auth", "api_key_header"]] = None
    credentials: Optional[ConnectorCredentialsUpdate] = None
    source_retry_limit: Optional[int] = None
    qualys_retry_limit: Optional[int] = None
    verify_ssl: Optional[bool] = None


class ConnectorResponse(BaseModel):
    """Safe response — NEVER includes encrypted credential values.
    Only has_* booleans indicate which credentials are configured.
    """
    id: str
    name: str
    base_url: str
    test_path: Optional[str]
    auth_method: str
    has_token: bool
    has_username: bool
    has_password: bool
    has_api_key: bool
    api_key_name: Optional[str]  # plaintext header name, not a secret
    source_retry_limit: Optional[int]
    qualys_retry_limit: Optional[int]
    verify_ssl: bool
    has_valid_endpoints: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
