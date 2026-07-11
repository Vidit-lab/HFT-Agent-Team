from __future__ import annotations

import pytest

from agents.risk_manager import assess, build_prompt
from agents.schemas import MarketAnalysis, Regime, ResearchThesis, RiskDecision, Stance

from .conftest import make_fake_client

_ANALYSIS = MarketAnalysis(regime=Regime.TRENDING_UP, summary="steady climb", confidence=0.8)
_BULL = ResearchThesis(stance=Stance.BULL, thesis="strong momentum", confidence=0.7)
_BEAR = ResearchThesis(stance=Stance.BEAR, thesis="overbought", confidence=0.3)


def test_build_prompt_includes_regime_and_both_theses():
    prompt = build_prompt("AAPL", _ANALYSIS, _BULL, _BEAR, current_position_size=0.0, equity=100_000.0)
    assert "trending_up" in prompt
    assert "strong momentum" in prompt
    assert "overbought" in prompt
    assert "100000.00" in prompt


def test_assess_parses_approved_response():
    client = make_fake_client('{"approved": true, "max_position_size": 50.0, "reasoning": "clear edge"}')
    decision, system_prompt, user_prompt = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, client=client)

    assert isinstance(decision, RiskDecision)
    assert decision.approved is True
    assert decision.max_position_size == 50.0
    assert "AAPL" in user_prompt
    assert system_prompt


def test_assess_parses_vetoed_response():
    client = make_fake_client('{"approved": false, "max_position_size": 0.0, "reasoning": "too risky"}')
    decision, _, _ = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, client=client)
    assert decision.approved is False


def test_assess_retries_on_invalid_json_then_succeeds():
    client = make_fake_client(
        "not json",
        '{"approved": true, "max_position_size": 10.0, "reasoning": "recovered"}',
    )
    decision, _, _ = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, client=client, max_retries=1)
    assert decision.reasoning == "recovered"


def test_assess_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, client=client, max_retries=2)


@pytest.mark.live
def test_assess_with_real_llm_returns_well_formed_decision():
    decision, _, _ = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0)
    assert isinstance(decision, RiskDecision)
    assert isinstance(decision.approved, bool)
    assert decision.max_position_size >= 0
    assert decision.reasoning
