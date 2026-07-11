from __future__ import annotations

import pytest

from agents.market_analyst import _realized_volatility, build_prompt, classify
from agents.schemas import MarketAnalysis, Regime

from .conftest import make_bars, make_fake_client


def test_build_prompt_includes_symbol_and_volatility():
    prompt = build_prompt("AAPL", make_bars())
    assert "Symbol: AAPL" in prompt
    assert "realized volatility" in prompt
    assert "Classify the current regime." in prompt


def test_realized_volatility_is_zero_for_flat_prices():
    bars = make_bars(n=10)
    bars["close"] = 100.0
    assert _realized_volatility(bars) == 0.0


def test_classify_parses_valid_response():
    client = make_fake_client('{"regime": "trending_up", "summary": "steady climb", "confidence": 0.8}')
    analysis, system_prompt, user_prompt = classify("AAPL", make_bars(), client=client)

    assert isinstance(analysis, MarketAnalysis)
    assert analysis.regime == Regime.TRENDING_UP
    assert "AAPL" in user_prompt
    assert system_prompt


def test_classify_retries_on_invalid_json_then_succeeds():
    client = make_fake_client(
        "not valid json",
        '{"regime": "range_bound", "summary": "recovered", "confidence": 0.4}',
    )
    analysis, _, _ = classify("AAPL", make_bars(), client=client, max_retries=2)
    assert analysis.regime == Regime.RANGE_BOUND
    assert analysis.summary == "recovered"


def test_classify_retries_on_invalid_regime_value():
    client = make_fake_client(
        '{"regime": "sideways", "summary": "bad enum", "confidence": 0.4}',
        '{"regime": "low_volatility", "summary": "recovered", "confidence": 0.4}',
    )
    analysis, _, _ = classify("AAPL", make_bars(), client=client, max_retries=1)
    assert analysis.regime == Regime.LOW_VOLATILITY


def test_classify_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        classify("AAPL", make_bars(), client=client, max_retries=2)


@pytest.mark.live
def test_classify_with_real_llm_returns_well_formed_analysis():
    analysis, _, _ = classify("AAPL", make_bars(n=30))
    assert isinstance(analysis, MarketAnalysis)
    assert analysis.regime in Regime
    assert analysis.summary
    assert 0.0 <= analysis.confidence <= 1.0
