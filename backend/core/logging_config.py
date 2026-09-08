"""Application logging setup.

Rules: never log passwords, tokens, API keys or personal employee data.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from backend.core.config import BASE_DIR, settings

_CONFIGURED = False
SENSITIVE_KEYS = {"password", "password_hash", "token", "api_key", "authorization"}


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = Path(BASE_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
        force=True,
    )
    logging.getLogger("passlib").setLevel(logging.ERROR)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def redact(payload: dict) -> dict:
    """Return a copy of ``payload`` safe for logging."""
    return {
        key: ("***" if key.lower() in SENSITIVE_KEYS else value)
        for key, value in payload.items()
    }
