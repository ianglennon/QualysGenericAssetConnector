import uuid
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class QualysConfig(Base):
    """Stores Qualys subscription credentials.

    All credential columns store Fernet-encrypted ciphertext.
    NEVER store or return plaintext values from these columns directly.
    """

    __tablename__ = "qualys_config"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_url: Mapped[str] = mapped_column(String, nullable=False)  # not a secret, stored plaintext
    username: Mapped[str] = mapped_column(String, nullable=False)  # not a secret, stored plaintext
    # Encrypted columns — Fernet ciphertext:
    encrypted_password: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_token: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
