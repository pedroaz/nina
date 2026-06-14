#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
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


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def detect_tui_target() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    arch_map = {
        "amd64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
    }
    arch = arch_map.get(machine)

    if system == "Linux" and arch in {"x64", "arm64"}:
        return f"bun-linux-{arch}", "nina-tui"
    if system == "Darwin" and arch in {"x64", "arm64"}:
        return f"bun-darwin-{arch}", "nina-tui"
    if system == "Windows" and arch == "x64":
        return "bun-windows-x64", "nina-tui.exe"

    raise SystemExit(f"Unsupported platform for local build: {system} {machine}")


def build_python_wheels(out_dir: Path) -> None:
    print("Building Python wheels...")
    out_dir.mkdir(parents=True, exist_ok=True)
    for project in PYTHON_PROJECTS:
        run(["uv", "build", "--wheel", "--out-dir", str(out_dir)], cwd=project)


def build_tui_binary(out_dir: Path) -> Path:
    target, binary_name = detect_tui_target()
    print(f"Building TUI binary for {target}...")
    out_dir.mkdir(parents=True, exist_ok=True)
    binary_path = out_dir / binary_name
    run(
        [
            "bun",
            "build",
            "src/main.ts",
            "--compile",
            f"--target={target}",
            "--outfile",
            str(binary_path),
        ],
        cwd=REPO_ROOT / "apps" / "tui",
    )
    return binary_path


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
    run(["uv", "venv", str(app_dir)])
    python_bin = python_executable(app_dir)
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise SystemExit(f"No wheel files were built in {wheel_dir}")
    run(["uv", "pip", "install", "--python", str(python_bin), *[str(wheel) for wheel in wheels]])


def install_tui_binary(bin_dir: Path, binary_path: Path) -> Path:
    print(f"Installing TUI binary into {bin_dir}...")
    bin_dir.mkdir(parents=True, exist_ok=True)
    installed_path = bin_dir / binary_path.name
    remove_path(installed_path)
    shutil.copy2(binary_path, installed_path)
    if os.name != "nt":
        installed_path.chmod(0o755)
    return installed_path


def write_launcher(app_dir: Path, launcher_dir: Path, tui_binary: Path) -> Path:
    print(f"Writing launcher into {launcher_dir}...")
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = launcher_dir / ("nina.cmd" if os.name == "nt" else "nina")
    remove_path(launcher_path)

    app_exec = nina_executable(app_dir)
    if os.name == "nt":
        launcher_path.write_text(
            f'@echo off\r\nset "NINA_TUI_BIN={tui_binary}"\r\nset "OPENTUI_NO_GRAPHICS=1"\r\n"{app_exec}" %*\r\n',
            encoding="ascii",
        )
    else:
        launcher_path.write_text(
            "#!/usr/bin/env sh\n"
            f"export NINA_TUI_BIN={shlex.quote(str(tui_binary))}\n"
            f"export OPENTUI_NO_GRAPHICS=1\n"
            f'exec {shlex.quote(str(app_exec))} "$@"\n',
            encoding="ascii",
        )
        launcher_path.chmod(0o755)
    return launcher_path


def main() -> int:
    install_root = env_path("NINA_INSTALL_ROOT", Path.home() / ".nina")
    launcher_dir = env_path("NINA_LAUNCHER_DIR", default_launcher_dir())
    app_dir = install_root / "app"
    bin_dir = install_root / "bin"

    with tempfile.TemporaryDirectory(prefix="nina-build-") as temp_dir:
        temp_path = Path(temp_dir)
        wheel_dir = temp_path / "wheels"
        tui_dir = temp_path / "tui"
        build_python_wheels(wheel_dir)
        built_tui = build_tui_binary(tui_dir)
        install_python_app(app_dir, wheel_dir)
        installed_tui = install_tui_binary(bin_dir, built_tui)
        launcher_path = write_launcher(app_dir, launcher_dir, installed_tui)

    print("Local Nina build complete.")
    print(f"Launcher: {launcher_path}")
    print(f"TUI binary: {installed_tui}")
    print(f"App venv: {app_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
