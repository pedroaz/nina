from sqlalchemy import Column, ForeignKey, Integer, Text

from nina_core.db.engine import Base  # type: ignore[import-untyped]


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


TASK_TYPES = (
    "unclassified",
    "reminder",
    "research",
    "coding",
    "reviewing",
    "blocked",
    "done",
    "human",
)
TASK_AGENT_STATUSES = ("idle", "working", "error")


class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    path = Column(Text, nullable=False, unique=True)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Text, primary_key=True)
    repository_id = Column(Text, ForeignKey("repositories.id"))
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    task_type = Column(Text, nullable=False, default="unclassified")
    status = Column(Text, nullable=False, default="idle")
    classified_at = Column(Text)
    classification_reason = Column(Text)
    classification_model = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)


class Note(Base):
    __tablename__ = "notes"
    id = Column(Text, primary_key=True)
    nina_type = Column(Text, nullable=False)
    entity_id = Column(Text)
    path = Column(Text, nullable=False, unique=True)
    title = Column(Text, nullable=False)
    content_hash = Column(Text, nullable=False)
    last_indexed_at = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)


class LLMInteraction(Base):
    __tablename__ = "llm_interactions"
    id = Column(Text, primary_key=True)
    provider = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    purpose = Column(Text, nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text)
    status = Column(Text, nullable=False)
    error = Column(Text)
    workflow_run_id = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    completed_at = Column(Text)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id = Column(Text, primary_key=True)
    workflow_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    input_json = Column(Text, nullable=False, default="{}")
    output_json = Column(Text)
    error = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)
    completed_at = Column(Text)


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id = Column(Text, primary_key=True)
    workflow_run_id = Column(Text, ForeignKey("workflow_runs.id"), nullable=False)
    step_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    output_json = Column(Text)
    error = Column(Text)
    attempt_count = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)
    completed_at = Column(Text)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    workflow_name = Column(Text, nullable=False)
    schedule_kind = Column(Text, nullable=False, default="cron")
    schedule_value = Column(Text, nullable=False)
    enabled = Column(Integer, nullable=False, default=1)
    last_run_at = Column(Text)
    next_run_at = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)


class JobRun(Base):
    __tablename__ = "job_runs"
    id = Column(Text, primary_key=True)
    job_name = Column(Text, nullable=False)
    scheduled_job_id = Column(Text, ForeignKey("scheduled_jobs.id"))
    workflow_run_id = Column(Text, ForeignKey("workflow_runs.id"))
    status = Column(Text, nullable=False)
    scheduled_at = Column(Text)
    started_at = Column(Text)
    completed_at = Column(Text)
    error = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)


class Event(Base):
    __tablename__ = "events"
    id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(Text, nullable=False, default=now_utc)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    id = Column(Text, primary_key=True)
    mode = Column(Text, nullable=False)
    title = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)
    completed_at = Column(Text)
    cancel_requested = Column(Integer, nullable=False, default=0)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(Text, primary_key=True)
    session_id = Column(Text, ForeignKey("conversation_sessions.id"), nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(Text, nullable=False, default=now_utc)


class NoteEmbedding(Base):
    __tablename__ = "note_embeddings"
    id = Column(Text, primary_key=True)
    note_id = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    nina_type = Column(Text, nullable=False, default="note")
    model = Column(Text, nullable=False)
    dim = Column(Integer, nullable=False)
    embedding_blob = Column(Text, nullable=False)
    content_hash = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)


class IntegrationTest(Base):
    __tablename__ = "integration_tests"
    id = Column(Text, primary_key=True)
    integration_name = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    identity_json = Column(Text)
    error = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc, index=True)


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="recording")
    source = Column(Text, nullable=False, default="mic")
    device_name = Column(Text)
    started_at = Column(Text, nullable=False)
    ended_at = Column(Text)
    duration_seconds = Column(Integer)
    audio_path = Column(Text, nullable=False)
    audio_size_bytes = Column(Integer)
    audio_format = Column(Text, nullable=False, default="wav")
    sample_rate = Column(Integer, nullable=False, default=16000)
    channels = Column(Integer, nullable=False, default=1)
    transcript_path = Column(Text)
    summary_path = Column(Text)
    # Vault-relative paths to the human-facing Markdown files written by the
    # transcribe and summarize workflows. Distinct from `transcript_path`
    # (raw .txt next to the audio) and `summary_path` (legacy: the same hub
    # note path; kept for backwards compatibility with old code paths).
    transcript_note_path = Column(Text)
    summary_note_path = Column(Text)
    workflow_run_id = Column(Text)
    error = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)
