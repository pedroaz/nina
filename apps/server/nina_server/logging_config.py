from __future__ import annotations

import logging
from logging.config import dictConfig
from typing import Any

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def resolve_log_level(level: str) -> int:
    resolved = logging.getLevelName(level.upper())
    return resolved if isinstance(resolved, int) else logging.INFO


def build_log_config(level: str) -> dict[str, Any]:
    resolved_level = resolve_log_level(level)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
                "datefmt": DATE_FORMAT,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "null": {
                "class": "logging.NullHandler",
            },
        },
        "root": {
            "handlers": ["default"],
            "level": resolved_level,
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": resolved_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "level": resolved_level,
            },
            "uvicorn.access": {
                "handlers": ["null"],
                "level": logging.WARNING,
                "propagate": False,
            },
        },
    }


def configure_logging(level: str) -> dict[str, Any]:
    log_config = build_log_config(level)
    dictConfig(log_config)
    return log_config
