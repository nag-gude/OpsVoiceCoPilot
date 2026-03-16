"""Tools microservice: Cloud Logging API for get_recent_logs.

Exposes POST /logs/recent so the Agent service can call it when the model
invokes the get_recent_logs tool. Requires GOOGLE_CLOUD_PROJECT.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from core.config import get_settings
from core.logging_config import get_logger
from tools.logging_tool import get_recent_logs_for_agent

logger = get_logger(__name__)
app = FastAPI(title="Ops Voice Co-Pilot Tools", version="1.0.0")


class LogsRecentRequest(BaseModel):
    filter_expr: Optional[str] = None
    page_size: int = 30


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "ops-voice-copilot-tools",
        "project_set": bool(settings.google_cloud_project),
    }


@app.post("/logs/recent")
def logs_recent(body: LogsRecentRequest):
    """Return recent log entries as a string for agent grounding."""
    settings = get_settings()
    if not settings.google_cloud_project:
        return {"error": "GOOGLE_CLOUD_PROJECT not set", "result": ""}
    result = get_recent_logs_for_agent(
        settings.google_cloud_project,
        filter_expr=body.filter_expr,
        page_size=min(body.page_size, 100),
    )
    return {"result": result}
