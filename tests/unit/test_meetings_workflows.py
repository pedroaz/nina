from __future__ import annotations

import wave
from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_recordings_path
from nina_core.meetings.service import MeetingService
from nina_core.workflows.runner import WorkflowRunner

pytestmark = pytest.mark.unit


def _create_silence_wav(path: Path, seconds: float = 0.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frame = b"\x00\x00"
        for _ in range(int(sample_rate * seconds)):
            writer.writeframes(frame)


def _patch_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    from nina_core.llm import transcription as tr

    monkeypatch.setattr(
        tr,
        "build_transcription_provider",
        lambda **kwargs: tr.NullTranscriptionProvider(text="hello transcript"),
    )


def test_transcribe_meeting_workflow_writes_note_and_logs(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"

    service = MeetingService(str(db_path), recordings, vault)
    started = service.start(title="Sprint review")
    meeting_id = started["id"]
    audio_path = Path(started["audio_path"])
    _create_silence_wav(audio_path)
    service.stop(meeting_id, duration_seconds=30, size_bytes=audio_path.stat().st_size)

    _patch_transcription(monkeypatch)

    runner = WorkflowRunner(str(db_path))
    result = runner.run("transcribe-meeting", {"meeting_id": meeting_id, "input": {}})

    assert result["status"] == "completed", result
    output = result["output"]

    hub_path = vault / output["note_path"]
    transcript_note_path = vault / output["transcript_note_path"]
    raw_text_path = Path(output["transcript_path"])

    assert hub_path.is_file()
    assert transcript_note_path.is_file()
    assert raw_text_path.is_file()
    assert raw_text_path.read_text().strip() == "hello transcript"

    # The transcript text lives in the dedicated transcript file, not the hub.
    assert "hello transcript" in transcript_note_path.read_text()
    hub_text = hub_path.read_text()
    assert "hello transcript" not in hub_text
    # Hub links to the transcript file via a wikilink.
    assert "[[" in hub_text and "Transcript]]" in hub_text

    meeting = service.get(meeting_id)
    assert meeting["status"] == "transcribed"
    assert meeting["transcript_path"]
    assert meeting["transcript_note_path"] == output["transcript_note_path"]

    from nina_core.models.models import LLMInteraction
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    session = sessionmaker(bind=engine)
    with session() as db:
        rows = (
            db.query(LLMInteraction).filter(LLMInteraction.purpose == "meeting_transcription").all()
        )
        assert len(rows) == 1
        assert rows[0].status == "completed"


def test_summarize_meeting_workflow_writes_summary_note_and_links_hub(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"

    service = MeetingService(str(db_path), recordings, vault)
    started = service.start(title="Roadmap")
    meeting_id = started["id"]
    audio_path = Path(started["audio_path"])
    _create_silence_wav(audio_path)
    service.stop(meeting_id, duration_seconds=120, size_bytes=audio_path.stat().st_size)
    transcript_path = audio_path.with_suffix(".txt")
    transcript_path.write_text("We decided to ship the new dashboard next quarter.")

    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    from nina_core.llm.provider import FakeProvider, LLMService

    fake = FakeProvider()
    fake.queue_text(
        "## Summary\n"
        "- We agreed on the dashboard plan.\n"
        "## Action items\n"
        "- Owner Alex to draft the design.\n"
        "## Decisions\n"
        "- Ship dashboard next quarter.\n"
    )

    def _patched_init(
        self: LLMService,
        db_path: str,
        provider=None,
        config=None,  # noqa: ARG001
        codex_binary_path=None,  # noqa: ARG001
    ) -> None:  # type: ignore[no-untyped-def]
        self.db_path = db_path
        self.config = config or __import__(
            "nina_core.config.settings", fromlist=["LLMConfig"]
        ).LLMConfig(provider="fake", model="fake")
        self.provider = fake

    monkeypatch.setattr(LLMService, "__init__", _patched_init)

    runner = WorkflowRunner(str(db_path))
    result = runner.run("summarize-meeting", {"meeting_id": meeting_id, "input": {}})

    assert result["status"] == "completed", result
    output = result["output"]
    hub_path = vault / output["note_path"]
    summary_note_path = vault / output["summary_note_path"]
    assert hub_path.is_file()
    assert summary_note_path.is_file()

    summary_text = summary_note_path.read_text()
    assert "## Summary" in summary_text
    assert "## Action items" in summary_text
    assert "## Decisions" in summary_text
    assert "[[" in summary_text and "Hub" in summary_text and "]]" in summary_text

    meeting = service.get(meeting_id)
    assert meeting["status"] == "summarized"
    assert meeting["summary_note_path"] == output["summary_note_path"]


def test_meeting_pipeline_writes_all_three_files(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: pipeline creates hub + transcript + summary, all linked."""
    db_path = get_database_path(isolated_config)
    recordings = get_recordings_path(isolated_config)
    vault = isolated_config / "vault"

    service = MeetingService(str(db_path), recordings, vault)
    started = service.start(title="Pipeline check")
    meeting_id = started["id"]
    audio_path = Path(started["audio_path"])
    _create_silence_wav(audio_path)
    service.stop(meeting_id, duration_seconds=10, size_bytes=audio_path.stat().st_size)

    _patch_transcription(monkeypatch)

    from nina_core.llm.provider import FakeProvider, LLMService

    fake = FakeProvider()
    fake.queue_text(
        "## Summary\n- Pipeline summary.\n"
        "## Action items\n- [ ] Follow up.\n"
        "## Decisions\n- Use the pipeline.\n"
    )

    def _patched_init(
        self: LLMService,
        db_path: str,
        provider=None,
        config=None,  # noqa: ARG001
        codex_binary_path=None,  # noqa: ARG001
    ) -> None:  # type: ignore[no-untyped-def]
        self.db_path = db_path
        self.config = config or __import__(
            "nina_core.config.settings", fromlist=["LLMConfig"]
        ).LLMConfig(provider="fake", model="fake")
        self.provider = fake

    monkeypatch.setattr(LLMService, "__init__", _patched_init)

    runner = WorkflowRunner(str(db_path))
    result = runner.run("meeting-pipeline", {"meeting_id": meeting_id, "input": {}})

    assert result["status"] == "completed", result
    output = result["output"]

    hub_path = vault / output["note_path"]
    transcript_path = vault / output["transcript_note_path"]
    summary_path = vault / output["summary_note_path"]

    assert hub_path.is_file()
    assert transcript_path.is_file()
    assert summary_path.is_file()

    hub_text = hub_path.read_text()
    assert "Transcript]]" in hub_text
    assert "Summary]]" in hub_text

    transcript_text = transcript_path.read_text()
    assert "hello transcript" in transcript_text
    assert "Hub" in transcript_text and "[[" in transcript_text

    summary_text = summary_path.read_text()
    assert "## Summary" in summary_text
    assert "Hub" in summary_text
    assert "Transcript" in summary_text

    meeting = service.get(meeting_id)
    assert meeting["status"] == "summarized"
    assert meeting["transcript_note_path"]
    assert meeting["summary_note_path"]
