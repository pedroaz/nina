import os
import sys

import uvicorn
from nina_core.config import (
    get_config_dir,
    get_config_path,
    get_database_path,
    get_token_path,
    get_vault_path,
    read_token,
)
from nina_core.db import create_database
from nina_core.scheduler.service import SchedulerService

from .app import app


def main() -> None:
    profile = os.environ.get("NINA_PROFILE", "default")
    config_dir = get_config_dir(profile)
    token_path = get_token_path(config_dir)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        print("Run 'nina init' first.", file=sys.stderr)
        return
    os.environ["NINA_TOKEN"] = read_token(token_path)
    os.environ["NINA_CONFIG_DIR"] = str(config_dir)
    os.environ["NINA_VAULT_PATH"] = str(get_vault_path(config_dir))
    os.environ["NINA_DATABASE_PATH"] = str(get_database_path(config_dir))
    db_path = str(get_database_path(config_dir))
    create_database(db_path)
    scheduler = SchedulerService(db_path)
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
