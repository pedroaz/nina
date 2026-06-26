from pathlib import Path

from .paths import (
    get_config_dir,
    get_config_path,
    get_database_path,
    get_log_path,
    get_token_path,
)
from nina_core.db import create_database  # type: ignore[import-untyped]
from nina_core.search.indexer import create_fts_table  # type: ignore[import-untyped]

from .settings import NinaConfig, merge_config
from .token import generate_token, write_token
from nina_core.obsidian.policy import DEFAULT_VAULT_FOLDERS

VAULT_FOLDERS = list(DEFAULT_VAULT_FOLDERS)


def ensure_vault_structure(vault_path: Path) -> None:
    vault_path.mkdir(parents=True, exist_ok=True)
    for folder in VAULT_FOLDERS:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)


def initialize(
    profile: str = "default",
    config_dir: Path | None = None,
    force: bool = False,
    vault_path: Path | str | None = None,
) -> None:
    if config_dir is None:
        config_dir = get_config_dir(profile)

    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "logs").mkdir(parents=True, exist_ok=True)

    config_path = get_config_path(config_dir)
    if config_path.exists() and not force:
        # Even on a no-op re-init, make sure the codex password exists
        # so the daemon can boot a supervised codex child.
        from nina_core.codex.password import (  # type: ignore[import-untyped]
            ensure_password_file,
        )

        config = NinaConfig.load(config_path).with_resolved_paths(config_dir)
        if vault_path is not None and not config.vault_path:
            config = merge_config(config, {"vault_path": str(vault_path)}, config_dir)
            config.save(config_path)
            ensure_vault_structure(Path(config.vault_path))
        ensure_password_file(config_dir, config.codex.password_ref, force=False)
        return

    config = NinaConfig(
        profile=profile,
        vault_path=str(vault_path) if vault_path is not None else "",
    ).with_resolved_paths(config_dir)
    config.save(config_path)

    token_path = get_token_path(config_dir)
    if not token_path.exists() or force:
        token = generate_token()
        write_token(token_path, token)

    if config.vault_path:
        ensure_vault_structure(Path(config.vault_path))

    db_path = get_database_path(config_dir)
    if force and db_path.exists():
        db_path.unlink()
    if not db_path.exists():
        create_database(str(db_path))
        create_fts_table(str(db_path))

    from nina_core.codex.password import (  # type: ignore[import-untyped]
        ensure_password_file,
    )

    ensure_password_file(config_dir, config.codex.password_ref, force=force)

    log_path = get_log_path(config_dir)
    if not log_path.exists():
        log_path.touch()
