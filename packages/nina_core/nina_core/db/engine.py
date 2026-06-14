from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def make_engine(db_path: str) -> Any:
    return create_engine(f"sqlite:///{db_path}", echo=False)


def make_session(engine: Any) -> Any:
    return sessionmaker(bind=engine)
