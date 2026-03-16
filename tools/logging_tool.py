"""Cloud Logging tool: get_recent_logs for grounding agent answers (FR-9)."""

from __future__ import annotations

import json
from typing import Any, Optional

from core.logging_config import get_logger

logger = get_logger(__name__)


def get_recent_logs(
    project_id: str,
    *,
    filter_expr: Optional[str] = None,
    page_size: int = 50,
    order_by: str = "timestamp desc",
) -> dict[str, Any]:
    """
    Fetch recent log entries from Google Cloud Logging.
    Used by the agent to ground answers in actual log data.
    """
    try:
        from google.cloud import logging as cloud_logging
    except ImportError:
        return {"error": "google-cloud-logging not installed", "entries": []}

    if not project_id:
        return {"error": "project_id required", "entries": []}

    client = cloud_logging.Client(project=project_id)
    resource_names = [f"projects/{project_id}"]
    filter_str = filter_expr or "severity>=ERROR"
    if len(filter_str) > 2000:
        filter_str = "severity>=ERROR"

    try:
        # list_entries returns an iterator of LogEntry
        iterator = client.list_entries(
            resource_names=resource_names,
            filter_=filter_str,
            order_by=order_by,
            page_size=min(page_size, 100),
        )
        out = []
        for i, entry in enumerate(iterator):
            if i >= page_size:
                break
            ts = entry.timestamp.isoformat() if getattr(entry, "timestamp", None) else None
            sev = getattr(entry, "severity", None) or ""
            text = getattr(entry, "text_payload", None) or ""
            j = getattr(entry, "json_payload", None)
            res = getattr(entry, "resource", None)
            out.append(
                {
                    "timestamp": ts,
                    "severity": str(sev),
                    "text_payload": text,
                    "json_payload": dict(j) if j else None,
                    "resource": dict(res) if res else None,
                }
            )
        return {"entries": out, "count": len(out)}
    except Exception as e:
        logger.exception("get_recent_logs failed: %s", e)
        return {"error": str(e), "entries": []}


def get_recent_logs_for_agent(
    project_id: str,
    filter_expr: Optional[str] = None,
    page_size: int = 30,
) -> str:
    """
    Same as get_recent_logs but returns a string suitable for the agent
    (grounding in tool results). Verbal attribution: "From the logs I just pulled..."
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
            text = text or json.dumps(j)[:500]
        if text:
            lines.append(f"[{ts}] {sev}: {text[:400]}")
    return "\n".join(lines[:30])
