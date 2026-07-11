from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from sqlmodel import select

from agents.reflection_loop import run_reflection_batch
from sim.models import AgentDecisionLog, Reflection, Side, Trade

from .conftest import FakeMemoryClient, make_fake_client

_REFLECTION_RESPONSE = '{"diagnosis": "bull thesis correct", "lesson_text": "trust strong momentum", "confidence": 0.8}'


def _insert_trade(session, *, id=None, run_id="test-run", timestamp, realized_pnl, side=Side.BUY, price=100.0, size=10.0):
    trade = Trade(
        id=id,
        run_id=run_id,
        timestamp=timestamp,
        symbol="AAPL",
        side=side,
        size=size,
        price=price,
        fee=1.0,
        slippage_cost=0.5,
        strategy="agent_graph_v1",
        realized_pnl=realized_pnl,
        regime_at_entry="trending_up",
        rationale_summary="strong bull thesis",
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


def test_reflects_on_a_closed_trade_and_writes_a_lesson(db_session):
    trade = _insert_trade(db_session, timestamp=datetime(2026, 1, 1), realized_pnl=100.0)
    memory_client = FakeMemoryClient()
    client = make_fake_client(_REFLECTION_RESPONSE)

    results = run_reflection_batch(db_session, memory_client, llm_client=client, as_of="2026-01-02")

    assert len(results) == 1
    assert results[0].trade_id == trade.id
    assert results[0].outcome == "win"
    assert results[0].lesson_text == "trust strong momentum"

    rows = db_session.exec(select(Reflection)).all()
    assert len(rows) == 1
    assert rows[0].trade_id == trade.id
    assert rows[0].lesson_memory_id == "fake-lesson-id"


def test_skips_a_trade_that_already_has_a_reflection(db_session):
    trade = _insert_trade(db_session, timestamp=datetime(2026, 1, 1), realized_pnl=100.0)
    db_session.add(
        Reflection(
            trade_id=trade.id, run_id="test-run", created_at=datetime(2026, 1, 2), outcome="win",
            return_pct=10.0, diagnosis="already done", lesson_text="already done", lesson_memory_id="x", confidence=0.5,
        )
    )
    db_session.commit()

    results = run_reflection_batch(db_session, FakeMemoryClient(), llm_client=make_fake_client(), as_of="2026-01-02")
    assert results == []


def test_open_trade_not_yet_aged_is_not_eligible(db_session):
    _insert_trade(db_session, timestamp=datetime(2026, 1, 1), realized_pnl=None)
    results = run_reflection_batch(
        db_session, FakeMemoryClient(), llm_client=make_fake_client(), as_of="2026-01-02", lookback_days=5
    )
    assert results == []


def test_open_trade_aged_past_lookback_uses_forward_return(db_session, monkeypatch):
    trade = _insert_trade(db_session, timestamp=datetime(2026, 1, 1), realized_pnl=None, price=100.0)

    def fake_load_ohlcv(symbol, start, end, cache_dir="data"):
        return pd.DataFrame({"close": [100.0, 110.0]})

    monkeypatch.setattr("agents.reflection_loop.load_ohlcv", fake_load_ohlcv)

    results = run_reflection_batch(
        db_session, FakeMemoryClient(), llm_client=make_fake_client(_REFLECTION_RESPONSE), as_of="2026-01-10", lookback_days=5
    )

    assert len(results) == 1
    assert results[0].trade_id == trade.id
    assert results[0].outcome == "win"
    assert results[0].return_pct == pytest.approx(10.0)


def test_max_trades_caps_the_batch(db_session):
    for i in range(3):
        _insert_trade(db_session, timestamp=datetime(2026, 1, 1 + i), realized_pnl=100.0)

    client = make_fake_client(_REFLECTION_RESPONSE, _REFLECTION_RESPONSE)
    results = run_reflection_batch(db_session, FakeMemoryClient(), llm_client=client, as_of="2026-01-10", max_trades=2)
    assert len(results) == 2


def test_run_id_filters_scope(db_session):
    _insert_trade(db_session, run_id="run-a", timestamp=datetime(2026, 1, 1), realized_pnl=100.0)
    _insert_trade(db_session, run_id="run-b", timestamp=datetime(2026, 1, 1), realized_pnl=100.0)

    results = run_reflection_batch(
        db_session, FakeMemoryClient(), llm_client=make_fake_client(_REFLECTION_RESPONSE), as_of="2026-01-10", run_id="run-a"
    )
    assert len(results) == 1


def test_reasoning_trail_is_pulled_from_matching_agent_decision_log(db_session):
    trade = _insert_trade(db_session, timestamp=datetime(2026, 1, 1), realized_pnl=100.0)
    db_session.add(
        AgentDecisionLog(
            run_id="test-run", timestamp=datetime(2026, 1, 1), symbol="AAPL", action="buy",
            trade_id=trade.id, raw_decision_json="{}",
            reasoning_trail_json='[{"node": "market_analyst", "system_prompt": "s", "user_prompt": "u", "raw_output": "UNIQUE_MARKER_XYZ", "retrieved_memory_ids": ["mem-42"]}]',
        )
    )
    db_session.commit()

    client = make_fake_client(_REFLECTION_RESPONSE)
    results = run_reflection_batch(db_session, FakeMemoryClient(), llm_client=client, as_of="2026-01-02")

    assert len(results) == 1
    assert results[0].trade_id == trade.id
    sent_user_prompt = client.chat.completions.calls[0]["messages"][1]["content"]
    assert "UNIQUE_MARKER_XYZ" in sent_user_prompt
