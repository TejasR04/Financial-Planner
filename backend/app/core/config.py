from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Meridian API"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://meridian:meridian@localhost:5432/meridian"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "meridian_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    password_reset_token_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_env: str = "sandbox"
    plaid_auto_sync_enabled: bool = True
    plaid_auto_sync_interval_minutes: int = 360
    # Fernet key (32 url-safe base64-encoded bytes) used to encrypt Plaid
    # access tokens at rest. Generate a real one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # and put it in .env — never reuse the placeholder below outside local dev.
    plaid_token_encryption_key: str = "wKcp4Vw4qN7pQoT1Md1AXjC8v4Gg9WdY7CqB2m1x4Zk="

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"

    cors_allow_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def validate_runtime_safety(self) -> "Settings":
        if self.refresh_cookie_samesite not in {"lax", "strict"}:
            raise ValueError("REFRESH_COOKIE_SAMESITE must be lax or strict")
        if bool(self.plaid_client_id) != bool(self.plaid_secret):
            raise ValueError("PLAID_CLIENT_ID and PLAID_SECRET must be configured together")
        if self.environment.lower() == "production":
            if self.jwt_secret_key == "change-me-in-.env" or len(self.jwt_secret_key) < 32:
                raise ValueError("Production JWT_SECRET_KEY must be a non-placeholder value of at least 32 characters")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("FRONTEND_URL must use HTTPS in production")
            if not self.cors_allow_origins or any(
                origin == "*" or not origin.startswith("https://") for origin in self.cors_allow_origins
            ):
                raise ValueError("Production CORS_ALLOW_ORIGINS must contain explicit HTTPS origins")
            if self.plaid_client_id and self.plaid_token_encryption_key == "wKcp4Vw4qN7pQoT1Md1AXjC8v4Gg9WdY7CqB2m1x4Zk=":
                raise ValueError("Production Plaid token encryption key must not use the development placeholder")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
