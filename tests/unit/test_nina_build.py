from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_nina_build():
    path = Path(__file__).resolve().parents[2] / "scripts" / "nina_build.py"
    spec = importlib.util.spec_from_file_location("nina_build_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_invokes_userland_setup_after_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    nina_build = _load_nina_build()
    app_dir = tmp_path / "app"

    monkeypatch.setattr(nina_build, "env_path", lambda name, default: default)
    monkeypatch.setattr(nina_build, "require_command", lambda name: None)
    monkeypatch.setattr(nina_build, "require_python_312", lambda: "/usr/bin/python3.12")
    monkeypatch.setattr(nina_build, "build_python_wheels", lambda out_dir: None)
    monkeypatch.setattr(nina_build, "build_tui_binary", lambda out_dir: tmp_path / "nina-tui")
    monkeypatch.setattr(nina_build, "install_python_app", lambda app_dir, wheel_dir: None)
    monkeypatch.setattr(
        nina_build, "install_tui_binary", lambda bin_dir, binary_path: tmp_path / "nina-tui"
    )
    monkeypatch.setattr(
        nina_build, "write_launcher", lambda app_dir, launcher_dir, tui_binary: tmp_path / "nina"
    )
    monkeypatch.setattr(nina_build, "run", lambda cmd, cwd=None: calls.append(list(cmd)))
    monkeypatch.setattr(
        nina_build,
        "env_path",
        lambda name, default: app_dir.parent if name == "NINA_INSTALL_ROOT" else default,
    )

    assert nina_build.main() == 0
    assert calls[-1][-3:] == ["nina_cli.main", "setup", "--no-system"]


def test_makefile_uninstall_targets_nina_uninstall() -> None:
    makefile = Path(__file__).resolve().parents[2] / "Makefile"
    text = makefile.read_text()
    assert "$(UV) run nina uninstall" in text
