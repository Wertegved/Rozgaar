from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Rozgaar API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = Field(
        default=(
            "http://localhost:5500,http://127.0.0.1:5500,"
            "http://localhost:5501,http://127.0.0.1:5501,"
            "http://localhost:5502,http://127.0.0.1:5502"
        ),
        validation_alias="CORS_ORIGINS",
    )
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str = Field(default="", validation_alias="SUPABASE_JWT_SECRET")
    supabase_db_url: str | None = None
    supabase_db_direct_url: str | None = None
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    payment_provider: str = "simulated"
    payment_advance_percentage: int = Field(default=20, ge=0, le=100)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Rozgaar"
    email_provider: str = "smtp"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    ai_primary_provider: str = "groq"
    ai_primary_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_api_key: str = ""
    ai_fallback_provider: str = "gemini"
    ai_fallback_model: str = "gemini-3.8-flash"
    gemini_api_key: str = ""
    ai_request_timeout_seconds: float = Field(default=30, gt=0)
    ai_max_retries: int = Field(default=2, ge=0)
    realtime_enabled: bool = True
    realtime_publication: str = "supabase_realtime"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("smtp_port", mode="before")
    @classmethod
    def default_blank_smtp_port(cls, value: object) -> object:
        return 587 if value == "" else value

    @field_validator("ai_primary_provider", "ai_fallback_provider")
    @classmethod
    def validate_ai_provider(cls, value: str) -> str:
        if value.lower() not in {"groq", "gemini", "fake"}:
            raise ValueError("AI provider must be one of: groq, gemini, fake")
        return value.lower()

    @field_validator("email_provider")
    @classmethod
    def validate_email_provider(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"smtp", "fake"}:
            raise ValueError("EMAIL_PROVIDER must be one of: smtp, fake")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str | None:
        if not self.database_url:
            return None
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()