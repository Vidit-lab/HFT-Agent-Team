from __future__ import annotations

from agents.formatting import format_market_state, format_memories

from .conftest import make_bars, make_memory


def test_format_market_state_includes_symbol_and_prices():
    bars = make_bars()
    state = format_market_state("AAPL", bars, lookback=5)
    assert "Symbol: AAPL" in state
    assert "Current price:" in state
    assert "5-day change:" in state


def test_format_memories_empty_list():
    assert format_memories([]) == "No relevant past lessons or trades found."


def test_format_memories_includes_type_and_content():
    memories = [make_memory("Momentum entries worked well.", type="lesson")]
    formatted = format_memories(memories)
    assert "[lesson]" in formatted
    assert "Momentum entries worked well." in formatted
