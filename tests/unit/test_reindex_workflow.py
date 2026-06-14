from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.workflows.runner import WorkflowRunner


def test_reindex_vault_workflow_runs(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NINA_EMBEDDING_PROVIDER", "fake")
    vault = get_vault_path(isolated_config)
    note_dir = vault / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "x.md").write_text(
        "---\ntitle: X\nnina_type: note\n---\n\nhello world"
    )
    runner = WorkflowRunner(str(get_database_path(isolated_config)))
    result = runner.run("reindex-vault", {})
    assert result["status"] == "completed"
    assert "embedded" in result["output"]
