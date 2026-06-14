from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .engine import Base  # type: ignore[import-untyped]
from .seed import seed_kanban_columns, seed_scheduled_jobs


def create_database(db_path: str) -> None:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)  # type: ignore[union-attr]
    SessionLocal: Any = sessionmaker(bind=engine)
    db = SessionLocal()
    seed_kanban_columns(db)
    seed_scheduled_jobs(db)
    db.commit()
    db.close()
