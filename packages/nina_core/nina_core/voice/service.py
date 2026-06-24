from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.llm.transcription import (
    TranscriptResult,
    build_transcription_provider,
    log_transcription_interaction,
    write_transcript_files,
)
from nina_core.models.models import VoiceCapture  # type: ignore[reportMissingTypeStubs]
from nina_core.obsidian.service import ObsidianService  # type: ignore[reportMissingTypeStubs]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VoiceCaptureService:
    def __init__(
        self,
        db_path: str,
        voice_path: str | Path,
        vault_path: str | Path,
        obsidian: ObsidianService | None = None,
    ) -> None:
        self.db_path = db_path
        self.voice_path = Path(voice_path)
        self.vault_path = Path(vault_path)
        self.obsidian = obsidian or ObsidianService(self.vault_path)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _session(self) -> Session:
        return self.SessionLocal()

    def _serialize(self, capture: VoiceCapture) -> dict[str, Any]:
        return {
            "id": capture.id,
            "title": capture.title,
            "status": capture.status,
            "source": capture.source,
            "device_name": capture.device_name,
            "started_at": capture.started_at,
            "ended_at": capture.ended_at,
            "duration_seconds": capture.duration_seconds,
            "audio_path": capture.audio_path,
            "audio_size_bytes": capture.audio_size_bytes,
            "audio_format": capture.audio_format,
            "sample_rate": capture.sample_rate,
            "channels": capture.channels,
            "transcript_path": capture.transcript_path,
            "transcript_note_path": capture.transcript_note_path,
            "language": capture.language,
            "model": capture.model,
            "error": capture.error,
            "created_at": capture.created_at,
            "updated_at": capture.updated_at,
        }

    def start(
        self,
        title: str,
        source: str = "mic",
        device_name: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_format: str = "wav",
    ) -> dict[str, Any]:
        self.voice_path.mkdir(parents=True, exist_ok=True)
        capture_id = "vc_" + uuid.uuid4().hex[:24]
        audio_path = str(self.voice_path / f"{capture_id}.{audio_format}")
        now = _now()
        db = self._session()
        try:
            capture = VoiceCapture(
                id=capture_id,
                title=title or f"Voice {now[:16]}",
                status="recording",
                source=source,
                device_name=device_name,
                started_at=now,
                audio_path=audio_path,
                audio_format=audio_format,
                sample_rate=sample_rate,
                channels=channels,
                created_at=now,
                updated_at=now,
            )
            db.add(capture)
            db.commit()
            db.refresh(capture)
            return self._serialize(capture)
        finally:
            db.close()

    def stop(
        self,
        capture_id: str,
        duration_seconds: int | None = None,
        size_bytes: int | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        db = self._session()
        try:
            capture = db.query(VoiceCapture).filter(VoiceCapture.id == capture_id).first()
            if capture is None:
                return None
            now = _now()
            if capture.status == "recording":
                capture.status = "stopped" if error is None else "failed"
                capture.ended_at = now
                if duration_seconds is not None:
                    capture.duration_seconds = duration_seconds
                elif capture.started_at:
                    try:
                        start_dt = datetime.fromisoformat(capture.started_at)
                        capture.duration_seconds = max(
                            0, int((datetime.fromisoformat(now) - start_dt).total_seconds())
                        )
                    except ValueError:
                        pass
                if size_bytes is not None:
                    capture.audio_size_bytes = size_bytes
                if error is not None:
                    capture.error = error
                capture.updated_at = now
                db.commit()
                db.refresh(capture)
            elif error is not None and not capture.error:
                capture.error = error
                capture.updated_at = now
                db.commit()
                db.refresh(capture)
            return self._serialize(capture)
        finally:
            db.close()

    def update_status(
        self,
        capture_id: str,
        status: str | None = None,
        transcript_path: str | None = None,
        transcript_note_path: str | None = None,
        language: str | None = None,
        model: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        db = self._session()
        try:
            capture = db.query(VoiceCapture).filter(VoiceCapture.id == capture_id).first()
            if capture is None:
                return None
            if status is not None:
                capture.status = status
            if transcript_path is not None:
                capture.transcript_path = transcript_path
            if transcript_note_path is not None:
                capture.transcript_note_path = transcript_note_path
            if language is not None:
                capture.language = language
            if model is not None:
                capture.model = model
            if error is not None:
                capture.error = error
            capture.updated_at = _now()
            db.commit()
            db.refresh(capture)
            return self._serialize(capture)
        finally:
            db.close()

    def list(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        db = self._session()
        try:
            query = db.query(VoiceCapture)
            if status:
                query = query.filter(VoiceCapture.status == status)
            rows = query.order_by(VoiceCapture.started_at.desc()).limit(max(1, limit)).all()
            return [self._serialize(row) for row in rows]
        finally:
            db.close()

    def list_transcriptions(
        self, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        captures = self.list(status=status, limit=limit)
        for capture in captures:
            transcript_path = capture.get("transcript_path")
            capture["transcript"] = None
            capture["transcript_missing"] = False
            capture["transcript_error"] = None
            if not transcript_path:
                continue
            path = Path(transcript_path)
            try:
                capture["transcript"] = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                capture["transcript_missing"] = True
            except OSError as exc:
                capture["transcript_missing"] = True
                capture["transcript_error"] = str(exc)
        return captures

    def _delete_path(self, path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            return

    def delete_transcriptions(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> int:
        db = self._session()
        try:
            query = db.query(VoiceCapture)
            if status:
                query = query.filter(VoiceCapture.status == status)
            captures = query.order_by(VoiceCapture.started_at.desc()).limit(max(1, limit)).all()

            deleted = 0
            for capture in captures:
                if capture.audio_path:
                    audio_path = Path(capture.audio_path)
                    self._delete_path(audio_path)
                    segments_path = audio_path.with_suffix(".segments.json")
                    self._delete_path(segments_path)

                if capture.transcript_path:
                    self._delete_path(Path(capture.transcript_path))

                if capture.transcript_note_path:
                    note_full = self.vault_path / capture.transcript_note_path
                    if note_full.is_file():
                        deleted_dir = self.vault_path / "System" / "Deleted"
                        deleted_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            os.rename(note_full, deleted_dir / note_full.name)
                        except OSError:
                            pass

                db.delete(capture)
                deleted += 1

            db.commit()
            return deleted
        finally:
            db.close()

    def get(self, capture_id: str) -> dict[str, Any] | None:
        db = self._session()
        try:
            capture = db.query(VoiceCapture).filter(VoiceCapture.id == capture_id).first()
            if capture is None:
                return None
            return self._serialize(capture)
        finally:
            db.close()

    def transcribe(
        self,
        capture_id: str,
        *,
        transcription_config: Any,
        save_note: bool = False,
    ) -> dict[str, Any]:
        capture = self.get(capture_id)
        if capture is None:
            raise RuntimeError(f"Voice capture not found: {capture_id}")
        audio_path = Path(capture["audio_path"])
        if not audio_path.is_file():
            self.update_status(capture_id, status="failed", error=f"Missing audio: {audio_path}")
            raise RuntimeError(f"Audio file missing: {audio_path}")

        self.update_status(capture_id, status="transcribing")
        provider: Any | None = None
        try:
            provider = build_transcription_provider(config=transcription_config)
            result = provider.transcribe(audio_path)
        except Exception as exc:
            failed = TranscriptResult(
                text="",
                segments=[],
                language=None,
                model=getattr(provider, "model", getattr(transcription_config, "model", "unknown")),
            )
            log_transcription_interaction(
                self.db_path,
                provider_name=type(provider).__name__ if provider is not None else "unavailable",
                model=failed.model,
                audio_path=str(audio_path),
                result=failed,
                workflow_run_id=None,
                status="failed",
                error=str(exc),
                purpose="voice_transcription",
            )
            self.update_status(capture_id, status="failed", error=str(exc))
            raise

        transcript_path = audio_path.with_suffix(".txt")
        segments_path = audio_path.with_suffix(".segments.json")
        write_transcript_files(result, transcript_path, segments_path)
        log_transcription_interaction(
            self.db_path,
            provider_name=type(provider).__name__,
            model=result.model,
            audio_path=str(audio_path),
            result=result,
            workflow_run_id=None,
            status="completed",
            purpose="voice_transcription",
        )

        transcript_note_path: str | None = None
        if save_note:
            transcript_note_path = self.obsidian.write_voice_capture_note(
                capture_id=capture_id,
                title=capture["title"],
                started_at=capture["started_at"],
                source=capture.get("source") or "mic",
                audio_path=capture.get("audio_path") or "",
                transcript=result.text,
                language=result.language,
                model=result.model,
            )

        updated = self.update_status(
            capture_id,
            status="transcribed",
            transcript_path=str(transcript_path),
            transcript_note_path=transcript_note_path,
            language=result.language,
            model=result.model,
        )
        return {
            "capture": updated or self.get(capture_id),
            "transcript": result.text,
            "transcript_path": str(transcript_path),
            "segments_path": str(segments_path),
            "transcript_note_path": transcript_note_path,
            "language": result.language,
            "model": result.model,
            "char_count": len(result.text),
        }
