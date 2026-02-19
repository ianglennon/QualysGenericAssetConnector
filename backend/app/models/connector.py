import enum
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AuthMethod(str, enum.Enum):
    bearer_token = "bearer_token"
    basic_auth = "basic_auth"
    api_key_header = "api_key_header"


class Connector(Base):
    """Stores generic asset connector configuration.

    All credential columns (encrypted_token, encrypted_username,
    encrypted_password, encrypted_api_key) store Fernet-encrypted ciphertext.
    NEVER store or return plaintext values from these columns directly.
    api_key_name is stored plaintext — the header name is not a secret.
    """

    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    test_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # auth_method stored as String (not sa.Enum) to avoid SQLite Enum DDL complexity.
    # Validated at schema layer (Pydantic) against AuthMethod enum values.
    auth_method: Mapped[str] = mapped_column(String, nullable=False)
    # Encrypted credential columns — Fernet ciphertext:
    encrypted_token: Mapped[str | None] = mapped_column(String, nullable=True)       # bearer_token auth
    encrypted_username: Mapped[str | None] = mapped_column(String, nullable=True)    # basic_auth
    encrypted_password: Mapped[str | None] = mapped_column(String, nullable=True)    # basic_auth
    api_key_name: Mapped[str | None] = mapped_column(String, nullable=True)          # plaintext — header name
    encrypted_api_key: Mapped[str | None] = mapped_column(String, nullable=True)     # api_key_header auth
    # pagination_config stores a list of strategy dicts; coerce to [] in response if None
    pagination_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
