from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import typer
from rich.console import Console

setup_app = typer.Typer(
    help="Install Nina runtime dependencies, audio tools, and optional extras.",
    invoke_without_command=True,
)
console = Console()
PYTHON_PACKAGES = ("faster-whisper", "soundcard", "soxr")
MACOS_PYTHON_PACKAGES = (
    "pyobjc-framework-CoreAudio",
    "pyobjc-framework-AVFoundation",
)
MACOS_PACKAGES = ("ffmpeg",)
LINUX_PACKAGES = ("ffmpeg",)
WINDOWS_PACKAGES: tuple[str, ...] = ()


class SetupError(RuntimeError):
    pass


def _nina_python() -> str:
    return sys.executable


def _run_pip(args: Sequence[str], *, python: str) -> int:
    uv = shutil.which("uv")
    if uv is None:
        console.print(
            "[red]uv not found on PATH.[/red] Install it from https://docs.astral.sh/uv/ and re-run.",
        )
        return 127
    cmd = [uv, "pip", *args, "--python", python]
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    return subprocess.call(cmd)


def _run_command(cmd: Sequence[str]) -> int:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    try:
        return subprocess.call(list(cmd))
    except FileNotFoundError as exc:
        raise SetupError(f"Required command not found: {cmd[0]}") from exc


def _verify_imports(python: str, modules: Sequence[str]) -> None:
    code = "import sys; sys.argv=['verify'];" + ";".join(f"import {module}" for module in modules)
    rc = subprocess.call([python, "-c", code])
    if rc != 0:
        raise SetupError(
            f"Installed packages were not importable from {python}: {', '.join(modules)}"
        )


def _install_python_packages(python: str, packages: Sequence[str]) -> None:
    rc = _run_pip(["install", *packages], python=python)
    if rc != 0:
        raise SetupError(
            f"Python package install failed (exit {rc}). Try manually: "
            f"`uv pip install --python {python} {' '.join(packages)}`"
        )


def _needs_sudo() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() != 0


def _prefix_with_sudo(command: str) -> list[str]:
    if _needs_sudo() and shutil.which("sudo"):
        return ["sudo", command]
    return [command]


def _install_system_packages() -> None:
    system = platform.system()
    if system == "Darwin":
        brew = shutil.which("brew")
        if brew is None:
            raise SetupError("Homebrew is not installed. Install brew, then rerun `nina setup`.")
        console.print("Installing macOS audio tools via Homebrew…")
        rc = _run_command([brew, "install", *MACOS_PACKAGES])
        if rc != 0:
            raise SetupError("Homebrew install failed.")
        return
    if system == "Linux":
        apt_get = shutil.which("apt-get")
        if apt_get is None:
            raise SetupError("apt-get is not available. Install the system packages manually.")
        console.print("Installing Linux audio tools via apt…")
        rc = _run_command([*_prefix_with_sudo(apt_get), "update"])
        if rc != 0:
            raise SetupError("apt-get update failed.")
        rc = _run_command([*_prefix_with_sudo(apt_get), "install", "-y", *LINUX_PACKAGES])
        if rc != 0:
            raise SetupError("apt-get install failed.")
        return
    if system == "Windows":
        if WINDOWS_PACKAGES:
            console.print(f"Installing Windows tools: {WINDOWS_PACKAGES}")
        else:
            console.print("No system packages required on Windows.")
        return
    raise SetupError(f"Automatic system package installation is not supported on {system}.")


def setup_runtime(python: str | None = None, *, install_system: bool = True) -> None:
    python = python or _nina_python()
    failures: list[str] = []
    if install_system:
        try:
            _install_system_packages()
        except SetupError as exc:
            failures.append(str(exc))
    try:
        _install_python_packages(python, PYTHON_PACKAGES)
        if sys.platform == "darwin":
            _install_python_packages(python, MACOS_PYTHON_PACKAGES)
        verify_modules = ["faster_whisper", "soundcard", "soxr"]
        if sys.platform == "darwin":
            verify_modules.append("CoreAudio")
        _verify_imports(python, verify_modules)
    except SetupError as exc:
        failures.append(str(exc))
    if failures:
        raise SetupError("Setup incomplete:\n- " + "\n- ".join(failures))


@setup_app.callback(invoke_without_command=True)
def setup_default(
    ctx: typer.Context,
    system: bool = typer.Option(
        True,
        "--system/--no-system",
        help="Install OS packages such as ffmpeg.",
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    try:
        setup_runtime(install_system=system)
    except SetupError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print("[green]Nina setup complete.[/green]")


@setup_app.command(
    "transcription",
    help="Install faster-whisper into the nina Python so the local transcription backend works.",
)
def setup_transcription(
    upgrade: bool = typer.Option(False, "--upgrade", help="Reinstall / upgrade the package."),
) -> None:
    nina_py = _nina_python()
    console.print(f"Installing faster-whisper into [bold]{nina_py}[/bold]…")
    args = ["install", "faster-whisper"]
    if upgrade:
        args.append("--upgrade")
    rc = _run_pip(args, python=nina_py)
    if rc != 0:
        console.print(
            f"[red]Install failed (exit {rc}).[/red] Try manually: `uv pip install --python {nina_py} faster-whisper`",
        )
        raise typer.Exit(rc)
    try:
        _verify_imports(nina_py, ["faster_whisper"])
    except SetupError:
        console.print(
            f"[red]faster-whisper was installed but is not importable from {nina_py}.[/red] Check the install log above."
        )
        raise typer.Exit(1) from None
    console.print("[green]faster-whisper is ready.[/green] Run `nina status` to confirm.")


@setup_app.command("python", help="Print the Python executable the nina shim is running on.")
def setup_python() -> None:
    nina_py = _nina_python()
    console.print(nina_py)
    if (
        getattr(sys, "prefix", None)
        and Path(sys.prefix).resolve() != Path(sys.base_prefix).resolve()
    ):
        console.print(f"[dim]venv root: {Path(sys.prefix).resolve()}[/dim]")


__all__ = ["setup_app", "setup_runtime"]
