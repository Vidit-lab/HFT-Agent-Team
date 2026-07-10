"""SQLite engine/session setup for the simulation ledger."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from sim import models  # noqa: F401 -- ensures table metadata is registered

DEFAULT_DB_PATH = "sim/ledger.db"


def get_engine(db_path: str = DEFAULT_DB_PATH):
    url = f"sqlite:///{db_path}" if db_path != ":memory:" else "sqlite://"
    return create_engine(url)


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session(engine) -> Session:
    # expire_on_commit=False: callers commonly read a row's fields (e.g. a
    # freshly-persisted BacktestResult) right after commit(), once the `with`
    # block -- and the session -- has already closed.
    return Session(engine, expire_on_commit=False)
