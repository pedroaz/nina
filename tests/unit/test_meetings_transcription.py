from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.llm.transcription import (
    FasterWhisperProvider,
    NullTranscriptionProvider,
    WhisperCliProvider,
    build_transcription_provider,
    log_transcription_interaction,
    write_transcript_files,
)

pytestmark = pytest.mark.unit


def test_null_provider_returns_constant_text() -> None:
    provider = NullTranscriptionProvider(text="hello world")
    result = provider.transcribe(Path("/tmp/does-not-matter.wav"))
    assert result.text == "hello world"
    assert result.model == "null"


def test_build_transcription_provider_returns_null_when_backend_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.config.settings import TranscriptionConfig

    monkeypatch.delenv("NINA_TRANSCRIPTION_BACKEND", raising=False)
    provider = build_transcription_provider(TranscriptionConfig(backend="null"))
    assert isinstance(provider, NullTranscriptionProvider)


def test_faster_whisper_provider_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "faster_whisper" or name.startswith("faster_whisper."):
            raise ImportError("not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    provider = FasterWhisperProvider()
    with pytest.raises(RuntimeError):
        provider.transcribe(Path("/tmp/missing.wav"))


def test_whisper_cli_provider_raises_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    provider = WhisperCliProvider()
    with pytest.raises(RuntimeError):
        provider.transcribe(tmp_path / "x.wav")


def test_write_transcript_files_writes_text_and_segments(tmp_path: Path) -> None:
    from nina_core.llm.transcription import TranscriptResult, TranscriptSegment

    result = TranscriptResult(
        text="hi there",
        segments=[TranscriptSegment(start=0.0, end=0.5, text="hi")],
        language="en",
        model="null",
    )
    text_path = tmp_path / "out.txt"
    seg_path = tmp_path / "out.segments.json"
    write_transcript_files(result, text_path, seg_path)
    assert text_path.read_text().strip() == "hi there"
    assert "segments" in seg_path.read_text()


def test_log_transcription_interaction_writes_row(tmp_path: Path) -> None:
    from nina_core.db import create_database
    from nina_core.llm.transcription import TranscriptResult

    db_path = tmp_path / "interactions.db"

    create_database(str(db_path))
    result = TranscriptResult(text="hi", segments=[], language="en", model="null")
    log_transcription_interaction(
        str(db_path),
        provider_name="NullTranscriptionProvider",
        model="null",
        audio_path="/tmp/x.wav",
        result=result,
        workflow_run_id="wf_demo",
    )
    from nina_core.models.models import LLMInteraction
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    session = sessionmaker(bind=engine)
    with session() as db:
        rows = db.query(LLMInteraction).all()
        assert len(rows) == 1
        assert rows[0].purpose == "meeting_transcription"
        assert rows[0].workflow_run_id == "wf_demo"


def test_hf_unauth_warning_is_suppressed_when_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`huggingface_hub` emits a `UserWarning` when downloading public models
    without `HF_TOKEN`. Nina should suppress it for the default (unauthenticated)
    case but pass it through when the user has explicitly set a token."""
    import warnings

    from nina_core.llm.transcription import _suppress_hf_unauth_warning

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with _suppress_hf_unauth_warning():
            warnings.warn(
                "You are sending unauthenticated requests to the HF Hub.",
                UserWarning,
                stacklevel=2,
            )
    assert all("unauthenticated requests" not in str(w.message) for w in caught) or len(caught) == 0


def test_hf_unauth_warning_passes_through_when_token_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the user has set `HF_TOKEN`, we don't suppress anything — the
    library will use the token and the warning should not fire anyway."""
    import warnings

    from nina_core.llm.transcription import _suppress_hf_unauth_warning

    monkeypatch.setenv("HF_TOKEN", "hf_testtoken")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with _suppress_hf_unauth_warning():
            warnings.warn(
                "You are sending unauthenticated requests to the HF Hub.",
                UserWarning,
                stacklevel=2,
            )
    assert any("unauthenticated requests" in str(w.message) for w in caught)
