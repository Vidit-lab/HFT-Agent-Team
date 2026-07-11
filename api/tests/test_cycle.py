"""Integration tests against a real LLM (Groq) and the live local Supermemory
server (via the memory_test_client fixture). Skipped, not failed, if either
is unavailable.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _require_groq():
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping agent cycle tests")


def test_run_cycle_executes_end_to_end(memory_test_client):
    response = memory_test_client.post("/api/run-cycle", json={"symbol": "AAPL", "run_id": "test-cycle-run"})
    assert response.status_code == 200
    body = response.json()

    assert body["run_id"] == "test-cycle-run"
    assert body["symbol"] == "AAPL"
    assert body["action"] in ("buy", "sell", "hold")
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["rationale"]

    portfolio = memory_test_client.get("/api/portfolio", params={"run_id": "test-cycle-run"})
    assert portfolio.status_code == 200
    assert portfolio.json()["run_id"] == "test-cycle-run"


def test_run_cycle_second_call_resumes_state_and_upserts_position(memory_test_client):
    run_id = "test-cycle-resume"
    first = memory_test_client.post("/api/run-cycle", json={"symbol": "AAPL", "run_id": run_id}).json()
    second = memory_test_client.post("/api/run-cycle", json={"symbol": "AAPL", "run_id": run_id}).json()

    expected_trade_count = sum(1 for r in (first, second) if r["action"] != "hold")
    trades = memory_test_client.get("/api/trades", params={"run_id": run_id}).json()
    assert trades["total"] == expected_trade_count

    portfolio = memory_test_client.get("/api/portfolio", params={"run_id": run_id}).json()
    aapl_positions = [p for p in portfolio["positions"] if p["symbol"] == "AAPL"]
    assert len(aapl_positions) <= 1  # upserted, never duplicated


def test_run_cycle_writes_a_memory_when_a_trade_happens(memory_test_client):
    response = memory_test_client.post(
        "/api/run-cycle", json={"symbol": "AAPL", "run_id": "test-cycle-memory"}
    ).json()
    if response["action"] == "hold":
        pytest.skip("agent chose to hold this cycle; nothing to verify")
    assert response["memory_write_id"]
    assert response["trade_id"] is not None


def test_run_cycle_invalid_symbol_is_422(memory_test_client):
    response = memory_test_client.post(
        "/api/run-cycle", json={"symbol": "NOT_A_REAL_TICKER_XYZ123", "run_id": "test-cycle-bad"}
    )
    assert response.status_code == 422
