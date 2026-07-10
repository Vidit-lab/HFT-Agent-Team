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
        pytest.skip("network not reachable; skipping trades API tests")


def test_trades_404_when_no_runs_exist(client):
    assert client.get("/api/trades").status_code == 404


def test_trades_list_matches_backtest_trade_count(client):
    run = run_backtest(client, end="2023-12-31")

    response = client.get("/api/trades", params={"limit": 500})
    assert response.status_code == 200
    body = response.json()

    assert body["run_id"] == run["run_id"]
    assert body["total"] == run["num_trades"]
    assert len(body["trades"]) == run["num_trades"]


def test_trades_pagination(client):
    run = run_backtest(client, end="2023-12-31")
    assert run["num_trades"] >= 2, "fixture backtest should produce enough trades to paginate"

    page1 = client.get("/api/trades", params={"limit": 1, "offset": 0}).json()
    page2 = client.get("/api/trades", params={"limit": 1, "offset": 1}).json()

    assert len(page1["trades"]) == 1
    assert len(page2["trades"]) == 1
    assert page1["trades"][0]["id"] != page2["trades"][0]["id"]
    assert page1["total"] == page2["total"] == run["num_trades"]


def test_get_single_trade_by_id(client):
    run_backtest(client)
    first = client.get("/api/trades", params={"limit": 1}).json()["trades"][0]

    response = client.get(f"/api/trades/{first['id']}")
    assert response.status_code == 200
    assert response.json() == first


def test_get_missing_trade_is_404(client):
    response = client.get("/api/trades/999999")
    assert response.status_code == 404
