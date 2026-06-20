from pathlib import Path

from .paths import (
    get_config_dir,
    get_config_path,
    get_database_path,
    get_log_path,
    get_token_path,
    get_vault_path,
)
from nina_core.db import create_database  # type: ignore[import-untyped]
from nina_core.search.indexer import create_fts_table  # type: ignore[import-untyped]

from .settings import NinaConfig
from .token import generate_token, write_token

VAULT_FOLDERS = [
    "Tasks",
    "Daily",
    "Meetings",
    "Templates",
    "System",
    "System/Deleted",
    "System/Indexes",
    "System/Logs",
    "Research",
    "Research/Sources",
]


def ensure_vault_structure(vault_path: Path) -> None:
    vault_path.mkdir(parents=True, exist_ok=True)
    for folder in VAULT_FOLDERS:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)


def initialize(
    profile: str = "default",
    config_dir: Path | None = None,
    force: bool = False,
) -> None:
    if config_dir is None:
        config_dir = get_config_dir(profile)

    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "logs").mkdir(parents=True, exist_ok=True)

    config_path = get_config_path(config_dir)
    if config_path.exists() and not force:
        # Even on a no-op re-init, make sure the opencode password exists
        # so the daemon can boot a supervised opencode child.
        from nina_core.opencode.password import (  # type: ignore[import-untyped]
            ensure_password_file,
        )

        config = NinaConfig.load(config_path)
        ensure_password_file(config_dir, config.opencode.password_ref, force=False)
        return

    config = NinaConfig(profile=profile).with_resolved_paths(config_dir)
    config.save(config_path)

    token_path = get_token_path(config_dir)
    if not token_path.exists() or force:
        token = generate_token()
        write_token(token_path, token)

    ensure_vault_structure(Path(get_vault_path(config_dir)))

    db_path = get_database_path(config_dir)
    if force and db_path.exists():
        db_path.unlink()
    if not db_path.exists():
        create_database(str(db_path))
        create_fts_table(str(db_path))

    from nina_core.opencode.password import (  # type: ignore[import-untyped]
        ensure_password_file,
    )

    ensure_password_file(config_dir, config.opencode.password_ref, force=force)

    log_path = get_log_path(config_dir)
    if not log_path.exists():
        log_path.touch()
