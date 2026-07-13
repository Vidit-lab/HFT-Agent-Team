from __future__ import annotations

import pytest

from agents.risk_manager import assess, build_prompt
from agents.schemas import MarketAnalysis, Regime, ResearchThesis, RiskDecision, Stance

from .conftest import make_fake_client

_ANALYSIS = MarketAnalysis(regime=Regime.TRENDING_UP, summary="steady climb", confidence=0.8)
_BULL = ResearchThesis(stance=Stance.BULL, thesis="strong momentum", confidence=0.7)
_BEAR = ResearchThesis(stance=Stance.BEAR, thesis="overbought", confidence=0.3)
# 100_000 equity * 25% / 315 => a ~79-unit ceiling, comfortably above every
# max_position_size these tests assert, so the clamp is a no-op for them.
_PRICE = 315.0


def test_build_prompt_includes_regime_and_both_theses():
    prompt = build_prompt("AAPL", _ANALYSIS, _BULL, _BEAR, current_position_size=0.0, equity=100_000.0, current_price=_PRICE)
    assert "trending_up" in prompt
    assert "strong momentum" in prompt
    assert "overbought" in prompt
    assert "100000.00" in prompt


def test_assess_parses_approved_response():
    client = make_fake_client('{"approved": true, "max_position_size": 50.0, "reasoning": "clear edge"}')
    decision, system_prompt, user_prompt = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, _PRICE, client=client)

    assert isinstance(decision, RiskDecision)
    assert decision.approved is True
    assert decision.max_position_size == 50.0
    assert "AAPL" in user_prompt
    assert system_prompt


def test_assess_parses_vetoed_response():
    client = make_fake_client('{"approved": false, "max_position_size": 0.0, "reasoning": "too risky"}')
    decision, _, _ = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, _PRICE, client=client)
    assert decision.approved is False


def test_assess_retries_on_invalid_json_then_succeeds():
    client = make_fake_client(
        "not json",
        '{"approved": true, "max_position_size": 10.0, "reasoning": "recovered"}',
    )
    decision, _, _ = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, _PRICE, client=client, max_retries=1)
    assert decision.reasoning == "recovered"


def test_assess_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, _PRICE, client=client, max_retries=2)


def test_assess_clamps_an_absurd_size_to_the_concentration_cap():
    """A model told to answer "in units" and given no price will happily return
    10000 -- fine for a stock, ~$630M of Bitcoin. The ceiling is enforced in code
    so no amount of confident reasoning can breach it."""
    client = make_fake_client('{"approved": true, "max_position_size": 10000.0, "reasoning": "load up"}')
    decision, _, _ = assess("BTC/USDT", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, 63_000.0, client=client)

    # 100_000 * 25% / 63_000 == 0.3968... units, not 10000.
    assert decision.max_position_size == pytest.approx((100_000.0 * 0.25) / 63_000.0)
    assert decision.max_position_size < 1.0


def test_build_prompt_gives_the_model_the_price_and_the_ceiling():
    prompt = build_prompt(
        "BTC/USDT", _ANALYSIS, _BULL, _BEAR, current_position_size=0.0, equity=100_000.0, current_price=63_000.0
    )
    assert "63000.00" in prompt  # it can no longer be blind to what a unit costs
    assert "0.396825" in prompt  # and it is told the ceiling outright


@pytest.mark.live
def test_assess_with_real_llm_returns_well_formed_decision():
    decision, _, _ = assess("AAPL", _ANALYSIS, _BULL, _BEAR, 0.0, 100_000.0, _PRICE)
    assert isinstance(decision, RiskDecision)
    assert isinstance(decision.approved, bool)
    assert decision.max_position_size >= 0
    assert decision.reasoning
