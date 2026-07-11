from __future__ import annotations

from datetime import datetime

import pytest

from agents.reflection import NOISE_THRESHOLD_PCT, build_prompt, compute_outcome, reflect
from agents.schemas import Reflection
from memory.schemas import Outcome
from sim.models import Side, Trade

from .conftest import make_fake_client

_TRAIL = [
    {"node": "market_analyst", "raw_output": '{"regime":"trending_up","confidence":0.8}'},
    {"node": "trader", "raw_output": '{"action":"buy","size":10.0,"confidence":0.7}'},
]


def _make_trade(*, realized_pnl: float | None, side: Side = Side.BUY, price: float = 100.0, size: float = 10.0) -> Trade:
    return Trade(
        id=1,
        run_id="test",
        timestamp=datetime(2026, 1, 1),
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


def test_compute_outcome_closed_trade_win():
    trade = _make_trade(realized_pnl=100.0, price=100.0, size=10.0)  # 10% of notional
    outcome, return_pct = compute_outcome(trade, current_price=None)
    assert outcome == Outcome.WIN
    assert return_pct == pytest.approx(10.0)


def test_compute_outcome_closed_trade_loss():
    trade = _make_trade(realized_pnl=-50.0, price=100.0, size=10.0)  # -5% of notional
    outcome, return_pct = compute_outcome(trade, current_price=None)
    assert outcome == Outcome.LOSS
    assert return_pct == pytest.approx(-5.0)


def test_compute_outcome_closed_trade_neutral_within_noise_threshold():
    trade = _make_trade(realized_pnl=1.0, price=100.0, size=10.0)  # 0.1% of notional
    outcome, return_pct = compute_outcome(trade, current_price=None)
    assert outcome == Outcome.NEUTRAL
    assert abs(return_pct) < NOISE_THRESHOLD_PCT


def test_compute_outcome_open_buy_uses_forward_return():
    trade = _make_trade(realized_pnl=None, side=Side.BUY, price=100.0)
    outcome, return_pct = compute_outcome(trade, current_price=110.0)
    assert outcome == Outcome.WIN
    assert return_pct == pytest.approx(10.0)


def test_compute_outcome_open_sell_inverts_sign():
    # a SELL "pays off" when price goes DOWN afterward
    trade = _make_trade(realized_pnl=None, side=Side.SELL, price=100.0)
    outcome, return_pct = compute_outcome(trade, current_price=90.0)
    assert outcome == Outcome.WIN
    assert return_pct == pytest.approx(10.0)


def test_compute_outcome_open_trade_requires_current_price():
    trade = _make_trade(realized_pnl=None)
    with pytest.raises(ValueError, match="current_price"):
        compute_outcome(trade, current_price=None)


def test_build_prompt_includes_trade_facts_and_reasoning_trail():
    trade = _make_trade(realized_pnl=100.0)
    prompt = build_prompt(trade, _TRAIL, Outcome.WIN, 10.0)
    assert "buy 10.0 AAPL" in prompt
    assert "trending_up" in prompt
    assert "strong bull thesis" in prompt
    assert "market_analyst" in prompt
    assert "win" in prompt


def test_build_prompt_handles_missing_reasoning_trail():
    trade = _make_trade(realized_pnl=100.0)
    prompt = build_prompt(trade, [], Outcome.WIN, 10.0)
    assert "No reasoning trail available" in prompt


def test_reflect_parses_valid_response():
    trade = _make_trade(realized_pnl=100.0)
    client = make_fake_client('{"diagnosis": "bull thesis was correct", "lesson_text": "trust strong bull theses", "confidence": 0.8}')
    reflection, system_prompt, user_prompt = reflect(trade, _TRAIL, Outcome.WIN, 10.0, client=client)

    assert isinstance(reflection, Reflection)
    assert reflection.diagnosis == "bull thesis was correct"
    assert "AAPL" in user_prompt
    assert system_prompt


def test_reflect_retries_on_invalid_json_then_succeeds():
    trade = _make_trade(realized_pnl=-50.0)
    client = make_fake_client(
        "not json",
        '{"diagnosis": "recovered", "lesson_text": "recovered lesson", "confidence": 0.5}',
    )
    reflection, _, _ = reflect(trade, _TRAIL, Outcome.LOSS, -5.0, client=client, max_retries=1)
    assert reflection.diagnosis == "recovered"


def test_reflect_raises_after_exhausting_retries():
    trade = _make_trade(realized_pnl=-50.0)
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        reflect(trade, _TRAIL, Outcome.LOSS, -5.0, client=client, max_retries=2)


@pytest.mark.live
def test_reflect_with_real_llm_returns_well_formed_reflection():
    trade = _make_trade(realized_pnl=100.0)
    reflection, _, _ = reflect(trade, _TRAIL, Outcome.WIN, 10.0)
    assert isinstance(reflection, Reflection)
    assert reflection.diagnosis
    assert reflection.lesson_text
    assert 0.0 <= reflection.confidence <= 1.0
