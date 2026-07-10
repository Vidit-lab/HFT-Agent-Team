"""Integration tests against real Yahoo Finance data (via sim/data_loader),
skipped rather than failed when the network isn't reachable.
"""

from __future__ import annotations

import httpx
import pytest

from .conftest import run_backtest


def _network_available() -> bool:
    try:
        httpx.get("https://query1.finance.yahoo.com", timeout=3.0)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(autouse=True)
def _require_network():
    if not _network_available():
        pytest.skip("network not reachable; skipping backtest API tests")


def test_post_backtest_runs_and_persists(client):
    body = run_backtest(client)

    assert body["symbol"] == "AAPL"
    assert body["strategy"] == "sma_crossover"
    assert body["initial_cash"] == 100_000.0
    assert body["num_trades"] > 0
    assert body["run_id"]


def test_post_backtest_invalid_symbol_is_422(client):
    response = client.post(
        "/api/backtest",
        json={"symbol": "NOT_A_REAL_TICKER_XYZ123", "start": "2023-01-01", "end": "2023-01-31"},
    )
    assert response.status_code == 422


def test_post_backtest_default_params(client):
    response = client.post("/api/backtest", json={"start": "2023-01-01", "end": "2023-06-30"})
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"  # default
