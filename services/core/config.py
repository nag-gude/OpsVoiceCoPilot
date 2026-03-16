"""
Ops Voice Co-Pilot - configuration from environment.

Uses env vars and optional .env. Secrets via GOOGLE_APPLICATION_CREDENTIALS
or workload identity.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -----------------------------
    # Google Cloud configuration
    # -----------------------------

    google_cloud_project: str = Field(..., alias="GOOGLE_CLOUD_PROJECT")

    google_cloud_location: str = Field(
        default="europe-west1",
        alias="GOOGLE_CLOUD_LOCATION",
    )

    vertex_ai_location: Optional[str] = Field(
        default=None,
        alias="VERTEX_AI_LOCATION",
    )

    google_application_credentials: Optional[str] = Field(
        default=None,
        alias="GOOGLE_APPLICATION_CREDENTIALS",
    )

    # -----------------------------
    # Gemini Live API
    # -----------------------------

    gemini_live_model: str = Field(
        default="gemini-live-2.5-flash-native-audio",
        alias="GEMINI_LIVE_MODEL",
    )

    # -----------------------------
    # API server
    # -----------------------------

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")

    api_port: int = Field(default=8080, alias="PORT")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # -----------------------------
    # Validators
    # -----------------------------

    @field_validator("vertex_ai_location", mode="before")
    def normalize_vertex_location(cls, v, info):
        """
        If VERTEX_AI_LOCATION not set, fall back to GOOGLE_CLOUD_LOCATION.
        """
        if v:
            return v
        return info.data.get("google_cloud_location")

    # -----------------------------
    # Helpers
    # -----------------------------

    def get_port(self) -> int:
        """Return port to bind (Cloud Run compatible)."""
        return self.api_port


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()