#!/usr/bin/env python3
"""
Push demo failure log entries to Google Cloud Logging for testing scenarios.

Use before a demo so get_recent_logs (and the voice agent) can return
realistic ERROR/WARNING entries when you ask "Why did this break?".

Usage:
  python scripts/push-demo-logs.py PROJECT_ID
  # or
  GOOGLE_CLOUD_PROJECT=my-project python scripts/push-demo-logs.py

Requires: google-cloud-logging and proper credentials
  (gcloud auth application-default login or GOOGLE_APPLICATION_CREDENTIALS).
"""

from __future__ import annotations

import argparse
import os
import sys

DEMO_FAILURE_MESSAGES = [
    ("ERROR", "Connection refused to db-primary:5432; retries exhausted."),
    ("ERROR", "Health check failed for service gateway after 3 attempts."),
    ("WARNING", "CPU usage above 90% on node pool default-pool (europe-west1-a)."),
    ("ERROR", "Pod ops-voice-copilot-agent-7d8b9c crashed (OOMKilled)."),
    ("WARNING", "High latency p99=2.1s on /ws/live/voice; threshold 1.0s."),
]


def push_logs(project_id: str, quiet: bool = False) -> int:
    try:
        from google.cloud import logging as cloud_logging
    except ImportError:
        print("Error: google-cloud-logging not installed.", file=sys.stderr)
        return 1

    try:
        client = cloud_logging.Client(project=project_id)
    except Exception as e:
        print(f"Error: unable to create Cloud Logging client: {e}", file=sys.stderr)
        return 1

    log_name = "ops-voice-copilot-demo"
    logger = client.logger(log_name)

    written = 0
    for severity_str, message in DEMO_FAILURE_MESSAGES:
        # Use string severity instead of cloud_logging.Severity
        severity_val = severity_str.upper()  # "ERROR" or "WARNING"
        try:
            logger.log_struct(
                {"message": message, "source": "ops-voice-copilot-demo"},
                severity=severity_val,
            )
            written += 1
            if not quiet:
                print(f"  {severity_val}: {message}")
        except Exception as e:
            print(f"Failed to log message: {message} ({e})", file=sys.stderr)

    if not quiet:
        print(f"\nWrote {written} demo log entries to project '{project_id}' (log: {log_name})")
        print("They will appear in get_recent_logs / voice agent when you ask about failures.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Push demo failure log entries to GCP Cloud Logging")
    parser.add_argument(
        "project_id",
        nargs="?",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT environment variable)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose output, only print errors",
    )
    args = parser.parse_args()

    if not args.project_id:
        print("Error: project_id required. Pass as argument or set GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 1

    return push_logs(args.project_id, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())