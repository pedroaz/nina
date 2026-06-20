from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.llm.provider import FakeProvider, LLMService
from nina_core.obsidian.service import ObsidianService
from nina_core.tasks.service import TaskService
from nina_core.workflows.runner import WorkflowRunner


@pytest.fixture
def services(isolated_config: Path, monkeypatch: pytest.MonkeyPatch):
    fake = FakeProvider()
    monkeypatch.setattr(LLMService, "_build_provider", lambda self: fake)
    db_path = str(get_database_path(isolated_config))
    vault_path = get_vault_path(isolated_config)

    def _create_service() -> TaskService:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        session_local = sessionmaker(bind=engine)
        return TaskService(session_local(), ObsidianService(vault_path))

    def _runner() -> WorkflowRunner:
        from nina_core.config import load_effective_config

        return WorkflowRunner(db_path, config=load_effective_config(isolated_config))

    return _create_service, fake, _runner


def _make_task(
    svc_factory, *, title: str, description: str = "", task_type: str = "unclassified"
) -> str:
    service = svc_factory()
    task = service.create(title, description, task_type=task_type)
    task_id = task.id
    return task_id


def test_classify_task_workflow_patches_task(services) -> None:
    svc, fake, runner_factory = services
    fake.queue_text('{"task_type": "coding", "reason": "refactor work"}')

    task_id = _make_task(svc, title="Refactor the auth module", description="split it up")

    result = runner_factory().run("classify-task", {"task_id": task_id})
    assert result["status"] == "completed"
    output = result["output"]
    assert output["task_type"] == "coding"
    assert output["reason"] == "refactor work"

    refreshed = svc().get(task_id)
    assert refreshed is not None
    assert refreshed.task_type == "coding"
    assert refreshed.classified_at is not None
    assert refreshed.classification_reason == "refactor work"
    assert refreshed.classification_model


def test_classify_task_workflow_falls_back_to_human(services) -> None:
    svc, fake, runner_factory = services
    fake.queue_text("I do not know what to do with this ticket.")

    task_id = _make_task(svc, title="???", description="no signal here")
    result = runner_factory().run("classify-task", {"task_id": task_id})
    assert result["status"] == "completed"
    assert result["output"]["task_type"] == "human"

    refreshed = svc().get(task_id)
    assert refreshed is not None
    assert refreshed.task_type == "human"


def test_run_task_refuses_human(services) -> None:
    svc, _, runner_factory = services
    task_id = _make_task(svc, title="Call mom", task_type="human")
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["status"] == "completed"
    output = result["output"]
    assert output["status"] == "skipped"
    assert "human" in output["reason"]
    assert output["would_route_to"] is None


def test_run_task_refuses_reminder_and_blocked(services) -> None:
    svc, _, runner_factory = services
    for task_type in ("reminder", "blocked"):
        task_id = _make_task(svc, title=f"x {task_type}", task_type=task_type)
        result = runner_factory().run("run-task", {"task_id": task_id})
        assert result["output"]["status"] == "skipped", task_type
        assert result["output"]["would_route_to"] is None


def test_run_task_routes_coding_to_agent_placeholder(services) -> None:
    svc, _, runner_factory = services
    task_id = _make_task(svc, title="Refactor auth", task_type="coding")
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["status"] == "completed"
    output = result["output"]
    assert output["status"] == "completed"
    assert output["would_route_to"] == "agent"

    refreshed = svc().get(task_id)
    assert refreshed is not None
    assert refreshed.status == "idle"


def test_run_task_routes_research_to_research_placeholder(services) -> None:
    svc, _, runner_factory = services
    task_id = _make_task(svc, title="Investigate X", task_type="research")
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["output"]["would_route_to"] == "research-topic"


def test_run_task_is_noop_for_done(services) -> None:
    svc, _, runner_factory = services
    task_id = _make_task(svc, title="Ship it", task_type="done")
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["output"]["status"] == "noop"
    assert result["output"]["would_route_to"] is None
