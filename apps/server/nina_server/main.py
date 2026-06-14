import json
import os
import sys
from pathlib import Path

import uvicorn
from nina_core.config import (
    ensure_vault_structure,
    get_config_dir,
    get_config_path,
    get_runtime_path,
    get_token_path,
    load_effective_config,
    read_token,
)
from nina_core.db import create_database
from nina_core.search.indexer import create_fts_table
from nina_core.scheduler.service import SchedulerService
from nina_core.search.watcher import make_watcher_if_enabled

from .app import app, apply_runtime_config


def _write_runtime_state(config_dir: Path, config) -> None:
    runtime_path = get_runtime_path(config_dir)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        json.dumps(
            {
                "profile": config.profile,
                "config_dir": str(config_dir),
                "daemon_host": config.daemon_host,
                "daemon_port": config.daemon_port,
            },
            indent=2,
        )
    )


def main() -> None:
    profile = os.environ.get("NINA_PROFILE", "default")
    config_dir = get_config_dir(profile)
    token_path = get_token_path(config_dir)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        print("Run 'nina init' first.", file=sys.stderr)
        return

    os.environ["NINA_TOKEN"] = read_token(token_path)
    config = load_effective_config(config_dir)
    apply_runtime_config(app, config_dir, config)
    _write_runtime_state(config_dir, config)
    ensure_vault_structure(Path(config.vault_path))
    create_database(config.database_path)
    create_fts_table(config.database_path)

    scheduler = SchedulerService(config.database_path)
    app.state.scheduler = scheduler
    scheduler.start()
    watcher = None
    if config.search.live_indexing:
        watcher = make_watcher_if_enabled(config.database_path, config.vault_path)
        if watcher is not None:
            watcher.start()
    try:
        uvicorn.run(
            app,
            host=config.daemon_host,
            port=config.daemon_port,
            log_level=config.log_level.lower(),
        )
    finally:
        scheduler.shutdown()
        if watcher is not None:
            watcher.stop()


if __name__ == "__main__":
    main()
