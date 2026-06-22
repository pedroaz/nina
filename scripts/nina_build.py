#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PYTHON = "3.12"
PYTHON_PROJECTS = [
    REPO_ROOT / "packages" / "nina_core",
    REPO_ROOT / "apps" / "server",
    REPO_ROOT / "apps" / "cli",
]


def env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def default_launcher_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Programs" / "Nina" / "bin"
        return Path.home() / "AppData" / "Local" / "Programs" / "Nina" / "bin"
    return Path.home() / ".local" / "bin"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(cmd, cwd=cwd or REPO_ROOT, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required command not found: {cmd[0]}") from exc


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required command not found on PATH: {name}")


def require_python_312() -> str:
    require_command("uv")
    result = subprocess.run(
        ["uv", "python", "find", REQUIRED_PYTHON],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Python 3.12 is required. Install it with 'uv python install 3.12' "
            "or make sure Python 3.12 is available to uv."
        )
    return result.stdout.strip()


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def build_python_wheels(out_dir: Path) -> None:
    print("Building Python wheels...")
    out_dir.mkdir(parents=True, exist_ok=True)
    for project in PYTHON_PROJECTS:
        run(["uv", "build", "--wheel", "--out-dir", str(out_dir)], cwd=project)


def python_executable(app_dir: Path) -> Path:
    if os.name == "nt":
        return app_dir / "Scripts" / "python.exe"
    return app_dir / "bin" / "python"


def nina_executable(app_dir: Path) -> Path:
    if os.name == "nt":
        return app_dir / "Scripts" / "nina.exe"
    return app_dir / "bin" / "nina"


def install_python_app(app_dir: Path, wheel_dir: Path) -> None:
    print(f"Installing Python app into {app_dir}...")
    remove_path(app_dir)
    python_interpreter = require_python_312()
    run(["uv", "venv", "--python", python_interpreter, str(app_dir)])
    python_bin = python_executable(app_dir)
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise SystemExit(f"No wheel files were built in {wheel_dir}")
    run(["uv", "pip", "install", "--python", str(python_bin), *[str(wheel) for wheel in wheels]])


def write_launcher(app_dir: Path, launcher_dir: Path) -> Path:
    print(f"Writing launcher into {launcher_dir}...")
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = launcher_dir / ("nina.cmd" if os.name == "nt" else "nina")
    remove_path(launcher_path)

    app_exec = nina_executable(app_dir)
    if os.name == "nt":
        launcher_path.write_text(
            f'@echo off\r\n"{app_exec}" %*\r\n',
            encoding="ascii",
        )
    else:
        launcher_path.write_text(
            f'#!/usr/bin/env sh\nexec {shlex.quote(str(app_exec))} "$@"\n',
            encoding="ascii",
        )
        launcher_path.chmod(0o755)
    return launcher_path


def main() -> int:
    require_python_312()
    install_root = env_path("NINA_INSTALL_ROOT", Path.home() / ".nina")
    launcher_dir = env_path("NINA_LAUNCHER_DIR", default_launcher_dir())
    app_dir = install_root / "app"

    with tempfile.TemporaryDirectory(prefix="nina-build-") as temp_dir:
        temp_path = Path(temp_dir)
        wheel_dir = temp_path / "wheels"
        build_python_wheels(wheel_dir)
        install_python_app(app_dir, wheel_dir)
        launcher_path = write_launcher(app_dir, launcher_dir)

    run([str(python_executable(app_dir)), "-m", "nina_cli.main", "setup", "--no-system"])

    print("Local Nina build complete.")
    print(f"Launcher: {launcher_path}")
    print(f"App venv: {app_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
