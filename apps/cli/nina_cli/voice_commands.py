from __future__ import annotations

import shutil
import subprocess
import sys
import time
from typing import Any

import typer

from .api import request
from .output import console, print_json

voice_app = typer.Typer(help="Voice capture and local transcription.")


def _run_clipboard_command(command: list[str], binary: str, text: str) -> tuple[bool, str | None]:
    argv = [binary, *command[1:]]
    if command[0] in {"xclip", "xsel"}:
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            proc.communicate(text, timeout=5)
        except subprocess.TimeoutExpired:
            return False, f"{command[0]} timed out after 5s"
        except Exception as exc:
            return False, str(exc)
        if proc.returncode == 0:
            return True, None
        return False, f"{command[0]} exited with {proc.returncode}"

    try:
        proc = subprocess.run(
            argv,
            input=text,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, None
    return False, proc.stderr.strip() or f"{command[0]} exited with {proc.returncode}"


def _copy_to_clipboard(text: str) -> tuple[bool, str | None]:
    candidates: list[list[str]] = []
    if sys.platform == "darwin":
        candidates.append(["pbcopy"])
    elif sys.platform == "win32":
        candidates.append(["clip"])
    else:
        candidates.extend(
            [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
        )
    last_error: str | None = None
    for command in candidates:
        binary = shutil.which(command[0])
        if binary is None:
            continue
        copied, error = _run_clipboard_command(command, binary, text)
        if copied:
            return True, None
        last_error = error
    return False, last_error or "no clipboard command found"


def _print_capture(capture: dict[str, Any]) -> None:
    title = capture.get("title") or capture.get("id")
    console.print(
        f"- [{capture.get('status')}] {title}  source={capture.get('source')}  id={capture.get('id')}"
    )


@voice_app.command("list", help="List voice captures. Compact alias: `nina vc ls`.")
def voice_list(
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(20, "-n", "--limit", help="Maximum number of captures"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    data = request("GET", "/voice", params=params).json()
    if json_output:
        print_json(data)
        return
    captures = data.get("captures", [])
    if not captures:
        console.print("No voice captures found.")
        return
    for capture in captures:
        _print_capture(capture)


@voice_app.command("show")
def voice_show(
    capture_id: str = typer.Argument(..., help="Voice capture id"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    data = request("GET", f"/voice/{capture_id}").json()
    if json_output:
        print_json(data)
        return
    _print_capture(data)
    for key in (
        "audio_path",
        "duration_seconds",
        "transcript_path",
        "transcript_note_path",
        "language",
        "model",
        "error",
    ):
        value = data.get(key)
        if value not in (None, ""):
            console.print(f"  {key}: {value}")


def _wait_until_stopped(capture_id: str) -> dict[str, Any]:
    while True:
        current = request("GET", f"/voice/{capture_id}").json()
        if current.get("status") != "recording":
            return current
        time.sleep(0.5)


def _transcribe(capture_id: str, *, save_note: bool) -> dict[str, Any]:
    return request(
        "POST",
        f"/voice/{capture_id}/transcribe",
        json={"save_note": save_note},
        timeout=60 * 60,
    ).json()


@voice_app.command("transcribe", help="Transcribe an existing voice capture.")
def voice_transcribe(
    capture_id: str = typer.Argument(..., help="Voice capture id"),
    save_note: bool = typer.Option(False, "--save-note", help="Write a Voice/*.md note."),
    copy: bool = typer.Option(False, "--copy", help="Copy transcript to the system clipboard."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    data = _transcribe(capture_id, save_note=save_note)
    transcript = data.get("transcript", "")
    copied = False
    copy_error = None
    if copy:
        copied, copy_error = _copy_to_clipboard(transcript)
    if json_output:
        payload = dict(data)
        payload["copied"] = copied
        payload["copy_error"] = copy_error
        print_json(payload)
        return
    console.print(transcript)
    if data.get("transcript_note_path"):
        console.print(f"Note: {data['transcript_note_path']}")
    if copy:
        console.print("Copied transcript." if copied else f"Copy failed: {copy_error}")


@voice_app.command("record", help="Record a voice clip, transcribe it, and print the text.")
def voice_record(
    title: str = typer.Argument("", help="Optional capture title"),
    source: str | None = typer.Option(
        None, "-s", "--source", help="Audio source: mic, system, or mixed"
    ),
    device: str | None = typer.Option(
        None, "-d", "--device", help="Fallback audio device name or index"
    ),
    mic_device: str | None = typer.Option(None, "--mic-device", help="Mic device name or index"),
    system_device: str | None = typer.Option(
        None, "--system-device", help="System device name or index"
    ),
    duration: int | None = typer.Option(
        None, "-D", "--duration", help="Auto-stop after this many seconds"
    ),
    save_note: bool = typer.Option(False, "--save-note", help="Write a Voice/*.md note."),
    copy: bool = typer.Option(False, "--copy", help="Copy transcript to the system clipboard."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    payload: dict[str, Any] = {"title": title}
    for key, value in {
        "source": source,
        "device": device,
        "mic_device": mic_device,
        "system_device": system_device,
        "duration_seconds": duration,
    }.items():
        if value is not None:
            payload[key] = value
    capture = request("POST", "/voice/record", json=payload, timeout=20).json()
    capture_id = capture["id"]
    if not json_output:
        console.print(f"Recording {capture_id} -> {capture.get('audio_path', '')}")
    try:
        stopped = _wait_until_stopped(capture_id)
    except KeyboardInterrupt:
        if not json_output:
            console.print("Stopping voice recording...")
        stopped = request("POST", f"/voice/{capture_id}/stop", json={}).json()
    if stopped.get("error"):
        if json_output:
            print_json({"capture": stopped})
        else:
            console.print(f"Voice capture {capture_id} saved with error: {stopped['error']}")
        raise typer.Exit(1)
    result = _transcribe(capture_id, save_note=save_note)
    transcript = result.get("transcript", "")
    copied = False
    copy_error = None
    if copy:
        copied, copy_error = _copy_to_clipboard(transcript)
    if json_output:
        payload = dict(result)
        payload["copied"] = copied
        payload["copy_error"] = copy_error
        print_json(payload)
        return
    console.print(transcript)
    if result.get("transcript_note_path"):
        console.print(f"Note: {result['transcript_note_path']}")
    if copy:
        console.print("Copied transcript." if copied else f"Copy failed: {copy_error}")


_ALIASES: dict[str, str] = {
    "ls": "list",
    "x": "show",
    "r": "record",
    "t": "transcribe",
}
for _alias, _target in _ALIASES.items():
    _callback = next(
        (info.callback for info in voice_app.registered_commands if info.name == _target),
        None,
    )
    if _callback is not None:
        voice_app.command(_alias, hidden=True)(_callback)


__all__ = ["voice_app"]
