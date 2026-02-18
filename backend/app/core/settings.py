from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str

    # Security
    secret_key: str
    fernet_key: str
    docs_enabled: bool = False

    # JWT
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Admin seed
    admin_email: str = ""
    admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
