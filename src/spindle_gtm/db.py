"""Local SQLite engine + session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from spindle_gtm.config import Settings, get_settings


def make_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{settings.db_path}", echo=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    engine = engine or make_engine()
    with Session(engine) as session:
        yield session
