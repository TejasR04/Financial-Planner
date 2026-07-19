from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Meridian API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://meridian:meridian@localhost:5432/meridian"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_env: str = "sandbox"
    # Fernet key (32 url-safe base64-encoded bytes) used to encrypt Plaid
    # access tokens at rest. Generate a real one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # and put it in .env — never reuse the placeholder below outside local dev.
    plaid_token_encryption_key: str = "wKcp4Vw4qN7pQoT1Md1AXjC8v4Gg9WdY7CqB2m1x4Zk="

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    cors_allow_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
