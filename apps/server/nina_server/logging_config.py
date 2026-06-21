from __future__ import annotations

import logging
from logging.config import dictConfig
from typing import Any

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
ACCESS_LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(client_addr)s - "%(request_line)s" %(status_code)s'
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
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": ACCESS_LOG_FORMAT,
                "datefmt": DATE_FORMAT,
                "use_colors": False,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
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
                "handlers": ["access"],
                "level": resolved_level,
                "propagate": False,
            },
        },
    }


def configure_logging(level: str) -> dict[str, Any]:
    log_config = build_log_config(level)
    dictConfig(log_config)
    return log_config
