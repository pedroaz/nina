from __future__ import annotations

import time
import wave
from pathlib import Path

import frontmatter
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _write_silence_wav(path: Path, seconds: float = 0.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frame = b"\x00\x00"
        for _ in range(int(sample_rate * seconds)):
            writer.writeframes(frame)


def test_meeting_lifecycle_start_stop_show_list(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
) -> None:
    started = api_client.post(
        "/meetings",
        headers=auth_headers,
        json={"title": "Quarterly planning", "source": "mic", "sample_rate": 16000},
    )
    assert started.status_code == 200
    meeting_id = started.json()["id"]
    assert started.json()["status"] == "recording"

    stopped = api_client.post(
        f"/meetings/{meeting_id}/stop",
        headers=auth_headers,
        json={"duration_seconds": 60, "size_bytes": 4096},
    )
    assert stopped.status_code == 200
    payload = stopped.json()
    assert payload["status"] == "stopped"
    assert payload["duration_seconds"] == 60
    assert payload["audio_size_bytes"] == 4096
    assert payload["note_path"].startswith("Meetings/")

    note_path = isolated_config / "vault" / payload["note_path"]
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["nina_type"] == "meeting"
    assert note.metadata["nina_id"] == meeting_id
    assert note.metadata["transcript_status"] == "pending"
    assert note.metadata["summary_status"] == "pending"

    listed = api_client.get("/meetings", headers=auth_headers)
    assert listed.status_code == 200
    assert any(m["id"] == meeting_id for m in listed.json()["meetings"])

    fetched = api_client.get(f"/meetings/{meeting_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Quarterly planning"


def test_daemon_owned_recording_endpoint_creates_and_finishes_meeting(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.meetings.recorder import NullAudioSource

    monkeypatch.setattr(
        "nina_core.meetings.manager.make_audio_source",
        lambda *args, **kwargs: NullAudioSource(),
    )

    started = api_client.post(
        "/meetings/record",
        headers=auth_headers,
        json={"title": "Daemon-owned recording", "duration_seconds": 1},
    )
    assert started.status_code == 200, started.json()
    meeting_id = started.json()["id"]
    assert started.json()["status"] == "recording"

    deadline = time.monotonic() + 10
    payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        fetched = api_client.get(f"/meetings/{meeting_id}", headers=auth_headers)
        assert fetched.status_code == 200
        payload = fetched.json()
        if payload.get("status") != "recording":
            break
        time.sleep(0.05)

    assert payload is not None
    assert payload["status"] == "stopped"
    assert payload["note_path"].startswith("Meetings/")
    note_path = isolated_config / "vault" / payload["note_path"]
    assert note_path.is_file()


def test_transcribe_meeting_workflow_writes_note_section(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm import transcription as tr

    monkeypatch.setattr(
        tr,
        "build_transcription_provider",
        lambda **kwargs: tr.NullTranscriptionProvider(text="hello from whisper"),
    )

    started = api_client.post(
        "/meetings",
        headers=auth_headers,
        json={"title": "Transcribe me"},
    )
    assert started.status_code == 200
    meeting_id = started.json()["id"]
    audio_path = Path(started.json()["audio_path"])
    _write_silence_wav(audio_path, seconds=0.2)

    stopped = api_client.post(
        f"/meetings/{meeting_id}/stop",
        headers=auth_headers,
        json={"duration_seconds": 30, "size_bytes": 1024},
    )
    assert stopped.status_code == 200
    note_relpath = stopped.json()["note_path"]
    note_path = isolated_config / "vault" / note_relpath

    transcribe = api_client.post(
        f"/meetings/{meeting_id}/transcribe",
        headers=auth_headers,
        json={},
    )
    assert transcribe.status_code == 200, transcribe.json()
    assert transcribe.json()["status"] == "completed"
    payload = transcribe.json()["output"]
    assert payload["char_count"] == len("hello from whisper")

    note = frontmatter.loads(note_path.read_text())
    assert "hello from whisper" in note.content
    assert note.metadata["transcript_status"] == "done"

    transcript = api_client.get(f"/meetings/{meeting_id}/transcript", headers=auth_headers)
    assert transcript.status_code == 200
    assert "hello from whisper" in transcript.json()["transcript"]


def test_summarize_meeting_workflow_uses_fake_llm(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm.provider import FakeProvider, LLMService

    fake = FakeProvider()
    fake.queue_text(
        "## Summary\n"
        "- We agreed on a Q3 dashboard launch.\n"
        "## Action items\n"
        "- Alex drafts the design.\n"
        "## Decisions\n"
        "- Ship in Q3.\n"
    )

    def _patched_init(self, db_path, provider=None, config=None) -> None:  # type: ignore[no-untyped-def]
        self.db_path = db_path
        from nina_core.config.settings import LLMConfig

        self.config = config or LLMConfig(provider="fake", model="fake")
        self.provider = fake

    monkeypatch.setattr(LLMService, "__init__", _patched_init)

    started = api_client.post(
        "/meetings",
        headers=auth_headers,
        json={"title": "Summarize me"},
    )
    assert started.status_code == 200
    meeting_id = started.json()["id"]
    audio_path = Path(started.json()["audio_path"])
    _write_silence_wav(audio_path, seconds=0.2)

    stopped = api_client.post(
        f"/meetings/{meeting_id}/stop",
        headers=auth_headers,
        json={"duration_seconds": 90, "size_bytes": 8192},
    )
    assert stopped.status_code == 200
    note_relpath = stopped.json()["note_path"]
    note_path = isolated_config / "vault" / note_relpath

    # Pre-populate a transcript so the workflow has something to summarize.
    (Path(audio_path).with_suffix(".txt")).write_text("We agreed on Q3.")

    summarize = api_client.post(
        f"/meetings/{meeting_id}/summarize",
        headers=auth_headers,
        json={},
    )
    assert summarize.status_code == 200, summarize.json()
    assert summarize.json()["status"] == "completed"
    note = frontmatter.loads(note_path.read_text())
    assert "## Summary" in note.content
    assert "Q3 dashboard launch" in note.content
    assert note.metadata["summary_status"] == "done"


def test_soft_delete_moves_note(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
) -> None:
    started = api_client.post(
        "/meetings",
        headers=auth_headers,
        json={"title": "Delete me"},
    )
    assert started.status_code == 200
    meeting_id = started.json()["id"]
    stopped = api_client.post(
        f"/meetings/{meeting_id}/stop",
        headers=auth_headers,
        json={"duration_seconds": 10, "size_bytes": 128},
    )
    note_relpath = stopped.json()["note_path"]
    note_path = isolated_config / "vault" / note_relpath
    assert note_path.is_file()

    deleted = api_client.delete(f"/meetings/{meeting_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert not note_path.is_file()
    assert (isolated_config / "vault" / "System" / "Deleted" / note_path.name).is_file()


def test_config_endpoint_includes_transcription_and_meetings(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.get("/config", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert "transcription" in payload
    assert "meetings" in payload
    assert payload["transcription"]["backend"] in {"local_whisper", "null"}
    assert payload["meetings"]["default_source"] in {"mic", "system", "mixed"}
    assert isinstance(payload["meetings"]["auto_normalize"], bool)
    assert payload["meetings"]["noise_reduction"] in {"off", "ffmpeg"}


def test_workflow_list_includes_meetings(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.get("/workflows", headers=auth_headers)
    assert response.status_code == 200
    names = response.json()
    assert "transcribe-meeting" in names
    assert "summarize-meeting" in names


def test_stop_endpoint_records_error_field(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
) -> None:
    """Regression: when the CLI is killed mid-recording, it POSTs the
    recorder error to the stop endpoint so the row's `error` column
    surfaces the failure. Without this, the user has no way to tell
    that a meeting has only a partial .wav.partial.
    """
    started = api_client.post(
        "/meetings",
        headers=auth_headers,
        json={"title": "Recorder error demo"},
    )
    assert started.status_code == 200
    meeting_id = started.json()["id"]

    stopped = api_client.post(
        f"/meetings/{meeting_id}/stop",
        headers=auth_headers,
        json={"duration_seconds": 0, "size_bytes": 0, "error": "killed by SIGKILL"},
    )
    assert stopped.status_code == 200
    assert stopped.json()["error"] == "killed by SIGKILL"

    detail = api_client.get(f"/meetings/{meeting_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["error"] == "killed by SIGKILL"
