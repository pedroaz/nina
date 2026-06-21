from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from nina_core.db.engine import make_engine, make_session


class DaemonDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = ""
        self.engine: Any | None = None
        self.SessionLocal: Any | None = None
        self.rebind(db_path)

    def rebind(self, db_path: str) -> None:
        if self.engine is not None and self.db_path == db_path:
            return
        self.dispose()
        self.db_path = db_path
        self.engine = make_engine(db_path)
        self.SessionLocal = make_session(self.engine)

    def session(self) -> Session:
        if self.SessionLocal is None:
            raise RuntimeError("daemon database is not initialized")
        return self.SessionLocal()

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
        self.engine = None
        self.SessionLocal = None
