"""Simple logging for Ops Voice Co-Pilot."""
import logging
import os


def get_logger(name: str) -> logging.Logger:
    """Return a logger with level from LOG_LEVEL env."""
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        log.addHandler(handler)
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log.setLevel(getattr(logging, level, logging.INFO))
    return log
