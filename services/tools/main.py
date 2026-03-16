"""
Tools microservice: Cloud Logging API for get_recent_logs.

Provides tool endpoint used by the Ops Voice Co-Pilot Agent.
"""

import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.core.config import get_settings
from services.core.logging_config import get_logger
from services.tools.logging_tool import get_recent_logs_for_agent

logger = get_logger(__name__)

app = FastAPI(
    title="Ops Voice Co-Pilot Tools",
    version="1.1.0"
)


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------

class LogsRecentRequest(BaseModel):

    filter_expr: Optional[str] = Field(
        default=None,
        description="Cloud Logging filter expression"
    )

    page_size: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Number of log entries to fetch (1-100)"
    )


class LogsRecentResponse(BaseModel):

    result: str
    error: Optional[str] = None


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
def health():

    settings = get_settings()

    return {
        "status": "ok",
        "service": "ops-voice-copilot-tools",
        "project_set": bool(settings.google_cloud_project),
    }


# ---------------------------------------------------------
# Logs Tool
# ---------------------------------------------------------

@app.post("/logs/recent", response_model=LogsRecentResponse)
async def logs_recent(body: LogsRecentRequest):

    settings = get_settings()

    if not settings.google_cloud_project:

        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLOUD_PROJECT not configured"
        )

    logger.info(
        "logs_recent called",
        extra={
            "filter": body.filter_expr,
            "page_size": body.page_size
        }
    )

    try:

        # Run blocking logging API in thread
        result = await asyncio.to_thread(
            get_recent_logs_for_agent,
            settings.google_cloud_project,
            filter_expr=body.filter_expr,
            page_size=body.page_size,
        )

        if not result:
            result = "No recent log entries found."

        return LogsRecentResponse(result=result)

    except Exception as e:

        logger.exception("logs_recent failed")

        return LogsRecentResponse(
            result="",
            error=str(e)
        )