from __future__ import annotations

import base64
import hashlib
import os
import warnings
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nina_core.models.models import NoteEmbedding
from nina_core.obsidian.policy import iter_indexable_note_files


@contextmanager
def _suppress_hf_unauth_warning() -> Any:
    """Suppress `huggingface_hub`'s "unauthenticated requests" `UserWarning`
    when no `HF_TOKEN` is set. See `transcription.py` for the rationale."""
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        yield
        return
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*unauthenticated requests to the HF Hub.*",
            category=UserWarning,
        )
        yield


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ScoredRow:
    path: str
    title: str
    nina_type: str
    score: float
    note_id: str


def encode_embedding(vector: list[float]) -> str:
    arr = np.asarray(vector, dtype=np.float32)
    return base64.b64encode(arr.tobytes()).decode("ascii")


def decode_embedding(blob: str, dim: int) -> list[float]:
    raw = base64.b64decode(blob.encode("ascii"))
    arr = np.frombuffer(raw, dtype=np.float32)
    if arr.size != dim:
        raise ValueError(f"Embedding dimension mismatch: stored={arr.size} expected={dim}")
    return arr.tolist()


class EmbeddingService(ABC):
    model_name: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def cosine_top_k(self, query: list[float], rows: list[ScoredRow], k: int) -> list[ScoredRow]:
        if not rows or not query:
            return []
        q = np.asarray(query, dtype=np.float32)
        q_norm = float(np.linalg.norm(q)) or 1.0
        scored: list[ScoredRow] = []
        for row in rows:
            stored = np.asarray(decode_embedding_blob(row), dtype=np.float32)  # type: ignore[arg-type]
            v_norm = float(np.linalg.norm(stored)) or 1.0
            sim = float(np.dot(q, stored) / (q_norm * v_norm))
            scored.append(
                ScoredRow(
                    path=row.path,
                    title=row.title,
                    nina_type=row.nina_type,
                    score=sim,
                    note_id=row.note_id,
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


def decode_embedding_blob(row: ScoredRow) -> list[float]:  # pragma: no cover - helper
    raise NotImplementedError


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def hash_embedding(embedding: list[float]) -> str:
    arr = np.asarray(embedding, dtype=np.float32)
    return hashlib.sha256(arr.tobytes()).hexdigest()[:32]


class FakeEmbeddingService(EmbeddingService):
    """Deterministic random embeddings. Useful for tests and offline dev."""

    model_name = "fake-embedding"
    dim = 64

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            v = v / (np.linalg.norm(v) or 1.0)
            out.append(v.tolist())
        return out

    def cosine_top_k(self, query: list[float], rows: list[ScoredRow], k: int) -> list[ScoredRow]:
        if not rows or not query:
            return []
        q = np.asarray(query, dtype=np.float32)
        q_norm = float(np.linalg.norm(q)) or 1.0
        scored: list[ScoredRow] = []
        for row in rows:
            stored_text = row.path + row.title
            seed = int(hashlib.sha256(stored_text.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            v = v / (np.linalg.norm(v) or 1.0)
            sim = float(np.dot(q, v) / (q_norm * (float(np.linalg.norm(v)) or 1.0)))
            scored.append(
                ScoredRow(
                    path=row.path,
                    title=row.title,
                    nina_type=row.nina_type,
                    score=sim,
                    note_id=row.note_id,
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


class FastembedEmbeddingService(EmbeddingService):
    """Local embeddings using `fastembed` (ONNX, no torch)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        with _suppress_hf_unauth_warning():
            self._model = TextEmbedding(model_name=model_name)
        # fastembed lazy-loads the model on first embed; get_dim via first call
        with _suppress_hf_unauth_warning():
            try:
                probe = next(iter(self._model.embed(["probe"])))
                self.dim = len(probe)
            except Exception as exc:  # pragma: no cover - depends on model
                raise RuntimeError(f"Failed to initialize fastembed model {model_name}: {exc}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with _suppress_hf_unauth_warning():
            embeddings = list(self._model.embed(texts))
        return [list(map(float, vec)) for vec in embeddings]


class OpenAIEmbeddingService(EmbeddingService):
    model_name = "disabled"
    dim = 0

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Remote OpenAI embeddings are disabled; use search.embedding_provider=fastembed.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("Remote OpenAI embeddings are disabled; use search.embedding_provider=fastembed.")


def build_embedding_service(
    config: "SearchConfig | None" = None,  # noqa: F821
) -> EmbeddingService:
    """Build an embedding service from Nina search config."""
    from nina_core.config.settings import SearchConfig

    cfg = config or SearchConfig()
    provider = cfg.embedding_provider.lower()
    if provider == "fake":
        return FakeEmbeddingService()
    if provider == "openai":
        raise RuntimeError("Remote OpenAI embeddings are disabled; use search.embedding_provider=fastembed.")
    if provider == "fastembed":
        return FastembedEmbeddingService(model_name=cfg.embedding_model)
    raise RuntimeError(f"Unsupported embedding provider: {provider}")


def rrf_merge(rankings: list[list[ScoredRow]], k: int = 60, limit: int = 5) -> list[ScoredRow]:
    """Reciprocal Rank Fusion across multiple ranked lists."""

    scores: dict[str, ScoredRow] = {}
    for ranking in rankings:
        for rank, row in enumerate(ranking, start=1):
            key = row.path
            existing = scores.get(key)
            rrf_score = 1.0 / (k + rank)
            if existing is None:
                scores[key] = ScoredRow(
                    path=row.path,
                    title=row.title,
                    nina_type=row.nina_type,
                    score=rrf_score,
                    note_id=row.note_id,
                )
            else:
                existing.score += rrf_score
    merged = list(scores.values())
    merged.sort(key=lambda r: r.score, reverse=True)
    return merged[:limit]


class EmbeddingStore:
    def __init__(
        self,
        db_path: str,
        service: EmbeddingService | None = None,
        config: "SearchConfig | None" = None,  # noqa: F821
    ) -> None:
        self.db_path = db_path
        self.service = service or build_embedding_service(config=config)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _session(self):
        return self.SessionLocal()

    def upsert(self, note_id: str, path: str, title: str, nina_type: str, body: str) -> bool:
        content_hash = hash_text(body)
        db = self._session()
        try:
            existing = (
                db.query(NoteEmbedding)
                .filter(
                    NoteEmbedding.note_id == note_id, NoteEmbedding.model == self.service.model_name
                )
                .first()
            )
            if existing and existing.content_hash == content_hash:
                return False
            embeddings = self.service.embed([body])
            if not embeddings:
                return False
            vector = embeddings[0]
            blob = encode_embedding(vector)
            now = _now()
            if existing is None:
                row = NoteEmbedding(
                    id=hash_text(f"{note_id}|{self.service.model_name}"),
                    note_id=note_id,
                    path=path,
                    title=title,
                    nina_type=nina_type,
                    model=self.service.model_name,
                    dim=self.service.dim,
                    embedding_blob=blob,
                    content_hash=content_hash,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            else:
                existing.title = title
                existing.nina_type = nina_type
                existing.dim = self.service.dim
                existing.embedding_blob = blob
                existing.content_hash = content_hash
                existing.updated_at = now
            db.commit()
            return True
        finally:
            db.close()

    def delete(self, note_id: str) -> None:
        db = self._session()
        try:
            db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note_id).delete()
            db.commit()
        finally:
            db.close()

    def delete_path(self, path: str) -> None:
        db = self._session()
        try:
            db.query(NoteEmbedding).filter(
                NoteEmbedding.path == path,
                NoteEmbedding.model == self.service.model_name,
            ).delete()
            db.commit()
        finally:
            db.close()

    def prune_to_paths(self, paths: set[str]) -> None:
        db = self._session()
        try:
            rows = (
                db.query(NoteEmbedding).filter(NoteEmbedding.model == self.service.model_name).all()
            )
            for row in rows:
                if row.path not in paths:
                    db.delete(row)
            db.commit()
        finally:
            db.close()

    def search(self, query: str, limit: int = 5) -> list[ScoredRow]:
        if not query:
            return []
        embeddings = self.service.embed([query])
        if not embeddings:
            return []
        query_vec = embeddings[0]
        db = self._session()
        try:
            rows = (
                db.query(NoteEmbedding).filter(NoteEmbedding.model == self.service.model_name).all()
            )
            scored_rows: list[ScoredRow] = []
            for row in rows:
                scored_rows.append(
                    ScoredRow(
                        path=row.path,
                        title=row.title,
                        nina_type=row.nina_type,
                        score=0.0,
                        note_id=row.note_id,
                    )
                )
            return self.service.cosine_top_k(query_vec, scored_rows, limit)
        finally:
            db.close()

    def list_rows(self) -> list[ScoredRow]:
        db = self._session()
        try:
            rows = (
                db.query(NoteEmbedding).filter(NoteEmbedding.model == self.service.model_name).all()
            )
            return [
                ScoredRow(
                    path=row.path,
                    title=row.title,
                    nina_type=row.nina_type,
                    score=0.0,
                    note_id=row.note_id,
                )
                for row in rows
            ]
        finally:
            db.close()


def reindex_embeddings(
    db_path: str,
    vault_path: str,
    config: "SearchConfig | None" = None,  # noqa: F821
) -> int:
    """Re-embed all notes in the vault. Returns the number of notes re-embedded."""

    import frontmatter
    from pathlib import Path

    from nina_core.search.indexer import index_note

    store = EmbeddingStore(db_path, config=config)
    vault = Path(vault_path)
    count = 0
    seen_paths: set[str] = set()
    for rel_path, path in iter_indexable_note_files(vault):
        seen_paths.add(rel_path)
        content = path.read_text()
        post = frontmatter.loads(content)
        note_id = post.metadata.get("nina_id") or hash_text(rel_path)
        title = post.metadata.get("title", path.stem)
        nina_type = post.metadata.get("nina_type", "note")
        if store.upsert(note_id, rel_path, title, nina_type, post.content):
            count += 1
        # Use index_note (idempotent DELETE+INSERT) instead of _index_single_note
        index_note(db_path, vault, rel_path)
    store.prune_to_paths(seen_paths)
    return count


def reindex_vault(
    db_path: str,
    vault_path: str,
    config: "SearchConfig | None" = None,  # noqa: F821
) -> dict[str, int]:
    """Reindex the vault: FTS5 + embeddings. Returns counts."""

    from nina_core.search.indexer import index_notes

    index_notes(db_path, vault_path)
    embedded = reindex_embeddings(db_path, vault_path, config=config)
    return {"fts": -1, "embedded": embedded}  # fts count is implicit (full rebuild)
