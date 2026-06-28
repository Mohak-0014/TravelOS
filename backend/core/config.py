from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so it loads correctly regardless of CWD
# (uvicorn --reload worker processes may inherit a different working directory)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelos"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None  # required when Qdrant is network-exposed in prod

    # LLM
    GROQ_API_KEY: str = ""

    # External APIs
    LITEAPI_KEY: str = ""
    HOTELSNL_API_KEY: str = ""
    FOURSQUARE_API_KEY: str = ""
    TICKETMASTER_API_KEY: str = ""
    EVENTBRITE_TOKEN: str = ""
    UNSPLASH_ACCESS_KEY: str = ""
    DUFFEL_API_KEY: str = ""
    # Overpass API (OpenStreetMap) — no key required

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    RATE_LIMIT_ENABLED: bool = True
    # Retry + circuit breaker on outbound provider calls (Nominatim, Duffel, LiteAPI, …)
    RESILIENCE_ENABLED: bool = True

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    # Optional
    SENTRY_DSN: str | None = None

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        """Fail closed: never boot production with the insecure default JWT secret."""
        if self.ENVIRONMENT == "production":
            if (
                self.JWT_SECRET_KEY in ("", "change-me-in-production")
                or len(self.JWT_SECRET_KEY) < 32
            ):
                raise ValueError(
                    "JWT_SECRET_KEY must be a strong value (>=32 chars) in production. "
                    "Generate one with: openssl rand -hex 32"
                )
        return self


settings = Settings()
