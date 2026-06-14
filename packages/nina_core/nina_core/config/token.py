import secrets
from pathlib import Path


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def read_token(path: Path) -> str:
    return path.read_text().strip()


def write_token(path: Path, token: str) -> None:
    path.write_text(token)
    path.chmod(0o600)
