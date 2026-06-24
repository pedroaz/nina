from __future__ import annotations

import time
from typing import cast

import frontmatter
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _wait_until_stopped(
    api_client: TestClient,
    auth_headers: dict[str, str],
    capture_id: str,
) -> dict[str, object]:
    deadline = time.monotonic() + 10
    payload: dict[str, object] = {}
    while time.monotonic() < deadline:
        fetched = api_client.get(f"/voice/{capture_id}", headers=auth_headers)
        assert fetched.status_code == 200
        payload = cast(dict[str, object], fetched.json())
        if payload.get("status") != "recording":
            return payload
        time.sleep(0.05)
    raise AssertionError(f"voice capture did not stop: {payload}")


def test_voice_recording_endpoint_creates_and_finishes_capture(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.meetings.recorder import NullAudioSource

    monkeypatch.setattr(
        "nina_core.voice.manager.make_audio_source",
        lambda *args, **kwargs: NullAudioSource(),
    )

    started = api_client.post(
        "/voice/record",
        headers=auth_headers,
        json={"title": "Quick dictation", "duration_seconds": 1},
    )
    assert started.status_code == 200, started.json()
    capture_id = started.json()["id"]
    assert capture_id.startswith("vc_")
    assert started.json()["status"] == "recording"
    assert "/voice/" in started.json()["audio_path"]

    payload = _wait_until_stopped(api_client, auth_headers, capture_id)
    assert payload["status"] == "stopped"
    assert payload["audio_size_bytes"]

    listed = api_client.get("/voice", headers=auth_headers)
    assert listed.status_code == 200
    assert any(capture["id"] == capture_id for capture in listed.json()["captures"])


def test_voice_transcribe_writes_transcript_and_optional_note(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm import transcription as tr
    from nina_core.meetings.recorder import NullAudioSource

    monkeypatch.setattr(
        "nina_core.voice.manager.make_audio_source",
        lambda *args, **kwargs: NullAudioSource(),
    )
    monkeypatch.setattr(
        "nina_core.voice.service.build_transcription_provider",
        lambda **kwargs: tr.NullTranscriptionProvider(text="voice transcript"),
    )

    started = api_client.post(
        "/voice/record",
        headers=auth_headers,
        json={"title": "Paste this", "duration_seconds": 1},
    )
    assert started.status_code == 200, started.json()
    capture_id = started.json()["id"]
    _wait_until_stopped(api_client, auth_headers, capture_id)

    transcribed = api_client.post(
        f"/voice/{capture_id}/transcribe",
        headers=auth_headers,
        json={"save_note": True},
    )
    assert transcribed.status_code == 200, transcribed.json()
    payload = transcribed.json()
    assert payload["transcript"] == "voice transcript"
    assert payload["transcript_path"].endswith(".txt")
    assert payload["transcript_note_path"].startswith("Voice/")
    assert payload["capture"]["status"] == "transcribed"

    note_path = isolated_config / "vault" / payload["transcript_note_path"]
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["nina_type"] == "voice_capture"
    assert note.metadata["nina_id"] == capture_id
    assert "voice transcript" in note.content


def test_config_endpoint_includes_voice_settings(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = api_client.get("/config", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["voice"] == {
        "global_hotkey_enabled": False,
        "global_hotkey": "Ctrl+Alt+Space",
        "insert_mode": "clipboard_paste",
        "preserve_clipboard": True,
    }
