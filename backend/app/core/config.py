"""Application settings loaded from environment variables.

Uses pydantic-settings so configuration is validated, typed and centralised.
A single cached `Settings` instance is exposed via `get_settings()`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    APP_NAME: str = "SystemIQ"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ---- Server ----
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---- Database ----
    DATABASE_URL: str = "sqlite:///./systemiq.db"

    # ---- Security ----
    SECRET_KEY: str = "CHANGE_ME"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # ---- Bootstrap admin ----
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_EMAIL: str = "admin@systemiq.io"
    FIRST_ADMIN_PASSWORD: str = "admin123"

    # ---- CORS ----
    # Stored as a plain comma-separated string. pydantic-settings v2 would try
    # to JSON-decode a list-typed env var, which breaks on comma-separated
    # input; keeping it a string and splitting in `cors_origins_list` avoids
    # that entirely.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Monitoring ----
    METRICS_BROADCAST_INTERVAL: float = 2.0
    METRICS_PERSIST_INTERVAL: float = 60.0
    METRICS_RETENTION_DAYS: int = 30

    # ---- Alert thresholds ----
    ALERT_CPU_THRESHOLD: float = 90.0
    ALERT_MEMORY_THRESHOLD: float = 90.0
    ALERT_DISK_THRESHOLD: float = 95.0

    # ---- Email ----
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "systemiq@localhost"
    ALERT_EMAIL_TO: str = ""

    # ---- ML ----
    ML_MODEL_DIR: str = "./ml_models"
    ML_MIN_TRAINING_SAMPLES: int = 30
    # Automatic retraining: periodically retrain & persist models from the
    # continuously collected data, so saved models stay fresh with no manual step.
    AUTO_RETRAIN_ENABLED: bool = True
    AUTO_RETRAIN_INTERVAL_HOURS: float = 24.0

    # ---- LLM ----
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = "llama3"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the comma-separated CORS_ORIGINS into a list of origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
