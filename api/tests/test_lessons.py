"""Integration tests against the live local Supermemory server, skipped
(via the memory_test_client fixture) if it isn't reachable.
"""

from __future__ import annotations

import time

from memory.schemas import LessonMemory, Outcome


def test_lessons_empty_when_nothing_written(memory_test_client):
    response = memory_test_client.get("/api/lessons")
    assert response.status_code == 200
    assert response.json()["lessons"] == []


def test_lessons_returns_written_lesson_filtered_by_strategy(memory_test_client):
    memory_test_client.memory_client.write_lesson(
        LessonMemory(
            strategy="momentum",
            regime="high_vol_bull",
            asset="ETH",
            outcome=Outcome.WIN,
            lesson_text="Momentum entries after consecutive green candles had strong follow-through.",
        )
    )
    time.sleep(8)  # async chunk embedding

    response = memory_test_client.get(
        "/api/lessons", params={"q": "momentum entry performance", "strategy": "momentum"}
    )
    assert response.status_code == 200
    lessons = response.json()["lessons"]
    assert len(lessons) >= 1
    assert lessons[0]["strategy"] == "momentum"
    assert lessons[0]["asset"] == "ETH"
