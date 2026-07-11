from __future__ import annotations

import pytest

from agents.portfolio_manager import MAX_POSITION_PCT_OF_EQUITY, _hard_cap_size, build_prompt, finalize
from agents.schemas import Action, TradeDecision

from .conftest import make_fake_client

_PROPOSAL = TradeDecision(action=Action.BUY, size=1000.0, rationale="Trader proposal", confidence=0.8)


def test_build_prompt_includes_trader_proposal_and_portfolio_state():
    prompt = build_prompt("AAPL", _PROPOSAL, current_position_size=0.0, current_price=100.0, cash=50_000.0, equity=100_000.0)
    assert "buy 1000.0" in prompt
    assert "Trader proposal" in prompt
    assert "Cash: 50000.00" in prompt


def test_hard_cap_size_caps_a_buy_to_pct_of_equity():
    capped = _hard_cap_size(Action.BUY, proposed_size=1000.0, current_price=100.0, equity=100_000.0)
    assert capped == pytest.approx((100_000.0 * MAX_POSITION_PCT_OF_EQUITY) / 100.0)


def test_hard_cap_size_leaves_sell_untouched():
    assert _hard_cap_size(Action.SELL, proposed_size=1000.0, current_price=100.0, equity=100_000.0) == 1000.0


def test_hard_cap_size_never_raises_a_smaller_proposal():
    capped = _hard_cap_size(Action.BUY, proposed_size=1.0, current_price=100.0, equity=100_000.0)
    assert capped == 1.0


def test_finalize_passes_through_a_hold_without_an_llm_call():
    hold = TradeDecision(action=Action.HOLD, size=0.0, rationale="nothing to do", confidence=0.5)

    class ExplodingClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    raise AssertionError("should not call the LLM for a pass-through hold")

    final, system_prompt, user_prompt = finalize(
        "AAPL", hold, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=ExplodingClient()
    )
    assert final is hold
    assert system_prompt == "" and user_prompt == ""


def test_finalize_confirms_the_proposal():
    client = make_fake_client('{"action": "buy", "size": 50.0, "rationale": "confirmed", "confidence": 0.8}')
    proposal = TradeDecision(action=Action.BUY, size=50.0, rationale="Trader proposal", confidence=0.8)

    final, _, _ = finalize("AAPL", proposal, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=client)
    assert final.size == 50.0


def test_finalize_shrinks_the_proposal():
    client = make_fake_client('{"action": "buy", "size": 20.0, "rationale": "shrunk for concentration", "confidence": 0.7}')
    proposal = TradeDecision(action=Action.BUY, size=50.0, rationale="Trader proposal", confidence=0.8)

    final, _, _ = finalize("AAPL", proposal, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=client)
    assert final.size == 20.0


def test_finalize_enforces_hard_cap_even_if_llm_confirms_oversized_proposal():
    # LLM "confirms" a 1000-unit buy at $100/share against $100k equity --
    # 25% cap means at most 250 units are allowed, regardless of what the LLM said.
    client = make_fake_client('{"action": "buy", "size": 1000.0, "rationale": "looks fine", "confidence": 0.8}')

    final, _, _ = finalize(
        "AAPL", _PROPOSAL, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=client
    )
    assert final.size == pytest.approx(250.0)


def test_finalize_retries_when_action_is_changed():
    client = make_fake_client(
        '{"action": "sell", "size": 10.0, "rationale": "flipped", "confidence": 0.5}',
        '{"action": "buy", "size": 10.0, "rationale": "corrected", "confidence": 0.5}',
    )
    final, _, _ = finalize(
        "AAPL", _PROPOSAL, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=client, max_retries=1
    )
    assert final.action == Action.BUY
    assert final.rationale == "corrected"


def test_finalize_retries_when_size_is_increased():
    client = make_fake_client(
        '{"action": "buy", "size": 5000.0, "rationale": "too greedy", "confidence": 0.5}',
        '{"action": "buy", "size": 100.0, "rationale": "corrected", "confidence": 0.5}',
    )
    final, _, _ = finalize(
        "AAPL", _PROPOSAL, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=client, max_retries=1
    )
    assert final.size == 100.0


def test_finalize_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        finalize(
            "AAPL", _PROPOSAL, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0, client=client, max_retries=2
        )


@pytest.mark.live
def test_finalize_with_real_llm_never_exceeds_proposed_size():
    final, _, _ = finalize("AAPL", _PROPOSAL, current_position_size=0.0, current_price=100.0, cash=100_000.0, equity=100_000.0)
    assert final.action == Action.BUY
    assert final.size <= _PROPOSAL.size
