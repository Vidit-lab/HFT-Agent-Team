from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from agents.schemas import Action, TradeDecision
from agents.trader import _format_market_state, _format_memories, build_prompt, decide

from .conftest import make_bars, make_fake_client


def _memory(chunk: str, **metadata) -> SimpleNamespace:
    return SimpleNamespace(chunk=chunk, metadata=metadata)


def test_format_market_state_includes_symbol_and_prices():
    bars = make_bars()
    state = _format_market_state("AAPL", bars, lookback=5)
    assert "Symbol: AAPL" in state
    assert "Current price:" in state
    assert "5-day change:" in state


def test_format_memories_empty_list():
    assert _format_memories([]) == "No relevant past lessons or trades found."


def test_format_memories_includes_type_and_content():
    memories = [_memory("Momentum entries worked well.", type="lesson")]
    formatted = _format_memories(memories)
    assert "[lesson]" in formatted
    assert "Momentum entries worked well." in formatted


def test_build_prompt_includes_position_size():
    bars = make_bars()
    prompt = build_prompt("AAPL", bars, [], current_position_size=2.5)
    assert "Current position size in AAPL: 2.5" in prompt


def test_decide_parses_valid_response():
    client = make_fake_client('{"action": "buy", "size": 1.0, "rationale": "test", "confidence": 0.6}')
    decision, system_prompt, user_prompt = decide("AAPL", make_bars(), [], client=client)

    assert decision.action == Action.BUY
    assert decision.size == 1.0
    assert "AAPL" in user_prompt
    assert system_prompt  # non-empty


def test_decide_retries_on_invalid_json_then_succeeds():
    client = make_fake_client(
        "not valid json at all",
        '{"action": "hold", "size": 0, "rationale": "recovered", "confidence": 0.3}',
    )
    decision, _, _ = decide("AAPL", make_bars(), [], client=client, max_retries=2)
    assert decision.action == Action.HOLD
    assert decision.rationale == "recovered"


def test_decide_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        decide("AAPL", make_bars(), [], client=client, max_retries=2)


def test_decide_rejects_sell_exceeding_current_position():
    # first response oversells; second response (after retry feedback) is valid
    client = make_fake_client(
        '{"action": "sell", "size": 5.0, "rationale": "oversell", "confidence": 0.5}',
        '{"action": "sell", "size": 1.0, "rationale": "corrected", "confidence": 0.5}',
    )
    decision, _, _ = decide("AAPL", make_bars(), [], client=client, current_position_size=1.0, max_retries=1)
    assert decision.size == 1.0
    assert decision.rationale == "corrected"


@pytest.fixture(autouse=True)
def _skip_live_without_key(request):
    if "live" in request.keywords and not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping live LLM test")


@pytest.mark.live
def test_decide_with_real_llm_returns_well_formed_decision():
    bars = make_bars(n=30)
    memories = [_memory("Momentum entries after green candles worked well.", type="lesson", strategy="momentum")]

    decision, _, _ = decide("AAPL", bars, memories, current_position_size=0.0)

    assert isinstance(decision, TradeDecision)
    assert decision.action in Action
    assert decision.size >= 0
    assert decision.rationale
    assert 0.0 <= decision.confidence <= 1.0
