from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_recordings_path
from nina_core.meetings.service import MeetingService
from nina_core.obsidian.service import ObsidianService

pytestmark = pytest.mark.unit


def test_meeting_service_lifecycle(isolated_config: Path) -> None:
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"
    service = MeetingService(str(db_path), recordings, vault)

    started = service.start(title="Standup", source="mic", sample_rate=16000, channels=1)
    meeting_id = started["id"]
    assert started["status"] == "recording"
    assert started["audio_path"].endswith(".wav")
    audio_file = Path(started["audio_path"])
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"RIFF....WAVE")

    stopped = service.stop(meeting_id, duration_seconds=42, size_bytes=16)
    assert stopped is not None
    assert stopped["status"] == "stopped"
    assert stopped["duration_seconds"] == 42
    assert stopped["audio_size_bytes"] == 16
    note_path = isolated_config / "vault" / stopped["note_path"]
    assert note_path.is_file()

    listed = service.list()
    assert any(m["id"] == meeting_id for m in listed)

    by_status = service.list(status="stopped")
    assert any(m["id"] == meeting_id for m in by_status)

    detail = service.get(meeting_id)
    assert detail is not None
    assert detail["title"] == "Standup"


def test_meeting_service_stop_is_idempotent(isolated_config: Path) -> None:
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"
    service = MeetingService(str(db_path), recordings, vault)

    started = service.start(title="Idempotent stop", source="mic", sample_rate=16000, channels=1)
    meeting_id = started["id"]
    audio_file = Path(started["audio_path"])
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"RIFF....WAVE")

    first = service.stop(meeting_id, duration_seconds=12, size_bytes=16)
    assert first is not None
    second = service.stop(meeting_id, error="late error")
    assert second is not None
    assert second["status"] == "stopped"
    assert second["error"] == "late error"
    assert second["note_path"] == first["note_path"]


def test_meeting_service_update_status(isolated_config: Path) -> None:
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"
    service = MeetingService(str(db_path), recordings, vault)
    started = service.start(title="Update demo")
    meeting_id = started["id"]
    updated = service.update_status(
        meeting_id,
        status="transcribed",
        transcript_path=str(recordings / "demo.txt"),
        workflow_run_id="wf_123",
    )
    assert updated is not None
    assert updated["status"] == "transcribed"
    assert updated["transcript_path"].endswith("demo.txt")
    assert updated["workflow_run_id"] == "wf_123"


def test_meeting_service_soft_delete_moves_note(isolated_config: Path) -> None:
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"
    service = MeetingService(str(db_path), recordings, vault)
    started = service.start(title="Delete me")
    meeting_id = started["id"]
    service.stop(meeting_id, duration_seconds=10)
    note_file = vault / started["note_path"]
    assert note_file.is_file()
    ok = service.delete(meeting_id)
    assert ok is True
    assert not note_file.is_file()
    assert (vault / "System" / "Deleted" / note_file.name).is_file()
    assert service.get(meeting_id) is None


def test_meeting_note_has_pending_sections(isolated_config: Path) -> None:
    vault = isolated_config / "vault"
    obsidian = ObsidianService(vault)
    obsidian.create_meeting_note(
        meeting_id="mt_demo",
        title="Section demo",
        started_at="2026-06-14T09:00:00+00:00",
        ended_at="2026-06-14T09:30:00+00:00",
        duration_seconds=1800,
        source="system",
        audio_path="/tmp/mt_demo.wav",
        transcript_status="pending",
        summary_status="pending",
    )
    note_path = vault / "Meetings" / "2026-06-14 - section-demo.md"
    assert note_path.is_file()
    text = note_path.read_text()
    assert "## Transcript" in text
    assert "## Summary" in text
    assert "## Action items" in text
    assert "## Decisions" in text
    assert "_Transcription pending._" in text
