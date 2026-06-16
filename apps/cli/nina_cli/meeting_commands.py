from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console

from nina_core.config import (
    get_config_dir,
    get_recordings_path,
    load_effective_config,
)
from nina_core.meetings.recorder import (
    RecorderError,
    boost_wav,
    list_input_devices,
    list_pulse_sources,
    make_audio_source,
    normalize_wav,
    peak_dbfs,
    record_wav,
)

from .api import api_base, headers, request

console = Console()

meeting_app = typer.Typer(
    help=(
        "Meeting recorder, transcription, and summary. "
        'Top-level shortcut: `nina r "title"`. '
        "Sub-app alias: `nina mt ...`."
    ),
    no_args_is_help=True,
)


def _runtime_meetings_dir() -> Path:
    config_dir = get_config_dir(os.environ.get("NINA_PROFILE", "default"))
    return get_recordings_path(config_dir)


def _resolve_config_dir() -> Path:
    return get_config_dir(os.environ.get("NINA_PROFILE", "default"))


def _load_meetings_config() -> tuple[int, int, str, float]:
    config_dir = _resolve_config_dir()
    try:
        config = load_effective_config(config_dir)
        source = config.meetings.default_source or "mic"
        gain = config.meetings.default_gain if config.meetings.default_gain > 0 else 1.0
        return config.meetings.sample_rate, config.meetings.channels, source, gain
    except Exception:
        return 16000, 1, "mic", 1.0


def _resolve_device_index(device: str | None) -> str | int | None:
    if not device:
        return None
    if device.isdigit():
        return int(device)
    return device


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


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
    query = "&".join(f"{k}={v}" for k, v in params)
    response = request("GET", f"/meetings?{query}")
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
        listed = request("GET", "/meetings?status=recording&limit=1").json()
        meetings = listed.get("meetings", [])
        if not meetings:
            console.print("No active recording found.")
            raise typer.Exit(1)
        meeting_id = meetings[0]["id"]
    response = request("POST", f"/meetings/{meeting_id}/stop", json={})
    data = response.json()
    console.print(f"Stopped meeting {meeting_id}.")
    _print_meeting(data)


@meeting_app.command("transcribe", help="Transcribe a meeting (local faster-whisper).")
def meeting_transcribe(meeting_id: str = typer.Argument(..., help="Meeting id")) -> None:
    response = request("POST", f"/meetings/{meeting_id}/transcribe", json={})
    data = response.json()
    status = data.get("status")
    output = data.get("output") or {}
    if status == "completed":
        console.print(
            f"Transcribed {meeting_id} -> {output.get('note_path', '')} ({output.get('char_count', 0)} chars)"
        )
    else:
        _print_json(data)
        raise typer.Exit(1)


@meeting_app.command("summarize", help="Summarize a meeting (configured LLM).")
def meeting_summarize(meeting_id: str = typer.Argument(..., help="Meeting id")) -> None:
    response = request("POST", f"/meetings/{meeting_id}/summarize", json={})
    data = response.json()
    status = data.get("status")
    output = data.get("output") or {}
    if status == "completed":
        console.print(f"Summarized {meeting_id} -> {output.get('note_path', '')}")
    else:
        _print_json(data)
        raise typer.Exit(1)


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
            console.print(
                f"Normalized {audio_file.name}: {before:.1f} dBFS → {after:.1f} dBFS."
            )
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
    """List audio input devices and PulseAudio sources."""
    from nina_core.meetings.recorder import is_portaudio_available, _has_parec

    inputs = list_input_devices()
    sources = list_pulse_sources()
    if inputs:
        console.print("[bold]Input devices (PortAudio):[/bold]")
        for dev in inputs:
            console.print(
                f"  [{dev['index']}] {dev['name']} (host={dev['host']}, channels={dev['channels']})"
            )
    else:
        console.print(
            "No PortAudio input devices found."
            + (
                " Run `pip install sounddevice` (requires libportaudio2)."
                if not is_portaudio_available()
                else ""
            )
        )
    if sources:
        console.print("[bold]PulseAudio / PipeWire sources:[/bold]")
        for src in sources:
            desc = src.get("description") or ""
            is_monitor = ".monitor" in src["name"]
            kind = " (system output)" if is_monitor else " (input)"
            console.print(f"  {src['name']}{kind}{(' — ' + desc) if desc else ''}")
    else:
        if _has_parec():
            console.print(
                "`parec` is available, but `pactl` is not. Run `pacmd list-sources` or `pactl list short sources` to inspect sources manually."
            )
        else:
            console.print(
                "No PulseAudio sources found. Install `pulseaudio-utils` for `parec` and `pactl`."
            )

    if not is_portaudio_available() and sources:
        mic_sources = [s for s in sources if ".monitor" not in s["name"]]
        if mic_sources:
            console.print(
                "\nPortAudio is not available. To record from your mic via PulseAudio, run:"
            )
            first_mic = mic_sources[0]["name"]
            console.print(f'  [cyan]nina r "title" --source parec --device {first_mic}[/cyan]')


def record_meeting(
    title: str,
    source: str | None = None,
    device: str | None = None,
    sample_rate: int = 0,
    channels: int = 0,
    duration: int | None = None,
    gain: float | None = None,
    auto_normalize: bool = False,
) -> None:
    """Run the recording loop and create the meeting note.

    Used by both `nina meeting record` and the top-level `nina r` shortcut.

    `gain` is a linear multiplier applied to the captured WAV after
    recording (e.g. 2.0 = +6 dB, 4.0 = +12 dB). `None` means "use
    `meetings.default_gain` from config". `auto_normalize` auto-gains
    the WAV to peak at -3 dBFS, which is the safest way to fix quiet
    recordings when you don't know the source's level in advance.
    """
    cfg_rate, cfg_channels, cfg_source, cfg_default_gain = _load_meetings_config()
    sr = sample_rate or cfg_rate
    ch = channels or cfg_channels
    chosen_source = source or cfg_source
    effective_gain = gain if gain is not None else cfg_default_gain

    if not title or title.strip().lower() in {"untitled"}:
        title = f"Meeting {time.strftime('%Y-%m-%d %H:%M')}"

    payload: dict[str, Any] = {
        "title": title,
        "source": chosen_source,
        "sample_rate": sr,
        "channels": ch,
        "audio_format": "wav",
    }
    if device:
        payload["device_name"] = device

    try:
        resp = httpx_post("/meetings", json=payload)
    except Exception as exc:
        console.print(f"Failed to start meeting: {exc}")
        raise typer.Exit(1) from None
    meeting = resp
    meeting_id = meeting["id"]
    audio_path = Path(meeting["audio_path"])
    console.print(f"Recording {meeting_id} -> {audio_path}")

    recordings_dir = _runtime_meetings_dir()
    recordings_dir.mkdir(parents=True, exist_ok=True)

    audio_source = make_audio_source(chosen_source, device=_resolve_device_index(device))
    stop_signal = {"requested": False}

    def _request_stop(_signum: int, _frame: object) -> None:
        stop_signal["requested"] = True

    had_signal = False
    try:
        signal.signal(signal.SIGINT, _request_stop)
        had_signal = True
    except ValueError:
        pass
    try:
        signal.signal(signal.SIGTERM, _request_stop)
    except ValueError:
        pass

    started = time.monotonic()
    size_bytes = 0
    record_error: str | None = None
    try:
        # Open the source with the chosen sample rate / channels. This is
        # where `PortAudioSource` creates the input stream and where
        # `PulseSource` forks `parec`. Without this call, the source has
        # no underlying capture device and `stream()` raises immediately.
        audio_source.open(sr, ch)
        size_bytes = record_wav(
            audio_path,
            audio_source,
            sample_rate=sr,
            channels=ch,
            duration_seconds=float(duration) if duration else None,
        )
    except RecorderError as exc:
        record_error = str(exc)
        console.print(f"Recording failed: {exc}")
        console.print(
            "Use `nina meeting devices` to inspect available inputs, "
            "or `--source parec --device <name>` to pick a specific "
            "PulseAudio/PipeWire source. `--source system` captures the "
            "default sink monitor (other people on the call)."
        )
    except KeyboardInterrupt:
        pass
    finally:
        if had_signal:
            try:
                signal.signal(signal.SIGINT, signal.default_int_handler)  # type: ignore[attr-defined]
            except Exception:
                pass

    elapsed = int(time.monotonic() - started)
    # `record_wav` already promoted `.wav.partial` → `.wav` even on
    # failures, so the audio we DID capture is reachable. If a
    # `RecorderError` left us with zero bytes, fall back to inspecting
    # the partial file as a last resort.
    if not audio_path.is_file():
        partial = audio_path.with_suffix(audio_path.suffix + ".partial")
        if partial.is_file() and partial.stat().st_size > 0:
            try:
                partial.replace(audio_path)
                size_bytes = audio_path.stat().st_size
            except Exception:
                pass
    if not audio_path.is_file():
        console.print("No audio file was produced.")
        raise typer.Exit(1) from None

    if size_bytes == 0:
        size_bytes = audio_path.stat().st_size

    # Optional post-capture gain / auto-normalize. The user might be
    # running on PipeWire with a low source volume, so even a perfect
    # capture can come back too quiet. Apply gain to the WAV in-place
    # before the daemon sees it. The on-disk file grows by the same
    # bytes (int math, no header changes).
    if auto_normalize:
        try:
            before_db, after_db = normalize_wav(audio_path, target_dbfs=-3.0)
            if after_db > before_db:
                console.print(
                    f"Auto-normalized: peak {before_db:.1f} dBFS → {after_db:.1f} dBFS."
                )
        except Exception as exc:
            console.print(f"(auto-normalize skipped: {exc})")
    if effective_gain != 1.0:
        try:
            new_peak = boost_wav(audio_path, effective_gain)
            console.print(
                f"Applied gain {effective_gain}x → peak now {new_peak:.1f} dBFS."
            )
        except Exception as exc:
            console.print(f"(gain skipped: {exc})")

    # Quiet-capture hint: if no gain was applied (CLI flag and config
    # default both at 1.0) and the WAV came back unusually quiet, suggest
    # fix-ups. This is the most common first-time-PipeWire problem.
    if effective_gain == 1.0 and not auto_normalize:
        try:
            peak = peak_dbfs(audio_path)
            if peak is not None and peak < -15.0:
                console.print(
                    f"[yellow]Heads up: capture peak is {peak:.1f} dBFS "
                    "(quiet). Try one of:[/yellow]"
                )
                console.print(
                    "  [cyan]nina meeting boost <id> --factor 4.0[/cyan]  "
                    "(+12 dB, safe to rerun)"
                )
                console.print(
                    "  [cyan]nina meeting boost <id> --normalize[/cyan]  "
                    "(auto-gain to -3 dBFS)"
                )
                console.print(
                    "  [cyan]wpctl set-default <source> <vol%>[/cyan]   "
                    "(raise the system source volume for next time)"
                )
        except Exception:
            pass

    try:
        stop_payload: dict[str, Any] = {
            "duration_seconds": elapsed,
            "size_bytes": size_bytes,
        }
        if record_error is not None:
            stop_payload["error"] = record_error
        stopped = httpx_post(f"/meetings/{meeting_id}/stop", json=stop_payload)
    except Exception as exc:
        console.print(f"Failed to finalize meeting: {exc}")
        raise typer.Exit(1) from None

    if record_error is not None:
        console.print(
            f"Meeting {meeting_id} saved with partial audio (error: {record_error}). "
            "Use `nina mt transcribe` and `nina mt summarize` on the partial file."
        )
        raise typer.Exit(1) from None
    note_path = stopped.get("note_path") or ""
    console.print(f"Meeting {meeting_id} saved. Note: {note_path}")


@meeting_app.command(
    "record", help="Record audio and create a meeting note. Stops on Ctrl+C or `--duration`."
)
def meeting_record(
    title: str = typer.Argument("Untitled", help='Meeting title (or "Untitled" to use the date)'),
    source: str | None = typer.Option(
        None,
        "-s",
        "--source",
        help=(
            "Audio source: mic (default), system (sink monitor), or parec "
            "(explicit PulseAudio/PipeWire source via `--device`)"
        ),
    ),
    device: str | None = typer.Option(
        None, "-d", "--device", help="Audio device name or index (see `nina meeting devices`)"
    ),
    sample_rate: int = typer.Option(
        0, "-r", "--sample-rate", help="Sample rate in Hz (default from config, usually 16000)"
    ),
    channels: int = typer.Option(
        0, "-c", "--channels", help="Channel count (default from config, usually 1)"
    ),
    duration: int | None = typer.Option(
        None, "-D", "--duration", help="Auto-stop after this many seconds"
    ),
    gain: float | None = typer.Option(
        None,
        "--gain",
        help=(
            "Linear gain applied to the captured WAV after recording "
            "(e.g. 2.0 = +6 dB, 4.0 = +12 dB). Useful when the source volume is low. "
            "Defaults to `meetings.default_gain` in config.yaml. Pass an explicit "
            "value to override for this call."
        ),
    ),
    auto_normalize: bool = typer.Option(
        False,
        "--auto-normalize",
        help="Auto-gain the WAV so its peak hits -3 dBFS (overrides --gain if both are set).",
    ),
) -> None:
    """Record audio from the local machine and create a meeting note.

    Captures your mic by default, or the system audio sink (PulseAudio/PipeWire
    monitor) when `--source system` is set, which is what you want for capturing
    other participants in a Teams, Zoom, or Meet call. Use `--source parec`
    with `--device <source-name>` to target a specific PulseAudio/PipeWire
    source (useful on systems where libportaudio2 is missing but PipeWire's
    pulse-compat layer is present).

    If the captured audio is too quiet (e.g. a low PipeWire source volume),
    pass `--gain 4.0` (+12 dB) or `--auto-normalize` (auto-gain to
    -3 dBFS). You can also boost an existing file with
    `nina meeting boost <id>`.

    Examples:

        nina meeting record "Quarterly planning"

        nina r "Standup" -s system

        nina r "Mic-only" -s parec -d alsa_input.pci-0000_00_1f.3.analog-stereo

        nina meeting record --duration 1800

        nina r "Quiet room" --gain 4.0

        nina r "Whatever volume" --auto-normalize
    """
    record_meeting(
        title=title,
        source=source,
        device=device,
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        gain=gain,
        auto_normalize=auto_normalize,
    )


def httpx_post(path: str, **kwargs: Any) -> dict[str, Any]:
    response = httpx.post(f"{api_base()}{path}", headers=headers(), timeout=20, **kwargs)
    if response.status_code >= 400:
        detail = None
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = response.text
        raise RuntimeError(f"{response.status_code} {detail}")
    return response.json()


# Register a handful of compact aliases for the most common meeting subcommands.
# `nina r` (top-level) is the main shortcut; these short aliases make the
# `nina mt ...` path less verbose for scripting.
_ALIASES: dict[str, str] = {
    "r": "record",
    "ls": "list",
    "rm": "delete",
    "t": "transcribe",
    "m": "summarize",
    "s": "stop",
    "o": "open",
    "p": "play",
    "x": "show",
}
for _alias, _target in _ALIASES.items():
    _callback = next(
        (info.callback for info in meeting_app.registered_commands if info.name == _target),
        None,
    )
    if _callback is not None:
        meeting_app.command(_alias, hidden=True)(_callback)


__all__ = ["meeting_app", "record_meeting"]
