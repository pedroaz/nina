from __future__ import annotations

import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import typer

from nina_core.config import get_config_dir, load_effective_config
from nina_core.meetings.recorder import (
    boost_wav,
    list_input_devices,
    normalize_wav,
    peak_dbfs,
)
from nina_core.meetings.backends import list_loopback_devices

from .api import request
from .output import console, print_json

meeting_app = typer.Typer(
    help=(
        "Meeting recorder, transcription, and summary. "
        'Top-level shortcut: `nina r "title"`. '
        "Sub-app alias: `nina mt ...`."
    ),
    no_args_is_help=True,
)


def _resolve_config_dir() -> Path:
    return get_config_dir(os.environ.get("NINA_PROFILE", "default"))


def _print_json(data: Any) -> None:
    print_json(data)


def _print_meeting(meeting: dict[str, Any]) -> None:
    title = meeting.get("title") or meeting.get("id")
    status = meeting.get("status")
    source = meeting.get("source")
    duration = meeting.get("duration_seconds")
    duration_str = ""
    if isinstance(duration, int):
        duration_str = f" ({duration // 60}m {duration % 60:02d}s)"
    console.print(f"- [{status}] {title}{duration_str}  source={source}  id={meeting.get('id')}")


@meeting_app.command("list", help="List meetings. Compact alias: `nina mt ls`.")
def meeting_list(
    status: str | None = typer.Option(
        None,
        "-s",
        "--status",
        help="Filter by status (recording|stopped|transcribed|summarized|failed)",
    ),
    limit: int = typer.Option(20, "-n", "--limit", help="Maximum number of meetings"),
    json_output: bool = typer.Option(False, "-j", "--json", help="Print JSON"),
) -> None:
    params: list[tuple[str, str]] = [("limit", str(limit))]
    if status:
        params.append(("status", status))
    response = request("GET", "/meetings", params=params)
    data = response.json()
    if json_output:
        _print_json(data)
        return
    meetings = data.get("meetings", [])
    if not meetings:
        console.print("No meetings found.")
        return
    for meeting in meetings:
        _print_meeting(meeting)


@meeting_app.command("show")
def meeting_show(
    meeting_id: str = typer.Argument(..., help="Meeting id"),
    json_output: bool = typer.Option(False, "-j", "--json", help="Print JSON"),
) -> None:
    response = request("GET", f"/meetings/{meeting_id}")
    data = response.json()
    if json_output:
        _print_json(data)
        return
    _print_meeting(data)
    for key in (
        "audio_path",
        "transcript_path",
        "summary_path",
        "note_path",
        "started_at",
        "ended_at",
        "device_name",
        "error",
    ):
        value = data.get(key)
        if value:
            console.print(f"  {key}: {value}")


@meeting_app.command("open", help="Open the meeting note in Obsidian.")
def meeting_open(meeting_id: str = typer.Argument(..., help="Meeting id")) -> None:
    response = request("GET", f"/meetings/{meeting_id}")
    data = response.json()
    note_path = data.get("note_path")
    if not note_path:
        console.print(f"Meeting {meeting_id} has no note yet.")
        raise typer.Exit(1)
    request("POST", "/search/open", json={"path": note_path})
    console.print(f"Requested Obsidian to open {note_path}")


@meeting_app.command("stop", help="Stop the active recording (or the meeting with the given id).")
def meeting_stop(
    meeting_id: str | None = typer.Argument(
        None, help="Meeting id (defaults to the most recent recording)"
    ),
) -> None:
    if meeting_id is None:
        listed = request("GET", "/meetings", params={"status": "recording", "limit": 1}).json()
        meetings = listed.get("meetings", [])
        if not meetings:
            console.print("No active recording found.")
            raise typer.Exit(1)
        meeting_id = meetings[0]["id"]
    response = request("POST", f"/meetings/{meeting_id}/stop", json={})
    data = response.json()
    console.print(f"Stopped meeting {meeting_id}.")
    _print_meeting(data)


@meeting_app.command(
    "pipeline",
    help=(
        "Transcribe + summarize a meeting back-to-back. Writes the "
        "transcript to Meetings/<date> - <title> - Transcript.md, the summary "
        "to Meetings/<date> - <title> - Summary.md, and links both from the "
        "hub note Meetings/<date> - <title>.md. Bound to Ctrl+E in the TUI."
    ),
)
def meeting_pipeline(meeting_id: str = typer.Argument(..., help="Meeting id")) -> None:
    response = request("POST", f"/meetings/{meeting_id}/pipeline", json={})
    data = response.json()
    status = data.get("status")
    output = data.get("output") or {}
    if status != "completed":
        _print_json(data)
        raise typer.Exit(1)
    hub = output.get("note_path", "")
    transcript = output.get("transcript_note_path", "")
    summary = output.get("summary_note_path", "")
    console.print(f"Pipeline complete for {meeting_id}.")
    if hub:
        console.print(f"  Hub:       {hub}")
    if transcript:
        console.print(f"  Transcript: {transcript}")
    if summary:
        console.print(f"  Summary:   {summary}")


@meeting_app.command("delete", help="Soft-delete a meeting (note moves to System/Deleted).")
def meeting_delete(meeting_id: str = typer.Argument(..., help="Meeting id")) -> None:
    response = request("DELETE", f"/meetings/{meeting_id}")
    data = response.json()
    if data.get("deleted"):
        console.print(f"Deleted meeting {meeting_id}.")
    else:
        console.print("Delete failed.")
        raise typer.Exit(1)


def resolve_audio_path(audio_path: str) -> Path:
    """Return a usable path for a meeting's audio, recovering from a
    stranded `.wav.partial` capture.

    If the final `.wav` is missing but the `.wav.partial` is present
    (recorder was killed before it could promote), the partial is renamed
    to the final path in place. Raises `FileNotFoundError` when neither
    file is usable.
    """
    if not audio_path:
        raise FileNotFoundError("Meeting has no audio_path recorded.")
    audio_file = Path(audio_path)
    if audio_file.is_file():
        return audio_file
    partial = audio_file.with_suffix(audio_file.suffix + ".partial")
    if partial.is_file() and partial.stat().st_size > 0:
        partial.replace(audio_file)
        return audio_file
    raise FileNotFoundError(f"Audio not found (looked for {audio_file.name} and {partial.name})")


@meeting_app.command("play", help="Play the meeting's audio file in the system player.")
def meeting_play(meeting_id: str = typer.Argument(..., help="Meeting id")) -> None:
    response = request("GET", f"/meetings/{meeting_id}")
    data = response.json()
    audio_path = data.get("audio_path")
    try:
        audio_file = resolve_audio_path(audio_path)
    except FileNotFoundError as exc:
        console.print(f"Cannot play meeting {meeting_id}: {exc}")
        raise typer.Exit(1) from None
    config_dir = _resolve_config_dir()
    try:
        cfg = load_effective_config(config_dir)
        play_cmd = cfg.meetings.play_command.format(path=str(audio_file))
    except Exception:
        play_cmd = str(audio_file)
    try:
        binary = play_cmd.split()[0]
        subprocess.Popen([binary, *play_cmd.split()[1:]])
    except Exception as exc:
        console.print(f"Failed to launch player: {exc}")
        raise typer.Exit(1) from None
    console.print(f"Playing {audio_file}")


@meeting_app.command(
    "boost",
    help=(
        "Apply gain or auto-normalize to the meeting's WAV in place. "
        "Use this when the recording came out too quiet because the source "
        "volume was low (common with PipeWire/PulseAudio sources). "
        "Run `nina meeting boost <id> --dry-run` to see the current dBFS first."
    ),
)
def meeting_boost(
    meeting_id: str = typer.Argument(..., help="Meeting id"),
    factor: float = typer.Option(
        2.0,
        "--factor",
        help="Linear gain factor (e.g. 2.0 = +6 dB, 4.0 = +12 dB). Ignored with --normalize.",
    ),
    normalize: bool = typer.Option(
        False,
        "--normalize",
        help="Auto-gain so the WAV's peak hits -3 dBFS (overrides --factor).",
    ),
    target_dbfs: float = typer.Option(
        -3.0,
        "--target-dbfs",
        help="Target peak dBFS used with --normalize (default: -3.0).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report the current peak dBFS but don't modify the file.",
    ),
) -> None:
    """Boost (or normalize) a meeting's WAV file in place."""
    response = request("GET", f"/meetings/{meeting_id}")
    data = response.json()
    audio_path = data.get("audio_path")
    try:
        audio_file = resolve_audio_path(audio_path)
    except FileNotFoundError as exc:
        console.print(f"Cannot boost meeting {meeting_id}: {exc}")
        raise typer.Exit(1) from None

    current_db = peak_dbfs(audio_file)
    if current_db is None:
        console.print(f"{audio_file.name} is silent or unreadable.")
        raise typer.Exit(1) from None
    console.print(f"Current peak: {current_db:.1f} dBFS")

    if dry_run:
        if normalize:
            console.print(
                f"Would normalize to {target_dbfs:.1f} dBFS (gain ~{10 ** ((target_dbfs - current_db) / 20):.2f}x)."
            )
        else:
            console.print(
                f"Would boost {factor}x (target ~{current_db + 20 * math.log10(factor):.1f} dBFS)."
            )
        return

    try:
        if normalize:
            before, after = normalize_wav(audio_file, target_dbfs=target_dbfs)
            console.print(f"Normalized {audio_file.name}: {before:.1f} dBFS → {after:.1f} dBFS.")
        else:
            new_peak = boost_wav(audio_file, factor)
            console.print(
                f"Boosted {audio_file.name} by {factor}x: "
                f"{current_db:.1f} dBFS → {new_peak:.1f} dBFS."
            )
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"Boost failed: {exc}")
        raise typer.Exit(1) from None


@meeting_app.command("devices")
def meeting_devices() -> None:
    """List local audio inputs and loopback devices via the soundcard backend."""

    inputs = list_input_devices()
    loopback = list_loopback_devices()
    if inputs:
        console.print("[bold]Input devices (soundcard):[/bold]")
        for dev in inputs:
            console.print(f"  {dev['name']}")
    else:
        console.print("No input devices found.")

    if loopback:
        console.print("[bold]System / loopback devices:[/bold]")
        for dev in loopback:
            console.print(f"  {dev['name']}")
    elif sys.platform == "darwin":
        console.print(
            "On macOS 14.4+, system audio is captured via the Core Audio Process Tap "
            "(no virtual device required). On older macOS, install BlackHole for loopback."
        )

    if not inputs:
        console.print("")
        console.print("Connect a microphone and run `nina meeting devices` again.")


def record_meeting(
    title: str,
    source: str | None = None,
    device: str | None = None,
    mic_device: str | None = None,
    system_device: str | None = None,
    sample_rate: int = 0,
    channels: int = 0,
    duration: int | None = None,
    gain: float | None = None,
    auto_normalize: bool | None = None,
    normalize_target_dbfs: float | None = None,
    noise_reduction: str | None = None,
) -> None:
    """Start a daemon-owned recording and wait until it finishes.

    The daemon owns the capture backend. The CLI just starts the session,
    waits for the row to stop, and asks the daemon to stop it if the user
    hits Ctrl+C.
    """
    if not title or title.strip().lower() in {"untitled"}:
        title = f"Meeting {time.strftime('%Y-%m-%d %H:%M')}"

    if device is None and mic_device is None and system_device is None:
        try:
            config = load_effective_config(get_config_dir())
        except Exception:
            config = None
        if config is not None and getattr(config.meetings, "default_device", None):
            device = config.meetings.default_device

    payload: dict[str, Any] = {"title": title}
    if source is not None:
        payload["source"] = source
    if device is not None:
        payload["device"] = device
    if mic_device is not None:
        payload["mic_device"] = mic_device
    if system_device is not None:
        payload["system_device"] = system_device
    if sample_rate > 0:
        payload["sample_rate"] = sample_rate
    if channels > 0:
        payload["channels"] = channels
    if duration is not None:
        payload["duration_seconds"] = duration
    if gain is not None:
        payload["gain"] = gain
    if auto_normalize is not None:
        payload["auto_normalize"] = auto_normalize
    if normalize_target_dbfs is not None:
        payload["normalize_target_dbfs"] = normalize_target_dbfs
    if noise_reduction is not None:
        payload["noise_reduction"] = noise_reduction

    try:
        meeting = httpx_post("/meetings/record", json=payload)
    except Exception as exc:
        console.print(f"Failed to start meeting: {exc}")
        raise typer.Exit(1) from None

    meeting_id = meeting["id"]
    console.print(f"Recording {meeting_id} -> {meeting.get('audio_path', '')}")
    if meeting.get("device_name"):
        console.print(f"Source: {meeting.get('source')} ({meeting.get('device_name')})")

    try:
        while True:
            current = request("GET", f"/meetings/{meeting_id}").json()
            status = current.get("status")
            if status != "recording":
                meeting = current
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        console.print("Stopping recording...")
        try:
            meeting = request("POST", f"/meetings/{meeting_id}/stop", json={}).json()
        except Exception as exc:
            console.print(f"Failed to stop meeting: {exc}")
            raise typer.Exit(1) from None

    if meeting.get("error"):
        console.print(f"Meeting {meeting_id} saved with error: {meeting['error']}")
        raise typer.Exit(1) from None
    note_path = meeting.get("note_path") or ""
    console.print(f"Meeting {meeting_id} saved. Note: {note_path}")


@meeting_app.command(
    "record",
    help="Record audio through the daemon and create a meeting note. Stops on Ctrl+C or `--duration`.",
)
def meeting_record(
    title: str = typer.Argument("Untitled", help='Meeting title (or "Untitled" to use the date)'),
    source: str | None = typer.Option(
        None,
        "-s",
        "--source",
        help=(
            "Audio source: mic, system, or mixed. "
            "On macOS 14.4+ `system` uses the Core Audio Process Tap (no BlackHole). "
            "On Linux/Windows it uses the OS-native loopback (Pulse monitor / WASAPI loopback)."
        ),
    ),
    device: str | None = typer.Option(
        None, "-d", "--device", help="Fallback audio device name or index"
    ),
    mic_device: str | None = typer.Option(
        None, "--mic-device", help="Mic device name or index (overrides --device for mic capture)"
    ),
    system_device: str | None = typer.Option(
        None,
        "--system-device",
        help="System/loopback device name or index (overrides --device for system capture)",
    ),
    sample_rate: int = typer.Option(
        0, "-r", "--sample-rate", help="Sample rate in Hz (default from config)"
    ),
    channels: int = typer.Option(0, "-c", "--channels", help="Channel count (default from config)"),
    duration: int | None = typer.Option(
        None, "-D", "--duration", help="Auto-stop after this many seconds"
    ),
    gain: float | None = typer.Option(
        None,
        "--gain",
        help=(
            "Linear gain applied after recording (e.g. 4.0 = +12 dB). "
            "Defaults to the daemon config if omitted."
        ),
    ),
    auto_normalize: bool | None = typer.Option(
        None,
        "--auto-normalize/--no-auto-normalize",
        help="Auto-gain the WAV so its peak hits the configured dBFS target.",
    ),
    normalize_target_dbfs: float | None = typer.Option(
        None,
        "--normalize-target-dbfs",
        help="Peak dBFS target used when auto-normalizing.",
    ),
    noise_reduction: str | None = typer.Option(
        None,
        "--noise-reduction",
        help="Optional noise reduction mode: off or ffmpeg.",
    ),
) -> None:
    """Record audio from the local machine through the daemon and create a meeting note."""
    record_meeting(
        title=title,
        source=source,
        device=device,
        mic_device=mic_device,
        system_device=system_device,
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        gain=gain,
        auto_normalize=auto_normalize,
        normalize_target_dbfs=normalize_target_dbfs,
        noise_reduction=noise_reduction,
    )


def httpx_post(path: str, **kwargs: Any) -> dict[str, Any]:
    return request("POST", path, timeout=20, **kwargs).json()


# Register a handful of compact aliases for the most common meeting subcommands.
# `nina r` (top-level) is the main shortcut; these short aliases make the
# `nina mt ...` path less verbose for scripting. The `e` alias matches the
# TUI's `Ctrl+E` keybind so the muscle memory is the same in both clients.
_ALIASES: dict[str, str] = {
    "r": "record",
    "ls": "list",
    "rm": "delete",
    "s": "stop",
    "o": "open",
    "p": "play",
    "x": "show",
    "e": "pipeline",
}
for _alias, _target in _ALIASES.items():
    _callback = next(
        (info.callback for info in meeting_app.registered_commands if info.name == _target),
        None,
    )
    if _callback is not None:
        meeting_app.command(_alias, hidden=True)(_callback)


__all__ = ["meeting_app", "record_meeting"]
