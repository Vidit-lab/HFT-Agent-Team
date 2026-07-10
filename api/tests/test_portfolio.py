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
        pytest.skip("network not reachable; skipping portfolio API tests")


def test_portfolio_404_when_no_runs_exist(client):
    response = client.get("/api/portfolio")
    assert response.status_code == 404


def test_portfolio_reflects_the_backtest_that_was_run(client):
    run = run_backtest(client)

    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()

    assert body["run_id"] == run["run_id"]
    assert body["strategy"] == "sma_crossover"
    assert body["symbol"] == "AAPL"
    assert body["latest"]["equity"] == pytest.approx(run["final_equity"])
    assert len(body["equity_curve"]) > 0
    assert body["equity_curve"][0]["cash"] == 100_000.0  # first snapshot, no fills yet


def test_portfolio_run_id_query_param_overrides_latest(client):
    run_a = run_backtest(client, end="2023-06-30")
    run_b = run_backtest(client, end="2023-12-31")
    assert run_a["run_id"] != run_b["run_id"]

    # explicit run_id wins
    resp_a = client.get("/api/portfolio", params={"run_id": run_a["run_id"]})
    assert resp_a.json()["run_id"] == run_a["run_id"]

    # default falls back to the most recently created run
    resp_default = client.get("/api/portfolio")
    assert resp_default.json()["run_id"] == run_b["run_id"]


def test_portfolio_unknown_run_id_is_404(client):
    response = client.get("/api/portfolio", params={"run_id": "does-not-exist"})
    assert response.status_code == 404
