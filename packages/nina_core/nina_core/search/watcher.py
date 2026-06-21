from __future__ import annotations

import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from nina_core.obsidian.policy import (
    INDEX_EXCLUDED_PREFIXES,
    TEMP_NOTE_SUFFIXES,
    is_indexable_note_path,
)
from nina_core.search.embeddings import EmbeddingStore
from nina_core.search.indexer import index_note


LOGGER = logging.getLogger(__name__)


REFUSED_SUFFIXES = TEMP_NOTE_SUFFIXES
REFUSED_PATHS = INDEX_EXCLUDED_PREFIXES


def _should_skip(path: Path, vault: Path) -> bool:
    if path.is_absolute():
        try:
            path.relative_to(vault)
        except ValueError:
            return True
    return not is_indexable_note_path(path, vault)


class _VaultEventHandler(FileSystemEventHandler):
    def __init__(self, db_path: str, vault: Path, debounce_seconds: float = 0.2) -> None:
        self.db_path = db_path
        self.vault = vault
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, path: Path) -> None:
        rel = str(path.relative_to(self.vault))
        with self._lock:
            existing = self._pending.get(rel)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self.debounce_seconds, self._apply, args=[rel])
            timer.daemon = True
            self._pending[rel] = timer
            timer.start()

    def _apply(self, rel_path: str) -> None:
        with self._lock:
            self._pending.pop(rel_path, None)
        full_path = self.vault / rel_path
        try:
            if not full_path.exists() or not full_path.is_file():
                self._remove_from_indexes(rel_path)
                return
            index_note(self.db_path, self.vault, rel_path)
            self._embed(rel_path, full_path)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Failed to handle vault change for %s: %s", rel_path, exc)

    def _embed(self, rel_path: str, full_path: Path) -> None:
        try:
            import frontmatter

            content = full_path.read_text()
            post = frontmatter.loads(content)
            from nina_core.search.embeddings import hash_text

            note_id = post.metadata.get("nina_id") or hash_text(rel_path)
            title = post.metadata.get("title", full_path.stem)
            nina_type = post.metadata.get("nina_type", "note")
            store = EmbeddingStore(self.db_path)
            store.upsert(note_id, rel_path, title, nina_type, post.content)
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("Embedding update skipped for %s: %s", rel_path, exc)

    def _remove_from_indexes(self, rel_path: str) -> None:
        try:
            EmbeddingStore(self.db_path).delete_path(rel_path)
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("Embedding delete skipped for %s: %s", rel_path, exc)
        try:
            index_note(self.db_path, self.vault, rel_path)
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("Index delete skipped for %s: %s", rel_path, exc)

    def on_modified(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        self._handle(event)

    def on_created(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        src = getattr(event, "src_path", None)
        if src:
            self._handle_removed_path(Path(src))
        dest = getattr(event, "dest_path", None)
        if dest:
            self._handle_path(Path(dest))

    def on_deleted(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        path = getattr(event, "src_path", None)
        if not path:
            return
        self._handle_removed_path(Path(path))

    def _handle_removed_path(self, target: Path) -> None:
        if _should_skip(target, self.vault):
            return
        try:
            rel = str(target.relative_to(self.vault))
        except ValueError:
            return
        self._remove_from_indexes(rel)

    def _handle(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return
        path = getattr(event, "src_path", None)
        if not path:
            return
        self._handle_path(Path(path))

    def _handle_path(self, path: Path) -> None:
        if _should_skip(path, self.vault):
            return
        self._schedule(path)


class VaultWatcher:
    def __init__(self, db_path: str, vault_path: str | Path) -> None:
        self.db_path = db_path
        self.vault_path = Path(vault_path)
        self._observer: Observer | None = None
        self._handler: _VaultEventHandler | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        self.vault_path.mkdir(parents=True, exist_ok=True)
        handler = _VaultEventHandler(self.db_path, self.vault_path)
        observer = Observer()
        observer.schedule(handler, str(self.vault_path), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer
        self._handler = handler

    def stop(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=2)
        self._observer = None
        self._handler = None

    @property
    def running(self) -> bool:
        return self._observer is not None


def make_watcher_if_enabled(
    db_path: str,
    vault_path: str | Path,
    enabled: bool = True,
) -> VaultWatcher | None:
    """Create a vault watcher if live indexing is enabled.

    The caller is responsible for passing `enabled` based on
    `NinaConfig.search.live_indexing`. We do not read from any env var.
    """
    if not enabled:
        return None
    return VaultWatcher(db_path, vault_path)
