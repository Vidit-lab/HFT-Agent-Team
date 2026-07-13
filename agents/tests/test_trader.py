from __future__ import annotations

import pytest

from agents.schemas import Action, MarketAnalysis, Regime, ResearchThesis, RiskDecision, Stance, TradeDecision
from agents.trader import build_prompt, decide

from .conftest import make_bars, make_fake_client

_ANALYSIS = MarketAnalysis(regime=Regime.TRENDING_UP, summary="steady climb", confidence=0.8)
_BULL = ResearchThesis(stance=Stance.BULL, thesis="strong momentum", confidence=0.7)
_BEAR = ResearchThesis(stance=Stance.BEAR, thesis="overbought", confidence=0.3)
_RISK_APPROVED = RiskDecision(approved=True, max_position_size=10.0, reasoning="clear edge")


def test_build_prompt_includes_theses_and_risk_cap():
    prompt = build_prompt("AAPL", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, current_position_size=2.5)
    assert "strong momentum" in prompt
    assert "overbought" in prompt
    assert "max position size this cycle: 10.0" in prompt
    assert "Current position size in AAPL: 2.5" in prompt


def test_decide_parses_valid_response():
    client = make_fake_client('{"action": "buy", "size": 1.0, "rationale": "test", "confidence": 0.6}')
    decision, system_prompt, user_prompt = decide(
        "AAPL", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, client=client
    )

    assert isinstance(decision, TradeDecision)
    assert decision.action == Action.BUY
    assert decision.size == 1.0
    assert "AAPL" in user_prompt
    assert system_prompt


def test_decide_retries_on_invalid_json_then_succeeds():
    client = make_fake_client(
        "not valid json at all",
        '{"action": "hold", "size": 0, "rationale": "recovered", "confidence": 0.3}',
    )
    decision, _, _ = decide("AAPL", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, client=client, max_retries=2)
    assert decision.action == Action.HOLD
    assert decision.rationale == "recovered"


def test_decide_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        decide("AAPL", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, client=client, max_retries=2)


def test_decide_rejects_sell_exceeding_current_position():
    client = make_fake_client(
        '{"action": "sell", "size": 5.0, "rationale": "oversell", "confidence": 0.5}',
        '{"action": "sell", "size": 1.0, "rationale": "corrected", "confidence": 0.5}',
    )
    decision, _, _ = decide(
        "AAPL",
        make_bars(),
        _ANALYSIS,
        _BULL,
        _BEAR,
        _RISK_APPROVED,
        client=client,
        current_position_size=1.0,
        max_retries=1,
    )
    assert decision.size == 1.0
    assert decision.rationale == "corrected"


def test_decide_rejects_size_exceeding_risk_managers_cap():
    client = make_fake_client(
        '{"action": "buy", "size": 999.0, "rationale": "too greedy", "confidence": 0.5}',
        '{"action": "buy", "size": 10.0, "rationale": "within cap", "confidence": 0.5}',
    )
    decision, _, _ = decide(
        "AAPL", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, client=client, max_retries=1
    )
    assert decision.size == 10.0
    assert decision.rationale == "within cap"


@pytest.mark.live
def test_decide_with_real_llm_returns_well_formed_decision():
    decision, _, _ = decide("AAPL", make_bars(n=30), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED)

    assert isinstance(decision, TradeDecision)
    assert decision.action in Action
    assert decision.size >= 0
    assert decision.rationale
    assert 0.0 <= decision.confidence <= 1.0


def test_build_prompt_tells_a_flat_trader_that_sell_is_unavailable():
    """The crash this prevents: with a flat book and a strong bear thesis, the
    model proposes a short, the guard rejects it, and it burns every retry
    re-proposing the same illegal move -- taking the whole cycle down with it."""
    flat = build_prompt("BTC/USDT", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, 0.0)
    assert "SELL is NOT available" in flat

    held = build_prompt("BTC/USDT", make_bars(), _ANALYSIS, _BULL, _BEAR, _RISK_APPROVED, 2.5)
    assert "sell at most 2.5 units" in held
    assert "cannot go short" in held
