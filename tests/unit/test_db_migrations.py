from __future__ import annotations

from pathlib import Path

from nina_core.db import create_database
from sqlalchemy import create_engine, text


def test_create_database_adds_missing_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "nina.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        # Create a conversation_sessions table that predates cancel_requested.
        conn.execute(
            text(
                "CREATE TABLE conversation_sessions ("
                " id TEXT PRIMARY KEY,"
                " mode TEXT NOT NULL,"
                " title TEXT,"
                " created_at TEXT NOT NULL,"
                " updated_at TEXT NOT NULL,"
                " completed_at TEXT"
                ")"
            )
        )
        conn.commit()
    engine.dispose()

    # The lightweight migration should add cancel_requested.
    create_database(str(db_path))

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(conversation_sessions)"))]
    assert "cancel_requested" in cols


def test_create_database_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "nina.db"
    create_database(str(db_path))
    # Running a second time should not raise.
    create_database(str(db_path))


def test_create_database_creates_note_embeddings(tmp_path: Path) -> None:
    db_path = tmp_path / "nina.db"
    create_database(str(db_path))
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        names = [
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        ]
    assert "note_embeddings" in names
