from __future__ import annotations

from typing import Any

import typer

from .api import request
from .output import console, print_json

search_app = typer.Typer(help="Search commands")


def _print_json(data: Any) -> None:
    print_json(data)


@search_app.command("run")
def search_run(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, "--limit", help="Maximum number of results"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    response = request("POST", "/search", json={"query": query, "limit": limit})
    data = response.json()
    if json_output:
        _print_json(data)
        return
    if not data:
        console.print("No results.")
        return
    for index, hit in enumerate(data, start=1):
        title = hit.get("title") or hit.get("path")
        path = hit.get("path")
        ntype = hit.get("nina_type") or "?"
        console.print(f"{index}. [{ntype}] {title} ({path})")


@search_app.command("reindex")
def search_reindex() -> None:
    response = request("POST", "/search/reindex", json={})
    data = response.json()
    console.print(f"Reindexed: {data.get('reindexed')}")


@search_app.command("reindex-embeddings")
def search_reindex_embeddings() -> None:
    """Force a full re-embedding pass over the vault.

    Useful after switching embedding models or if the embeddings index
    has drifted from the FTS index. The watcher and the `reindex-vault`
    scheduled job handle this incrementally.
    """

    import os
    from pathlib import Path

    from nina_core.config import get_config_dir, get_database_path, get_vault_path
    from nina_core.search.embeddings import reindex_vault

    config_dir_str = os.environ.get("NINA_CONFIG_DIR")
    if not config_dir_str:
        config_dir_str = str(get_config_dir(os.environ.get("NINA_PROFILE", "default")))
    config_dir = Path(config_dir_str)
    db_path = str(get_database_path(config_dir))
    vault_path = str(get_vault_path(config_dir))
    result = reindex_vault(db_path, vault_path)
    console.print(f"Reindexed vault. Embedded: {result.get('embedded', 0)}")
