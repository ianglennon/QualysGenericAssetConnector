from cryptography.fernet import Fernet
from app.core.settings import get_settings
from functools import lru_cache


class CredentialCrypto:
    """Fernet-based symmetric encryption for credential storage.

    RULE: Only this service encrypts/decrypts credentials.
    Models and routers never handle plaintext credentials after initial validation.
    """

    def __init__(self, key: str):
        self._fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        """Encrypt plaintext string → URL-safe base64 token."""
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt Fernet token → plaintext string. Raises InvalidToken if tampered."""
        return self._fernet.decrypt(token.encode()).decode()


@lru_cache
def get_crypto() -> CredentialCrypto:
    return CredentialCrypto(get_settings().fernet_key)
