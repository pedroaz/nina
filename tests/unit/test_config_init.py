from __future__ import annotations

from nina_core.config import initialize, load_effective_config
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


def test_initialize_does_not_create_implicit_vault(tmp_path) -> None:
    config_dir = tmp_path / "nina-config"

    initialize(config_dir=config_dir, force=True)

    config = load_effective_config(config_dir)
    assert config.vault_path == ""
    assert not (config_dir / "vault").exists()


def test_initialize_existing_profile_with_explicit_vault_repairs_missing_vault(tmp_path) -> None:
    config_dir = tmp_path / "nina-config"
    vault = tmp_path / "nina-vault"
    initialize(config_dir=config_dir, force=True)

    initialize(config_dir=config_dir, vault_path=vault)

    config = load_effective_config(config_dir)
    assert config.vault_path == str(vault)
    assert (vault / "Tasks").exists()


def test_initialize_with_vault_creates_selected_vault(tmp_path) -> None:
    config_dir = tmp_path / "nina-config"
    vault = tmp_path / "pedro-vault"

    initialize(config_dir=config_dir, force=True, vault_path=vault)

    config = load_effective_config(config_dir)
    assert config.vault_path == str(vault)
    assert (vault / "Tasks").exists()
    assert (vault / "System" / "Deleted").exists()
