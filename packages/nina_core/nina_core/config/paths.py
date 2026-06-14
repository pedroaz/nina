import os
from pathlib import Path

DEFAULT_PROFILE = "default"


def get_config_dir(profile: str = DEFAULT_PROFILE) -> Path:
    env_dir = os.environ.get("NINA_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".nina" / profile


def get_vault_path(config_dir: Path) -> Path:
    return config_dir / "vault"


def get_database_path(config_dir: Path) -> Path:
    return config_dir / "nina.db"


def get_token_path(config_dir: Path) -> Path:
    return config_dir / "token"


def get_config_path(config_dir: Path) -> Path:
    return config_dir / "config.yaml"


def get_log_path(config_dir: Path) -> Path:
    return config_dir / "logs" / "daemon.log"


def get_pid_path(config_dir: Path) -> Path:
    return config_dir / "daemon.pid"
