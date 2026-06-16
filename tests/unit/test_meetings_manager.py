from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import load_effective_config
from nina_core.meetings.manager import MeetingRecordingManager, RecordingRequest
from nina_core.meetings.recorder import NullAudioSource

pytestmark = pytest.mark.unit


def test_meeting_recording_manager_start_and_stop(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_effective_config(isolated_config)
    manager = MeetingRecordingManager()

    monkeypatch.setattr(
        "nina_core.meetings.manager.make_audio_source",
        lambda *args, **kwargs: NullAudioSource(),
    )

    started = manager.start(
        config=config,
        config_dir=isolated_config,
        request=RecordingRequest(title="Daemon-owned recording", duration_seconds=1),
    )
    assert started["status"] == "recording"

    stopped = manager.stop(started["id"], timeout_seconds=5)
    assert stopped is not None
    assert stopped["status"] == "stopped"
    assert stopped["note_path"].startswith("Meetings/")
    assert (isolated_config / "vault" / stopped["note_path"]).is_file()


def test_meeting_recording_manager_defaults_to_mic_on_macos(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_effective_config(isolated_config)
    config.meetings.default_source = "mixed"
    manager = MeetingRecordingManager()
    requested_sources: list[str] = []

    def fake_source(source: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        requested_sources.append(source)
        return NullAudioSource()

    monkeypatch.setattr("nina_core.meetings.manager.sys.platform", "darwin")
    monkeypatch.setattr("nina_core.meetings.manager.make_audio_source", fake_source)

    started = manager.start(
        config=config,
        config_dir=isolated_config,
        request=RecordingRequest(title="Mac recording", duration_seconds=1),
    )
    try:
        assert requested_sources == ["mic"]
        assert started["source"] == "mic"
    finally:
        manager.stop(started["id"], timeout_seconds=5)
