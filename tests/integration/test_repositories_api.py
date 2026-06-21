from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def test_repository_api_registers_lists_and_blocks_delete_when_used(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    repo_path = _init_git_repo(isolated_config / "api-repo")

    created = api_client.post(
        "/repositories",
        headers=auth_headers,
        json={"path": str(repo_path), "name": "api-repo"},
    )

    assert created.status_code == 200
    repo = created.json()
    assert repo["name"] == "api-repo"
    assert repo["path"] == str(repo_path)

    listed = api_client.get("/repositories", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == repo["id"] for item in listed.json())

    task = api_client.post(
        "/tasks",
        headers=auth_headers,
        json={
            "title": "Use repo",
            "task_type": "coding",
            "repository_id": repo["id"],
            "auto_classify": False,
        },
    )
    assert task.status_code == 200
    assert task.json()["repository_id"] == repo["id"]
    assert task.json()["repository_path"] == str(repo_path)

    blocked = api_client.delete(f"/repositories/{repo['id']}", headers=auth_headers)
    assert blocked.status_code == 400


def test_repository_api_rejects_non_git_path(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    not_repo = isolated_config / "not-a-repo"
    not_repo.mkdir()

    response = api_client.post(
        "/repositories",
        headers=auth_headers,
        json={"path": str(not_repo)},
    )

    assert response.status_code == 400
    assert "Invalid git repository" in response.json()["detail"]


def test_repository_api_lists_git_worktrees(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    repo_path = _init_git_repo(isolated_config / "worktree-repo")

    created = api_client.post(
        "/repositories",
        headers=auth_headers,
        json={"path": str(repo_path), "name": "worktree-repo"},
    )
    assert created.status_code == 200
    repo = created.json()

    response = api_client.get(f"/repositories/{repo['id']}/worktrees", headers=auth_headers)

    assert response.status_code == 200
    worktrees = response.json()
    assert any(item["path"] == repo["path"] for item in worktrees)
    assert all("detached" in item for item in worktrees)

