import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings for Sagent (Ticket Triage Agent).
    Loads configuration from environment variables and .env file.
    """
    APP_NAME: str = "Sagent"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    
    # Gemini AI Configuration
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Active Gemini model for triage and reasoning")
    EMBEDDING_MODEL: str = Field(default="gemini-embedding-001", description="Model used for text embeddings")
    
    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/sagent",
        description="Async PostgreSQL connection URL (Neon or local)"
    )
    
    # CORS
    CORS_ORIGINS: list[str] | str = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    # AI Resilience & Retry Parameters
    MAX_GEMINI_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 10.0

    # Session-Based Ticket History Settings
    MAX_TICKET_PER_SESSION: int = Field(default=10, description="Max tickets preserved per session")
    SESSION_EXPIRY_DAYS: int = Field(default=7, description="Number of days a session lasts before expiring")

    # Phase 2 Security & Guardrails
    SECURITY_ENABLED: bool = Field(default=True, description="Enable PII scrubbing and injection guardrails")
    REQUIRE_API_KEY: bool = Field(default=False, description="Require API Key for incoming API requests")
    SAGENT_API_KEY: str = Field(default="sagent-sec-key-2026", description="Expected master API key")
    RATE_LIMIT_RPM: int = Field(default=120, description="Max requests per minute per client IP")
    MAX_AUTOMATED_REFUND_USD: float = Field(default=250.0, description="Max automated refund amount in USD without manager approval")

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def sanitize_database_url(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return v
        url_str = v.strip()
        # Convert standard postgres:// or postgresql:// to postgresql+asyncpg://
        if url_str.startswith("postgres://"):
            url_str = "postgresql+asyncpg://" + url_str[len("postgres://"):]
        elif url_str.startswith("postgresql://") and not url_str.startswith("postgresql+"):
            url_str = "postgresql+asyncpg://" + url_str[len("postgresql://"):]

        # asyncpg does not accept sslmode or channel_binding query params
        if "asyncpg" in url_str:
            try:
                from sqlalchemy.engine.url import make_url
                url = make_url(url_str)
                query = dict(url.query)
                changed = False
                if "sslmode" in query:
                    mode = query.pop("sslmode")
                    if "ssl" not in query:
                        query["ssl"] = mode
                    changed = True
                if "channel_binding" in query:
                    query.pop("channel_binding")
                    changed = True
                if changed:
                    url_str = url._replace(query=query).render_as_string(hide_password=False)
            except Exception:
                pass
        return url_str

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns cached Settings instance.
    Can be invalidated in testing or dynamic reloads.
    """
    return Settings()
