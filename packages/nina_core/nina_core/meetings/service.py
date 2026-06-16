from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import Meeting  # type: ignore[reportMissingTypeStubs]
from nina_core.obsidian.service import ObsidianService  # type: ignore[reportMissingTypeStubs]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "meeting"


def _meeting_path(title: str, started_at: str) -> Path:
    date = started_at[:10]
    return Path("Meetings") / f"{date} - {_slugify(title)}.md"


class MeetingService:
    def __init__(
        self,
        db_path: str,
        recordings_path: str | Path,
        vault_path: str | Path,
        obsidian: ObsidianService | None = None,
    ) -> None:
        self.db_path = db_path
        self.recordings_path = Path(recordings_path)
        self.vault_path = Path(vault_path)
        self.obsidian = obsidian or ObsidianService(self.vault_path)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _session(self) -> Session:
        return self.SessionLocal()

    def _serialize(self, meeting: Meeting) -> dict[str, Any]:
        note_path: str | None = None
        if meeting.started_at and meeting.title:
            note_path = str(_meeting_path(str(meeting.title), str(meeting.started_at)))
        return {
            "id": meeting.id,
            "title": meeting.title,
            "status": meeting.status,
            "source": meeting.source,
            "device_name": meeting.device_name,
            "started_at": meeting.started_at,
            "ended_at": meeting.ended_at,
            "duration_seconds": meeting.duration_seconds,
            "audio_path": meeting.audio_path,
            "audio_size_bytes": meeting.audio_size_bytes,
            "audio_format": meeting.audio_format,
            "sample_rate": meeting.sample_rate,
            "channels": meeting.channels,
            "transcript_path": meeting.transcript_path,
            "summary_path": meeting.summary_path,
            "transcript_note_path": meeting.transcript_note_path,
            "summary_note_path": meeting.summary_note_path,
            "workflow_run_id": meeting.workflow_run_id,
            "error": meeting.error,
            "note_path": note_path,
            "created_at": meeting.created_at,
            "updated_at": meeting.updated_at,
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
        self.recordings_path.mkdir(parents=True, exist_ok=True)
        meeting_id = "mt_" + uuid.uuid4().hex[:24]
        audio_path = str(self.recordings_path / f"{meeting_id}.{audio_format}")
        now = _now()
        db = self._session()
        try:
            meeting = Meeting(
                id=meeting_id,
                title=title or f"Meeting {now[:10]}",
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
            db.add(meeting)
            db.commit()
            db.refresh(meeting)
            return self._serialize(meeting)
        finally:
            db.close()

    def stop(
        self,
        meeting_id: str,
        duration_seconds: int | None = None,
        size_bytes: int | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        db = self._session()
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting is None:
                return None
            now = _now()
            if meeting.status != "stopped":
                meeting.status = "stopped"
                meeting.ended_at = now
                if duration_seconds is not None:
                    meeting.duration_seconds = duration_seconds
                elif meeting.started_at:
                    try:
                        start_dt = datetime.fromisoformat(meeting.started_at)
                        meeting.duration_seconds = max(
                            0, int((datetime.fromisoformat(now) - start_dt).total_seconds())
                        )
                    except ValueError:
                        pass
                if size_bytes is not None:
                    meeting.audio_size_bytes = size_bytes
                if error is not None:
                    meeting.error = error
                meeting.updated_at = now
                db.commit()
                db.refresh(meeting)
            elif error is not None and not meeting.error:
                meeting.error = error
                meeting.updated_at = now
                db.commit()
                db.refresh(meeting)
            payload = self._serialize(meeting)
        finally:
            db.close()

        note_path = self.vault_path / _meeting_path(payload["title"], payload["started_at"])
        if not note_path.exists():
            self.obsidian.create_meeting_note(
                meeting_id=payload["id"],
                title=payload["title"],
                started_at=payload["started_at"],
                ended_at=payload.get("ended_at"),
                duration_seconds=payload.get("duration_seconds"),
                source=payload.get("source") or "mic",
                audio_path=payload.get("audio_path") or "",
                transcript_status="pending",
                summary_status="pending",
                workflow_run_id=payload.get("workflow_run_id"),
            )
        return payload

    def update_status(
        self,
        meeting_id: str,
        status: str | None = None,
        transcript_path: str | None = None,
        summary_path: str | None = None,
        transcript_note_path: str | None = None,
        summary_note_path: str | None = None,
        workflow_run_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        db = self._session()
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting is None:
                return None
            now = _now()
            if status is not None:
                meeting.status = status
            if transcript_path is not None:
                meeting.transcript_path = transcript_path
            if summary_path is not None:
                meeting.summary_path = summary_path
            if transcript_note_path is not None:
                meeting.transcript_note_path = transcript_note_path
            if summary_note_path is not None:
                meeting.summary_note_path = summary_note_path
            if workflow_run_id is not None:
                meeting.workflow_run_id = workflow_run_id
            if error is not None:
                meeting.error = error
            meeting.updated_at = now
            db.commit()
            db.refresh(meeting)
            return self._serialize(meeting)
        finally:
            db.close()

    def list(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        db = self._session()
        try:
            query = db.query(Meeting)
            if status:
                query = query.filter(Meeting.status == status)
            rows = query.order_by(Meeting.started_at.desc()).limit(max(1, limit)).all()
            return [self._serialize(row) for row in rows]
        finally:
            db.close()

    def get(self, meeting_id: str) -> dict[str, Any] | None:
        db = self._session()
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting is None:
                return None
            return self._serialize(meeting)
        finally:
            db.close()

    def most_recent(self, status: str | None = "recording") -> dict[str, Any] | None:
        db = self._session()
        try:
            query = db.query(Meeting)
            if status:
                query = query.filter(Meeting.status == status)
            meeting = query.order_by(Meeting.started_at.desc()).first()
            if meeting is None:
                return None
            return self._serialize(meeting)
        finally:
            db.close()

    def delete(self, meeting_id: str) -> bool:
        meeting = self.get(meeting_id)
        if meeting is None:
            return False
        if meeting.get("started_at") and meeting.get("title"):
            self.obsidian.soft_delete_meeting_note(
                meeting_id=meeting_id,
                title=meeting["title"],
                started_at=meeting["started_at"],
            )
        db = self._session()
        try:
            row = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()
