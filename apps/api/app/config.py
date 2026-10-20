from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parents[3] / ".env",
            Path(__file__).resolve().parents[3] / ".env.local",
        ),
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://deliverygap@localhost:5432/deliverygap"
    database_url_unpooled: str = ""
    neon_auth_base_url: str = ""
    neon_auth_jwks_url: str = ""
    neon_ai_gateway_base_url: str = ""
    neon_ai_gateway_token: str = ""
    neon_embedding_model: str = "qwen3-embedding-0-6b"

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def psycopg_url(cls, value: str) -> str:
        if value.startswith(("postgres://", "postgresql://")):
            return "postgresql+psycopg://" + value.split("://", 1)[1]
        return value

    app_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=24)
    redis_url: str = "redis://localhost:6379/0"
    source_storage_backend: Literal["s3", "filesystem"] = "s3"
    local_storage_path: str = ".cache/source-objects"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "deliverygap-private"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    max_source_chars: int = Field(default=1_000_000, ge=1, le=2_000_000)
    max_source_spans: int = Field(default=2000, ge=1, le=5000)
    max_pdf_pages: int = Field(default=200, ge=1, le=500)

    @model_validator(mode="after")
    def secure_origin(self) -> "Settings":
        from urllib.parse import urlsplit

        origin = urlsplit(self.app_origin)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path:
            raise ValueError("APP_ORIGIN must be a scheme and host without a trailing slash")
        if origin.hostname not in {"localhost", "127.0.0.1"}:
            if origin.scheme != "https" or not self.cookie_secure:
                raise ValueError("Non-local origins require HTTPS and secure cookies")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
