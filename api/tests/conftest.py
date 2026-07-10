"""Shared fixtures for api/ tests.

`client` isolates the DB only (a fresh SQLite file per test, via
dependency_overrides -- never touches sim/ledger.db). `memory_test_client`
additionally isolates the memory layer to a unique test container and skips
gracefully if the local Supermemory server isn't reachable, matching the
pattern used in memory/tests/conftest.py.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import sim.models  # noqa: F401 -- registers table metadata on SQLModel.metadata
from api.deps import get_memory_client, get_session
from api.main import app
from memory.client import SupermemoryClient


@pytest.fixture
def db_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine):
    def override_get_session():
        with Session(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


def _memory_server_reachable() -> bool:
    base_url = os.environ.get("SUPERMEMORY_BASE_URL", "http://localhost:6767")
    try:
        httpx.get(base_url, timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture
def require_memory_server():
    if not os.environ.get("SUPERMEMORY_API_KEY") or not _memory_server_reachable():
        pytest.skip("Supermemory server not reachable; skipping memory-backed API tests")


def run_backtest(client: TestClient, **overrides) -> dict:
    """POST /api/backtest with sensible defaults (hits the warm AAPL 2023 cache
    from earlier dev runs -- fast, no fresh network fetch), returning the
    parsed BacktestRunOut body."""
    payload = {"symbol": "AAPL", "start": "2023-01-01", "end": "2023-06-30", **overrides}
    response = client.post("/api/backtest", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def memory_test_client(db_engine, require_memory_server):
    def override_get_session():
        with Session(db_engine, expire_on_commit=False) as session:
            yield session

    container_tag = f"trading_system_api_test_{uuid.uuid4().hex[:10]}"
    memory_client = SupermemoryClient(container_tag=container_tag)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_memory_client] = lambda: memory_client
    with TestClient(app) as test_client:
        test_client.memory_client = memory_client  # exposed so tests can seed data directly
        yield test_client
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_memory_client, None)
