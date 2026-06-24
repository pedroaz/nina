from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.llm.provider import FakeProvider, LLMService
from nina_core.obsidian.service import ObsidianService
from nina_core.repositories.service import RepositoryService
from nina_core.tasks.service import TaskService
from nina_core.workflows.runner import WorkflowRunner


@pytest.fixture
def services(isolated_config: Path, monkeypatch: pytest.MonkeyPatch):
    fake = FakeProvider()
    monkeypatch.setattr(LLMService, "_build_provider", lambda self: fake)
    db_path = str(get_database_path(isolated_config))
    vault_path = get_vault_path(isolated_config)
    repo_path = isolated_config / "workflow-repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", str(repo_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def _create_service() -> TaskService:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        session_local = sessionmaker(bind=engine)
        return TaskService(session_local(), ObsidianService(vault_path), background_classify=False)

    repo_service = _create_service()
    try:
        repository_id = RepositoryService(repo_service.db).create(repo_path).id
    finally:
        repo_service.db.close()

    def _runner() -> WorkflowRunner:
        from nina_core.config import load_effective_config

        return WorkflowRunner(db_path, config=load_effective_config(isolated_config))

    return _create_service, fake, _runner, repository_id


def _make_task(
    svc_factory,
    *,
    title: str,
    description: str = "",
    task_type: str = "unclassified",
    repository_id: str | None = None,
    pipeline_stage: str | None = None,
) -> str:
    service = svc_factory()
    try:
        task = service.create(title, description, task_type=task_type, repository_id=repository_id, pipeline_stage=pipeline_stage)
        return task.id
    finally:
        service.db.close()


def test_classify_task_workflow_patches_task(services) -> None:
    svc, fake, runner_factory, repo_id = services
    fake.queue_text('{"task_type": "coding", "reason": "refactor work"}')

    task_id = _make_task(
        svc,
        title="Refactor the auth module",
        description="split it up",
        repository_id=repo_id,
    )

    result = runner_factory().run("classify-task", {"task_id": task_id})
    assert result["status"] == "completed"
    output = result["output"]
    assert output["task_type"] == "coding"
    assert output["reason"] == "refactor work"

    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "coding"
        assert refreshed.status == "idle"
        assert refreshed.classified_at is not None
        assert refreshed.classification_reason == "refactor work"
        assert refreshed.classification_model
    finally:
        service.db.close()


def test_classify_task_blocks_coding_without_repository(services) -> None:
    svc, fake, runner_factory, _repo_id = services
    fake.queue_text('{"task_type": "coding", "reason": "code change"}')
    task_id = _make_task(svc, title="Fix the API", task_type="unclassified")

    result = runner_factory().run("classify-task", {"task_id": task_id})

    assert result["status"] == "completed"
    assert result["output"]["task_type"] == "coding"
    assert result["output"]["applied_task_type"] == "unclassified"
    assert result["output"]["requires_repository"] is True
    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "unclassified"
        assert refreshed.status == "error"
    finally:
        service.db.close()


def test_classify_task_workflow_falls_back_to_reminder(services) -> None:
    svc, fake, runner_factory, _repo_id = services
    fake.queue_text("I do not know what to do with this ticket.")

    task_id = _make_task(svc, title="???", description="no signal here", repository_id=_repo_id)
    result = runner_factory().run("classify-task", {"task_id": task_id})
    assert result["status"] == "completed"
    assert result["output"]["task_type"] == "reminder"

    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "reminder"
    finally:
        service.db.close()


def test_run_task_refuses_reminder_and_blocked(services) -> None:
    svc, _, runner_factory, _repo_id = services
    for task_type in ("reminder", "blocked"):
        task_id = _make_task(svc, title=f"x {task_type}", task_type=task_type)
        result = runner_factory().run("run-task", {"task_id": task_id})
        assert result["output"]["status"] == "skipped", task_type
        assert result["output"]["would_route_to"] is None


def test_run_task_routes_coding_through_codex_task(services, monkeypatch) -> None:
    from nina_core.codex.client import CodexClient, CodexExecResult

    captured_log_paths: list[Path] = []

    async def fake_exec_task(
        self,
        prompt,
        *,
        cwd,
        env,
        json_mode=True,
        log_path=None,
        **_kwargs,
    ):
        assert env["NINA_TASK_TYPE"] == "coding"
        assert "Nina task type: coding" in prompt
        assert log_path is not None
        captured_log_paths.append(Path(log_path))
        return CodexExecResult(
            exit_code=0, stdout="{}\n", stderr="", last_message="Outcome: completed\n"
        )

    monkeypatch.setattr(CodexClient, "exec_task", fake_exec_task)
    svc, _, runner_factory, repo_id = services
    task_id = _make_task(svc, title="Refactor auth", task_type="coding", repository_id=repo_id)
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["status"] == "completed"
    output = result["output"]
    assert output["status"] == "completed"
    assert output["task_type"] == "coding"
    assert output["would_route_to"] == "codex:coding"
    assert output["task_status"] == "working"
    assert output["log_path"] == str(captured_log_paths[0])
    assert captured_log_paths[0].suffix == ".log"

    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "coding"
        assert refreshed.status == "working"
    finally:
        service.db.close()


@pytest.mark.parametrize(
    ("pipeline_stage", "expected_snippet", "task_type"),
    [
        ("created", "Do discovery first", "coding"),
        ("exploration", "Explore the ticket end-to-end", "coding"),
        ("coding", "Implement the requested change", "coding"),
        ("testing", "Validate the change", "coding"),
        ("reviewing", "Review the changes as an independent reviewer", "reviewing"),
    ],
)
def test_run_task_uses_pipeline_stage_in_prompt_and_env(services, monkeypatch, pipeline_stage: str, expected_snippet: str, task_type: str) -> None:
    from nina_core.codex.client import CodexClient, CodexExecResult

    async def fake_exec_task(self, prompt, *, cwd, env, json_mode=True, log_path=None, **_kwargs):
        assert env["NINA_TASK_TYPE"] == task_type
        assert env["NINA_PIPELINE_STAGE"] == pipeline_stage
        assert f"Nina pipeline stage: {pipeline_stage}" in prompt
        assert expected_snippet in prompt
        return CodexExecResult(
            exit_code=0,
            stdout="{}\n",
            stderr="",
            last_message="Outcome: completed\n" + ("Decision: approved\n" if task_type == "reviewing" else ""),
        )

    monkeypatch.setattr(CodexClient, "exec_task", fake_exec_task)
    svc, _, runner_factory, repo_id = services
    task_id = _make_task(
        svc,
        title=f"Pipeline {pipeline_stage} task",
        task_type=task_type,
        repository_id=repo_id,
        pipeline_stage=pipeline_stage,
    )
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["status"] == "completed"
    output = result["output"]
    assert output["status"] == "completed"
    assert output["task_type"] == task_type
    assert output["would_route_to"] == f"codex:{task_type}"

def test_run_task_routes_reviewing_through_codex_task(services, monkeypatch) -> None:
    from nina_core.codex.client import CodexClient, CodexExecResult

    async def fake_exec_task(self, prompt, *, cwd, env, json_mode=True, log_path=None, **_kwargs):
        assert log_path is not None
        assert env["NINA_TASK_TYPE"] == "reviewing"
        assert "Decision: approved, rejected, or blocked" in prompt
        return CodexExecResult(
            exit_code=0,
            stdout="{}\n",
            stderr="",
            last_message="Outcome: completed\nDecision: approved\n",
        )

    monkeypatch.setattr(CodexClient, "exec_task", fake_exec_task)
    svc, _, runner_factory, repo_id = services
    task_id = _make_task(svc, title="Review auth", task_type="reviewing", repository_id=repo_id)
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["status"] == "completed"
    assert result["output"]["would_route_to"] == "codex:reviewing"


def test_run_task_classifies_unclassified_then_runs_coding(services, monkeypatch) -> None:
    from nina_core.codex.client import CodexClient, CodexExecResult

    async def fake_exec_task(self, prompt, *, cwd, env, json_mode=True, log_path=None, **_kwargs):
        assert log_path is not None
        assert env["NINA_TASK_TYPE"] == "coding"
        return CodexExecResult(
            exit_code=0, stdout="{}\n", stderr="", last_message="Outcome: completed\n"
        )

    monkeypatch.setattr(CodexClient, "exec_task", fake_exec_task)
    svc, fake, runner_factory, repo_id = services
    fake.queue_text('{"task_type": "coding", "reason": "code change"}')
    task_id = _make_task(svc, title="Fix the API", task_type="unclassified", repository_id=repo_id)

    result = runner_factory().run("run-task", {"task_id": task_id})

    assert result["status"] == "completed"
    output = result["output"]
    assert output["task_type"] == "coding"
    assert output["would_route_to"] == "codex:coding"
    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "coding"
        assert refreshed.status == "working"
    finally:
        service.db.close()


def test_run_task_preserves_repository_required_classification(services) -> None:
    svc, fake, runner_factory, _repo_id = services
    fake.queue_text('{"task_type": "coding", "reason": "code change"}')
    task_id = _make_task(svc, title="Fix the API", task_type="unclassified")

    result = runner_factory().run("run-task", {"task_id": task_id})

    assert result["status"] == "completed"
    output = result["output"]
    assert output["status"] == "error"
    assert output["task_type"] == "coding"
    assert output["applied_task_type"] == "unclassified"
    assert output["requires_repository"] is True
    assert output["would_route_to"] is None
    assert "no repository is attached" in output["reason"]
    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "unclassified"
        assert refreshed.status == "error"
    finally:
        service.db.close()


def test_run_task_routes_research_to_research_workflow(services, monkeypatch) -> None:
    from nina_core.research.service import FakeResearchProvider, ResearchService

    monkeypatch.setattr(ResearchService, "_build_provider", lambda self: FakeResearchProvider())
    svc, _, runner_factory, _repo_id = services
    task_id = _make_task(
        svc,
        title="Investigate X",
        description="Prefer official docs",
        task_type="research",
    )
    result = runner_factory().run("run-task", {"task_id": task_id, "search_mode": "cached"})

    assert result["status"] == "completed"
    output = result["output"]
    assert output["would_route_to"] == "research"
    assert output["status"] == "completed"
    assert output["note_path"].startswith("Research/")
    assert output["search_mode"] == "cached"

    service = svc()
    try:
        refreshed = service.get(task_id)
        assert refreshed is not None
        assert refreshed.task_type == "research"
        assert refreshed.status == "idle"
    finally:
        service.db.close()


def test_run_task_is_noop_for_done(services) -> None:
    svc, _, runner_factory, _repo_id = services
    task_id = _make_task(svc, title="Ship it", task_type="done")
    result = runner_factory().run("run-task", {"task_id": task_id})
    assert result["output"]["status"] == "noop"
    assert result["output"]["would_route_to"] is None
