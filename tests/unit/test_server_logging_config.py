from __future__ import annotations

import logging

from nina_server.logging_config import (
    DATE_FORMAT,
    LOG_FORMAT,
    build_log_config,
    resolve_log_level,
)


def test_build_log_config_uses_seconds_only_timestamp_format() -> None:
    config = build_log_config("debug")

    assert config["root"]["level"] == logging.DEBUG
    assert config["formatters"]["default"] == {
        "format": LOG_FORMAT,
        "datefmt": DATE_FORMAT,
    }
    assert "%(asctime)s" in LOG_FORMAT
    assert "%(msecs)" not in LOG_FORMAT


def test_build_log_config_suppresses_uvicorn_access_logs() -> None:
    config = build_log_config("info")

    assert config["handlers"]["null"]["class"] == "logging.NullHandler"
    assert config["loggers"]["uvicorn.access"] == {
        "handlers": ["null"],
        "level": logging.WARNING,
        "propagate": False,
    }


def test_resolve_log_level_falls_back_to_info_for_unknown_levels() -> None:
    assert resolve_log_level("warning") == logging.WARNING
    assert resolve_log_level("not-a-level") == logging.INFO
