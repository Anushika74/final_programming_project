"""Centralised logging configuration.

Provides a consistent, structured-ish console logger across the whole app.
Call `configure_logging()` once at startup, then use `logging.getLogger(__name__)`.
"""
from __future__ import annotations

import logging
import sys
from logging.config import dictConfig

from app.core.config import settings


def configure_logging() -> None:
    """Configure root logging handlers and formatters."""
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": sys.stdout,
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            "loggers": {
                # Quieten noisy third-party loggers a little.
                "uvicorn.access": {"level": "WARNING"},
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )

    logging.getLogger("systemiq").info(
        "Logging configured (level=%s, env=%s)", log_level, settings.ENVIRONMENT
    )
