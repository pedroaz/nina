from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import typer
from rich.console import Console

setup_app = typer.Typer(help="Install optional dependencies into the nina Python.")
console = Console()


def _nina_python() -> str:
    """Return the Python executable the current `nina` process is running on.

    On a fresh machine this is the venv `~/.nina/app/bin/python` (or wherever
    `make build` placed the install). It is the Python that needs to see
    `faster-whisper`, not whatever the user happens to have on PATH.
    """
    return sys.executable


def _run_pip(args: Sequence[str], *, python: str) -> int:
    """Run `uv pip <args> --python <python>` and stream output. Returns rc."""
    uv = shutil.which("uv")
    if uv is None:
        console.print(
            "[red]uv not found on PATH.[/red] Install it from https://docs.astral.sh/uv/ "
            "and re-run this command.",
        )
        return 127
    cmd = [uv, "pip", *args, "--python", python]
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    return subprocess.call(cmd)


@setup_app.command(
    "transcription",
    help=(
        "Install faster-whisper into the nina Python so the local "
        "transcription backend works. Run this once after `nina init` on a "
        "fresh machine; it does the right `uv pip install` for you."
    ),
)
def setup_transcription(
    upgrade: bool = typer.Option(
        False, "--upgrade", help="Reinstall / upgrade the package even if present."
    ),
) -> None:
    nina_py = _nina_python()
    console.print(f"Installing faster-whisper into [bold]{nina_py}[/bold]…")
    args = ["install", "faster-whisper"]
    if upgrade:
        args.append("--upgrade")
    rc = _run_pip(args, python=nina_py)
    if rc != 0:
        console.print(
            f"[red]Install failed (exit {rc}).[/red] Try manually: "
            f"`uv pip install --python {nina_py} faster-whisper`",
        )
        raise typer.Exit(rc)
    # Verify the install actually made the module importable.
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        console.print(
            f"[red]faster-whisper was installed but is not importable from "
            f"{nina_py}.[/red] Check the install log above.",
        )
        raise typer.Exit(1) from None
    console.print("[green]faster-whisper is ready.[/green] Run `nina status` to confirm.")


@setup_app.command(
    "python",
    help="Print the Python executable the nina shim is running on.",
)
def setup_python() -> None:
    nina_py = _nina_python()
    console.print(nina_py)
    # `sys.prefix` is the venv root inside a venv, otherwise the install prefix.
    # Print it when running inside a venv so the user can copy-paste the
    # right `uv pip install --python ...` line.
    if (
        getattr(sys, "prefix", None)
        and Path(sys.prefix).resolve() != Path(sys.base_prefix).resolve()
    ):
        console.print(f"[dim]venv root: {Path(sys.prefix).resolve()}[/dim]")


__all__ = ["setup_app"]
