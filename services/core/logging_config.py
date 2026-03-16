"""
Logging configuration for Ops Voice Co-Pilot.

Compatible with Google Cloud Run and Cloud Logging.
"""

import logging
import os
import sys
from typing import Optional


def configure_logging(level: Optional[str] = None) -> None:
    """
    Configure root logging once.

    Cloud Run automatically captures stdout/stderr and sends to Cloud Logging.
    """

    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()

    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """
    Return a module logger.
    """

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    # Prevent double logging
    logger.propagate = False

    return logger