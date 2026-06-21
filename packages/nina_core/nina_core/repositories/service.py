from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from nina_core.models.models import Repository, Task


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_git_root(path: str | Path) -> str:
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise ValueError(f"Repository path does not exist: {candidate}")
    if not candidate.is_dir():
        raise ValueError(f"Repository path is not a directory: {candidate}")
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except FileNotFoundError as exc:
        raise ValueError("git is required to register repositories") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Timed out validating git repository: {candidate}") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "not a git repository").strip()
        raise ValueError(f"Invalid git repository {candidate}: {message}")
    root = result.stdout.strip()
    if not root:
        raise ValueError(f"Invalid git repository {candidate}: missing git root")
    return str(Path(root).expanduser().resolve())


def _default_name(path: str) -> str:
    return Path(path).name or path


@dataclass(frozen=True)
class RepositoryWorktree:
    path: str
    head: str | None = None
    branch: str | None = None
    bare: bool = False
    detached: bool = False
    locked: str | None = None
    prunable: str | None = None


def _clean_branch(value: str | None) -> str | None:
    if not value:
        return None
    prefix = "refs/heads/"
    return value[len(prefix):] if value.startswith(prefix) else value


def _parse_worktree_porcelain(output: str) -> list[RepositoryWorktree]:
    worktrees: list[RepositoryWorktree] = []
    current: dict[str, str | bool] = {}

    def flush() -> None:
        if not current.get("worktree"):
            return
        worktrees.append(
            RepositoryWorktree(
                path=str(current["worktree"]),
                head=str(current["HEAD"]) if current.get("HEAD") else None,
                branch=_clean_branch(str(current["branch"]) if current.get("branch") else None),
                bare=bool(current.get("bare")),
                detached=bool(current.get("detached")),
                locked=str(current["locked"]) if current.get("locked") not in (None, True) else None,
                prunable=str(current["prunable"]) if current.get("prunable") not in (None, True) else None,
            )
        )
        current.clear()

    for line in output.splitlines():
        if not line.strip():
            flush()
            continue
        key, separator, value = line.partition(" ")
        if key == "worktree" and current.get("worktree"):
            flush()
        current[key] = value if separator else True
    flush()
    return worktrees


class RepositoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, path: str | Path, name: str | None = None) -> Repository:
        root = _canonical_git_root(path)
        existing = self.get_by_path(root)
        if existing is not None:
            if name and name.strip() and existing.name != name.strip():
                existing.name = name.strip()
                existing.updated_at = _now()
                self.db.commit()
            return existing
        repo = Repository(
            id=str(uuid.uuid4()),
            name=(name or _default_name(root)).strip() or _default_name(root),
            path=root,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(repo)
        self.db.commit()
        return repo

    def list(self) -> list[Repository]:
        return self.db.query(Repository).order_by(Repository.name.asc(), Repository.path.asc()).all()

    def get(self, repository_id: str | None) -> Repository | None:
        if not repository_id:
            return None
        return self.db.query(Repository).filter(Repository.id == repository_id).first()

    def get_by_path(self, path: str | Path) -> Repository | None:
        root = str(Path(path).expanduser().resolve())
        return self.db.query(Repository).filter(Repository.path == root).first()

    def resolve(self, value: str) -> Repository | None:
        raw = value.strip()
        if not raw:
            return None
        by_id = self.get(raw)
        if by_id is not None:
            return by_id
        by_name = self.db.query(Repository).filter(Repository.name == raw).first()
        if by_name is not None:
            return by_name
        try:
            return self.get_by_path(raw)
        except Exception:
            return None

    def list_worktrees(self, repository_id: str) -> list[RepositoryWorktree]:
        repo = self.get(repository_id)
        if repo is None:
            raise ValueError(f"Repository not found: {repository_id}")
        try:
            result = subprocess.run(
                ["git", "-C", repo.path, "worktree", "list", "--porcelain"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except FileNotFoundError as exc:
            raise ValueError("git is required to list repository worktrees") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"Timed out listing worktrees for repository: {repo.path}") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "git worktree list failed").strip()
            raise ValueError(f"Could not list worktrees for {repo.path}: {message}")
        return _parse_worktree_porcelain(result.stdout)

    def delete(self, repository_id: str) -> bool:
        repo = self.get(repository_id)
        if repo is None:
            return False
        active_task = (
            self.db.query(Task)
            .filter(Task.repository_id == repository_id)
            .filter(Task.task_type.notin_(["deleted", "archived"]))
            .first()
        )
        if active_task is not None:
            raise ValueError("Cannot delete a repository while tasks still reference it")
        self.db.delete(repo)
        self.db.commit()
        return True
