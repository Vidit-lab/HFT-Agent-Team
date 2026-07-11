"""Integration tests against a real LLM (Groq) and the live local Supermemory
server (via the memory_test_client fixture). Skipped, not failed, if either
is unavailable -- same pattern as test_cycle.py.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _require_groq():
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping reflection tests")


def test_reflect_endpoint_with_no_trades_returns_empty(memory_test_client):
    response = memory_test_client.post("/api/reflect", json={"run_id": "test-reflect-empty", "max_trades": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["reflected_count"] == 0
    assert body["reflections"] == []


def test_reflect_endpoint_reflects_a_trade_via_forward_return(memory_test_client):
    run_id = "test-reflect-cycle"
    cycle = None
    for _ in range(3):
        cycle = memory_test_client.post("/api/run-cycle", json={"symbol": "AAPL", "run_id": run_id}).json()
        if cycle["action"] != "hold":
            break
    if cycle is None or cycle["action"] == "hold":
        pytest.skip("agent held across all attempts; nothing to reflect on this run")

    response = memory_test_client.post(
        "/api/reflect", json={"run_id": run_id, "max_trades": 5, "lookback_days": 0}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reflected_count"] >= 1

    reflection = body["reflections"][0]
    assert reflection["outcome"] in ("win", "loss", "neutral")
    assert reflection["lesson_text"]
    assert reflection["lesson_memory_id"]
    assert reflection["diagnosis"]
    assert 0.0 <= reflection["confidence"] <= 1.0


def test_reflect_endpoint_is_idempotent(memory_test_client):
    run_id = "test-reflect-idempotent"
    cycle = memory_test_client.post("/api/run-cycle", json={"symbol": "AAPL", "run_id": run_id}).json()
    if cycle["action"] == "hold":
        pytest.skip("agent held this cycle; nothing to reflect on")

    first = memory_test_client.post("/api/reflect", json={"run_id": run_id, "lookback_days": 0}).json()
    second = memory_test_client.post("/api/reflect", json={"run_id": run_id, "lookback_days": 0}).json()

    assert first["reflected_count"] >= 1
    assert second["reflected_count"] == 0


def test_reflect_endpoint_respects_max_trades(memory_test_client):
    run_id = "test-reflect-max"
    for _ in range(2):
        memory_test_client.post("/api/run-cycle", json={"symbol": "AAPL", "run_id": run_id})

    response = memory_test_client.post(
        "/api/reflect", json={"run_id": run_id, "max_trades": 1, "lookback_days": 0}
    )
    body = response.json()
    assert body["reflected_count"] <= 1
