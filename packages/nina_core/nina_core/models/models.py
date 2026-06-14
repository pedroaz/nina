from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from nina_core.db.engine import Base  # type: ignore[import-untyped]


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class Project(Base):
    __tablename__ = "projects"
    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    status = Column(Text, nullable=False, default="active")
    note_path = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Text, primary_key=True)
    project_id = Column(Text, ForeignKey("projects.id"))
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    status = Column(Text, nullable=False, default="todo")
    kanban_column = Column(Text, nullable=False, default="Todo")
    kanban_position = Column(Integer, nullable=False, default=0)
    note_path = Column(Text)
    created_at = Column(Text, nullable=False, default=now_utc)
    updated_at = Column(Text, nullable=False, default=now_utc)
    project = relationship("Project")


class KanbanColumn(Base):
    __tablename__ = "kanban_columns"
    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    position = Column(Integer, nullable=False)
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


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(Text, primary_key=True)
    session_id = Column(Text, ForeignKey("conversation_sessions.id"), nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(Text, nullable=False, default=now_utc)
