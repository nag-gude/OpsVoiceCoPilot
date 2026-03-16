"""Cloud Logging tool: get_recent_logs for grounding agent answers (FR-9)."""

from __future__ import annotations

import json
from typing import Any, Optional
import asyncio

from services.core.logging_config import get_logger

logger = get_logger(__name__)

MAX_PAGE_SIZE = 100
MAX_TEXT_LEN = 400
MAX_JSON_LEN = 500
MAX_FILTER_LEN = 2000


def get_recent_logs(
    project_id: str,
    *,
    filter_expr: Optional[str] = None,
    page_size: int = 50,
    order_by: str = "timestamp desc",
) -> dict[str, Any]:
    """
    Fetch recent log entries from Google Cloud Logging.
    Returns dict with "entries" list and optional "error".
    """
    try:
        from google.cloud import logging as cloud_logging
    except ImportError:
        return {"error": "google-cloud-logging not installed", "entries": []}

    if not project_id:
        return {"error": "project_id required", "entries": []}

    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    filter_str = filter_expr or "severity>=ERROR"
    if len(filter_str) > MAX_FILTER_LEN:
        filter_str = "severity>=ERROR"

    try:
        client = cloud_logging.Client(project=project_id)
        resource_names = [f"projects/{project_id}"]

        iterator = client.list_entries(
            resource_names=resource_names,
            filter_=filter_str,
            order_by=order_by,
            page_size=page_size,
        )

        out = []
        for i, entry in enumerate(iterator):
            if i >= page_size:
                break
            ts = getattr(entry, "timestamp", None)
            ts_str = ts.isoformat() if ts else ""
            sev = getattr(entry, "severity", "")
            text = getattr(entry, "text_payload", "") or ""
            j = getattr(entry, "json_payload", None)
            res = getattr(entry, "resource", None)

            # Truncate large JSON payloads
            if j:
                try:
                    text = text or json.dumps(j)[:MAX_JSON_LEN]
                except Exception:
                    text = "[unserializable JSON payload]"

            out.append(
                {
                    "timestamp": ts_str,
                    "severity": str(sev),
                    "text_payload": text[:MAX_TEXT_LEN],
                    "json_payload": dict(j) if j else None,
                    "resource": dict(res) if res else None,
                }
            )

        return {"entries": out, "count": len(out)}

    except Exception as e:
        logger.exception("get_recent_logs failed: %s", e)
        return {"error": str(e), "entries": []}


async def get_recent_logs_async(
    project_id: str,
    filter_expr: Optional[str] = None,
    page_size: int = 30,
) -> dict[str, Any]:
    """
    Async wrapper for get_recent_logs.
    Can be called in FastAPI endpoints without blocking the event loop.
    """
    return await asyncio.to_thread(
        get_recent_logs,
        project_id,
        filter_expr=filter_expr,
        page_size=page_size,
    )


def get_recent_logs_for_agent(
    project_id: str,
    filter_expr: Optional[str] = None,
    page_size: int = 30,
) -> str:
    """
    Returns string suitable for grounding agent answers.
    Limits lines and characters for readability.
    """
    result = get_recent_logs(
        project_id,
        filter_expr=filter_expr,
        page_size=page_size,
    )

    if result.get("error"):
        return f"Error fetching logs: {result['error']}"

    entries = result.get("entries", [])
    if not entries:
        return "No recent log entries matched the filter."

    lines = []
    for e in entries:
        ts = e.get("timestamp", "")
        sev = e.get("severity", "")
        text = e.get("text_payload") or ""
        j = e.get("json_payload")
        if j:
            text = text or json.dumps(j)[:MAX_JSON_LEN]
        if text:
            lines.append(f"[{ts}] {sev}: {text[:MAX_TEXT_LEN]}")

    # Limit total lines returned
    return "\n".join(lines[:30])