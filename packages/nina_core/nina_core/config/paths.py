import os
from pathlib import Path

from .settings import NinaConfig

DEFAULT_PROFILE = "default"


def get_config_dir(profile: str = DEFAULT_PROFILE) -> Path:
    env_dir = os.environ.get("NINA_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".nina" / profile


def get_config_path(config_dir: Path) -> Path:
    return config_dir / "config.yaml"


def load_effective_config(config_dir: Path) -> NinaConfig:
    return NinaConfig.load(get_config_path(config_dir)).with_resolved_paths(config_dir)


def get_vault_path(config_dir: Path) -> Path:
    return Path(load_effective_config(config_dir).vault_path)


def get_database_path(config_dir: Path) -> Path:
    return Path(load_effective_config(config_dir).database_path)


def get_token_path(config_dir: Path) -> Path:
    return config_dir / "token"


def get_runtime_path(config_dir: Path) -> Path:
    return config_dir / "daemon.json"


def get_log_path(config_dir: Path) -> Path:
    return config_dir / "logs" / "daemon.log"


def get_pid_path(config_dir: Path) -> Path:
    return config_dir / "daemon.pid"
