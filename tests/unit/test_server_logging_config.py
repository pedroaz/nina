from __future__ import annotations

import logging

from nina_server.logging_config import (
    ACCESS_LOG_FORMAT,
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


def test_build_log_config_replaces_uvicorn_default_formatters() -> None:
    config = build_log_config("info")
    access_formatter = config["formatters"]["access"]

    assert access_formatter["()"] == "uvicorn.logging.AccessFormatter"
    assert access_formatter["fmt"] == ACCESS_LOG_FORMAT
    assert access_formatter["datefmt"] == DATE_FORMAT
    assert access_formatter["use_colors"] is False
    assert "%(levelprefix)s" not in ACCESS_LOG_FORMAT
    assert "%(client_addr)s" in ACCESS_LOG_FORMAT
    assert "%(request_line)s" in ACCESS_LOG_FORMAT
    assert "%(status_code)s" in ACCESS_LOG_FORMAT
    assert "%(msecs)" not in ACCESS_LOG_FORMAT


def test_resolve_log_level_falls_back_to_info_for_unknown_levels() -> None:
    assert resolve_log_level("warning") == logging.WARNING
    assert resolve_log_level("not-a-level") == logging.INFO
