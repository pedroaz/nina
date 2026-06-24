from __future__ import annotations

from nina_core.config.init import VAULT_FOLDERS, ensure_vault_structure


def test_ensure_vault_structure_creates_only_active_folders(tmp_path) -> None:  # type: ignore[no-untyped-def]
    vault = tmp_path / "vault"

    ensure_vault_structure(vault)

    expected = {
        "Tasks",
        "Research",
        "Meetings",
        "Voice",
        "System",
        "System/Deleted",
        "System/Archived",
    }
    actual = {str(path.relative_to(vault)) for path in vault.rglob("*") if path.is_dir()}
    assert actual == expected
    assert set(VAULT_FOLDERS) == {
        "Tasks",
        "Research",
        "Meetings",
        "Voice",
        "System/Deleted",
        "System/Archived",
    }
