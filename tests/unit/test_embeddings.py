from __future__ import annotations

import math
from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.search.embeddings import (
    EmbeddingService,
    EmbeddingStore,
    FakeEmbeddingService,
    ScoredRow,
    decode_embedding,
    encode_embedding,
    reindex_embeddings,
    rrf_merge,
)


def test_encode_decode_round_trip() -> None:
    vec = [0.1, 0.2, 0.3, 0.4]
    blob = encode_embedding(vec)
    decoded = decode_embedding(blob, len(vec))
    assert all(math.isclose(a, b, rel_tol=1e-6) for a, b in zip(decoded, vec, strict=False))


def test_rrf_merge_merges_two_lists() -> None:
    list_a = [
        ScoredRow(path="a.md", title="A", nina_type="note", score=0.0, note_id="a"),
        ScoredRow(path="b.md", title="B", nina_type="note", score=0.0, note_id="b"),
    ]
    list_b = [
        ScoredRow(path="b.md", title="B", nina_type="note", score=0.0, note_id="b"),
        ScoredRow(path="c.md", title="C", nina_type="note", score=0.0, note_id="c"),
    ]
    merged = rrf_merge([list_a, list_b], k=60, limit=5)
    paths = [r.path for r in merged]
    assert paths[0] == "b.md"  # appears in both
    assert set(paths) == {"a.md", "b.md", "c.md"}


def test_fake_embedding_is_deterministic() -> None:
    service: EmbeddingService = FakeEmbeddingService()
    a = service.embed(["hello world"])
    b = service.embed(["hello world"])
    assert a == b
    assert len(a[0]) == 64


def test_fake_embedding_distinguishes_texts() -> None:
    service: EmbeddingService = FakeEmbeddingService()
    a = service.embed(["hello world"])
    b = service.embed(["goodbye world"])
    assert a != b


def test_embedding_store_upsert_and_search(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nina_core.config.settings import SearchConfig

    cfg = SearchConfig(embedding_provider="fake")
    vault = get_vault_path(isolated_config)
    db_path = str(get_database_path(isolated_config))
    note_dir = vault / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "a.md").write_text("---\ntitle: A\nnina_type: note\n---\n\nhello world")
    (note_dir / "b.md").write_text("---\ntitle: B\nnina_type: note\n---\n\ngoodbye world")
    store = EmbeddingStore(db_path, service=FakeEmbeddingService())
    count = reindex_embeddings(db_path, str(vault), config=cfg)
    assert count == 2

    # Search for the exact text of a.md; the fake embedding is deterministic
    # so we can assert the result.
    results = store.search("hello world", limit=5)
    assert any(r.path == "Research/a.md" for r in results)


def test_embedding_store_skip_unchanged(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nina_core.config.settings import SearchConfig

    cfg = SearchConfig(embedding_provider="fake")
    vault = get_vault_path(isolated_config)
    db_path = str(get_database_path(isolated_config))
    note_dir = vault / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "a.md").write_text("---\ntitle: A\nnina_type: note\n---\n\nhello")
    EmbeddingStore(db_path, service=FakeEmbeddingService())
    first = reindex_embeddings(db_path, str(vault), config=cfg)
    second = reindex_embeddings(db_path, str(vault), config=cfg)
    assert first == 1
    assert second == 0


def test_embedding_store_delete(isolated_config: Path) -> None:
    vault = get_vault_path(isolated_config)
    db_path = str(get_database_path(isolated_config))
    note_dir = vault / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "a.md").write_text("---\ntitle: A\nnina_type: note\n---\n\nhello")
    store = EmbeddingStore(db_path, service=FakeEmbeddingService())
    reindex_embeddings(db_path, str(vault))
    store.delete("a")
    rows = store.list_rows()
    assert rows == []
