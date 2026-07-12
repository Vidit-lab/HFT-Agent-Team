"""Integration tests for POST /api/consolidate against a real LLM (Groq) and the
live local Supermemory server. Skipped, not failed, if either is unavailable --
same pattern as test_reflect.py.
"""

from __future__ import annotations

import os
import time

import pytest

from memory.schemas import LessonMemory, Outcome


@pytest.fixture(autouse=True)
def _require_groq():
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping consolidation tests")


def _seed_lessons(memory_client, texts, *, regime="trending_up", outcome=Outcome.WIN):
    for text in texts:
        memory_client.write_lesson(
            LessonMemory(strategy="agent_graph_v1", regime=regime, lesson_text=text, asset="AAPL", outcome=outcome)
        )
    time.sleep(4)  # let indexing settle so list_documents sees them


def test_consolidate_with_no_lessons_returns_empty(memory_test_client):
    response = memory_test_client.post("/api/consolidate", json={"scope": "test-empty"})
    assert response.status_code == 200
    body = response.json()
    assert body["consolidated_count"] == 0
    assert body["consolidations"] == []


def test_consolidate_produces_higher_order_lessons(memory_test_client):
    _seed_lessons(
        memory_test_client.memory_client,
        [
            "In trending_up regimes with a strong Bull thesis, sizing up tends to pay off.",
            "During AAPL uptrends, a confident Bull case justified sizing up to capture the move.",
            "When trending_up and the bull argument outweighs the bear, a wider size envelope is warranted.",
        ],
    )

    response = memory_test_client.post("/api/consolidate", json={"scope": "test-consolidate"})
    assert response.status_code == 200
    body = response.json()

    assert body["consolidated_count"] >= 1
    meta = body["consolidations"][0]
    assert meta["meta_lesson"]
    assert meta["consolidated_memory_id"]
    assert meta["regime"] == "trending_up"
    assert meta["outcome"] == "win"
    assert meta["source_count"] >= 1
    assert len(meta["source_memory_ids"]) == meta["source_count"]
    assert 0.0 <= meta["confidence"] <= 1.0


def test_consolidate_is_idempotent(memory_test_client):
    _seed_lessons(
        memory_test_client.memory_client,
        [
            "Momentum entries after consecutive green candles had strong follow-through.",
            "In low-vol uptrends, momentum continuation was reliable this cycle.",
        ],
    )

    first = memory_test_client.post("/api/consolidate", json={"scope": "test-idem"}).json()
    second = memory_test_client.post("/api/consolidate", json={"scope": "test-idem"}).json()

    assert first["consolidated_count"] >= 1
    assert second["consolidated_count"] == 0  # same bucket membership, skipped
