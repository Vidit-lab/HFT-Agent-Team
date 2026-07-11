"""FastAPI dependencies: DB session, memory client, and "which run" resolution.

Both `get_db_engine` and `get_memory_client` are meant to be overridden via
`app.dependency_overrides` in tests, so each test gets an isolated SQLite
file and (for memory-backed routes) a uniquely-tagged Supermemory container
rather than touching real dev data.
"""

from __future__ import annotations

from functools import lru_cache

from sqlmodel import Session, select

from memory.client import SupermemoryClient
from sim.db import get_engine, init_db
from sim.models import Portfolio


@lru_cache
def get_db_engine():
    engine = get_engine()
    init_db(engine)
    return engine


def get_session():
    with Session(get_db_engine(), expire_on_commit=False) as session:
        yield session


def get_memory_client() -> SupermemoryClient:
    return SupermemoryClient()


def resolve_run_id(session: Session, run_id: str | None) -> str | None:
    """Explicit `run_id` wins; otherwise fall back to the most recently
    active run. Resolved via Portfolio (not BacktestResult) because every
    run gets a Portfolio snapshot -- batch backtests from POST /api/backtest
    AND paper-trading runs from POST /api/run-cycle alike -- whereas
    BacktestResult only exists for *completed* batch runs; a paper run is
    ongoing indefinitely and never gets one. Portfolio.id (insertion order)
    rather than .timestamp, since a batch backtest's rows carry historical
    market-data timestamps that don't reflect when the run actually
    happened in wall-clock time. Returns None if no run exists yet."""
    if run_id:
        return run_id
    latest = session.exec(select(Portfolio).order_by(Portfolio.id.desc())).first()
    return latest.run_id if latest else None
