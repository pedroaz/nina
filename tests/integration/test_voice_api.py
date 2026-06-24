from __future__ import annotations

import time
from pathlib import Path
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
    post_processing_called = {"denoise": False, "normalize": False, "boost": False}

    def _mark_denoise(*args: object, **kwargs: object) -> bool:
        post_processing_called["denoise"] = True
        return False

    def _mark_normalize(*args: object, **kwargs: object) -> tuple[float, float]:
        post_processing_called["normalize"] = True
        return (0.0, 0.0)

    def _mark_boost(*args: object, **kwargs: object) -> float:
        post_processing_called["boost"] = True
        return 0.0

    monkeypatch.setattr("nina_core.voice.manager.apply_ffmpeg_noise_reduction", _mark_denoise)
    monkeypatch.setattr("nina_core.voice.manager.normalize_wav", _mark_normalize)
    monkeypatch.setattr("nina_core.voice.manager.boost_wav", _mark_boost)

    started = api_client.post(
        "/voice/record",
        headers=auth_headers,
        json={"title": "Quick dictation", "duration_seconds": 1},
    )
    assert started.status_code == 200, started.json()
    capture_id = started.json()["id"]
    assert capture_id.startswith("vc_")
    assert started.json()["status"] == "recording"
    assert started.json()["sample_rate"] == 16000
    assert started.json()["channels"] == 1
    assert "/voice/" in started.json()["audio_path"]

    active = api_client.get("/voice/active", headers=auth_headers)
    assert active.status_code == 200, active.json()
    assert active.json()["capture"]["id"] == capture_id

    payload = _wait_until_stopped(api_client, auth_headers, capture_id)
    assert payload["status"] == "stopped"
    assert payload["audio_size_bytes"]
    assert post_processing_called == {"denoise": False, "normalize": False, "boost": False}

    active_after_stop = api_client.get("/voice/active", headers=auth_headers)
    assert active_after_stop.status_code == 200, active_after_stop.json()
    assert active_after_stop.json()["capture"] is None

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


def test_voice_transcription_delete_endpoint_respects_limit_and_status(
    api_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm import transcription as tr
    from nina_core.meetings.recorder import NullAudioSource

    monkeypatch.setattr(
        "nina_core.voice.manager.make_audio_source",
        lambda *args, **kwargs: NullAudioSource(),
    )

    call_index = 0

    def _provider(**kwargs: object) -> tr.NullTranscriptionProvider:
        nonlocal call_index
        call_index += 1
        return tr.NullTranscriptionProvider(text=f"transcript {call_index}")

    monkeypatch.setattr(
        "nina_core.voice.service.build_transcription_provider",
        _provider,
    )

    created: list[str] = []
    for idx in range(3):
        started = api_client.post(
            "/voice/record",
            headers=auth_headers,
            json={"title": f"Delete me {idx}", "duration_seconds": 1},
        )
        assert started.status_code == 200, started.json()
        capture_id = started.json()["id"]
        _wait_until_stopped(api_client, auth_headers, capture_id)

        transcribed = api_client.post(
            f"/voice/{capture_id}/transcribe",
            headers=auth_headers,
            json={"save_note": False},
        )
        assert transcribed.status_code == 200, transcribed.json()
        created.append(capture_id)

    list_response = api_client.get("/voice/transcriptions?limit=10", headers=auth_headers)
    assert list_response.status_code == 200
    listed_ids = [item["id"] for item in list_response.json()["transcriptions"]]
    assert all(capture_id in listed_ids for capture_id in created)

    limited = api_client.delete(
        "/voice/transcriptions?limit=1",
        headers=auth_headers,
    )
    assert limited.status_code == 200
    assert limited.json()["deleted"] == 1

    after_limit = api_client.get("/voice/transcriptions?limit=10", headers=auth_headers)
    assert after_limit.status_code == 200
    remaining = [item["id"] for item in after_limit.json()["transcriptions"]]
    assert len(remaining) == len(created) - 1

    status_deleted = api_client.delete(
        "/voice/transcriptions?status=transcribed&limit=1",
        headers=auth_headers,
    )
    assert status_deleted.status_code == 200
    assert status_deleted.json()["deleted"] == 1

    remaining_again = api_client.get("/voice/transcriptions?limit=10", headers=auth_headers)
    assert remaining_again.status_code == 200
    remaining_ids = [item["id"] for item in remaining_again.json()["transcriptions"]]
    assert len(remaining_ids) == len(created) - 2
    assert len(remaining_ids) >= 1

    listed = api_client.get(
        "/voice/transcriptions?status=transcribed&limit=10",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    transcriptions = listed.json()["transcriptions"]
    assert any(
        item["transcript"] is not None and item["transcript"].startswith("transcript")
        for item in transcriptions
    )

    filtered = api_client.get(
        "/voice/transcriptions?status=recording&limit=10",
        headers=auth_headers,
    )
    assert filtered.status_code == 200
    assert all(item["status"] == "recording" for item in filtered.json()["transcriptions"])

    remaining_payload = remaining_again.json()["transcriptions"]
    missing_candidate = next((item for item in remaining_payload if item["transcript_path"]), None)
    assert missing_candidate is not None
    transcript_path = missing_candidate["transcript_path"]
    Path(transcript_path).unlink()
    missing = api_client.get("/voice/transcriptions?limit=10", headers=auth_headers)
    assert missing.status_code == 200
    missing_capture = next(
        item for item in missing.json()["transcriptions"] if item["id"] == missing_candidate["id"]
    )
    assert missing_capture["transcript"] is None
    assert missing_capture["transcript_missing"] is True


def test_voice_transcribe_backend_failure_is_bad_request(
    api_client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.meetings.recorder import NullAudioSource

    monkeypatch.setattr(
        "nina_core.voice.manager.make_audio_source",
        lambda *args, **kwargs: NullAudioSource(),
    )

    def _missing_provider(**kwargs: object) -> object:
        raise RuntimeError("whisper CLI not found on PATH. Install faster-whisper.")

    monkeypatch.setattr(
        "nina_core.voice.service.build_transcription_provider",
        _missing_provider,
    )

    started = api_client.post(
        "/voice/record",
        headers=auth_headers,
        json={"title": "Missing backend", "duration_seconds": 1},
    )
    assert started.status_code == 200, started.json()
    capture_id = started.json()["id"]
    _wait_until_stopped(api_client, auth_headers, capture_id)

    transcribed = api_client.post(
        f"/voice/{capture_id}/transcribe",
        headers=auth_headers,
        json={"save_note": False},
    )
    assert transcribed.status_code == 400, transcribed.json()
    assert "whisper CLI not found" in transcribed.json()["detail"]

    capture = api_client.get(f"/voice/{capture_id}", headers=auth_headers)
    assert capture.status_code == 200, capture.json()
    assert capture.json()["status"] == "failed"
    assert "whisper CLI not found" in capture.json()["error"]


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
