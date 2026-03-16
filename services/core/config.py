"""Ops Voice Co-Pilot - configuration from environment.

Uses env vars and optional .env. Secrets via GOOGLE_APPLICATION_CREDENTIALS
or workload identity; API keys not hardcoded (NFR-3).
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Override via env (e.g. GOOGLE_CLOUD_PROJECT)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Google Cloud (required for Vertex AI Live API, Cloud Logging)
    google_cloud_project: str = ""
    vertex_ai_location: str = "europe-west2"
    google_application_credentials: Optional[str] = None

    # Gemini Live API (Vertex AI)
    gemini_live_model: str = "gemini-live-2.5-flash-native-audio"

    # API (Cloud Run sets PORT)
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    log_level: str = "INFO"

    def get_port(self) -> int:
        """Return port to bind (respects Cloud Run PORT)."""
        return int(os.environ.get("PORT", self.api_port))


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()

