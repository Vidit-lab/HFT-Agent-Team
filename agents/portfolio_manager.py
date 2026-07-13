"""Phase 5 node: Portfolio Manager. Final arbiter -- reviews the Trader's
proposed decision against overall portfolio exposure (equity, cash,
existing position) and either confirms it or shrinks the size further. It
may never increase the Trader's proposed size or flip its action; the worst
case is a smaller trade or an effective hold. A hard concentration cap is
enforced in code regardless of what the LLM says, the same defense-in-depth
pattern already used for the sell-exceeds-position check elsewhere.

When the Trader already decided to hold, there is nothing to arbitrate --
this node passes it through without an LLM call.
"""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from agents.limits import MAX_POSITION_PCT_OF_EQUITY, max_affordable_units
from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import Action, TradeDecision

__all__ = ["MAX_POSITION_PCT_OF_EQUITY", "build_prompt", "finalize"]

SYSTEM_PROMPT = """You are the Portfolio Manager for a paper-trading system -- the final sign-off \
before a trade executes. The Trader has proposed a decision; your job is to confirm it or shrink \
its size if it looks imprudent relative to overall portfolio equity, cash, and existing exposure. \
You may NEVER increase the size or change the action. Respond with ONLY a JSON object matching \
this schema, no other text:
{"action": "buy" | "sell" | "hold", "size": number (<= the Trader's proposed size), "rationale": \
string (1-3 sentences), "confidence": number between 0 and 1}"""


def build_prompt(
    symbol: str,
    trade_decision: TradeDecision,
    current_position_size: float,
    current_price: float,
    cash: float,
    equity: float,
) -> str:
    return (
        f"Symbol: {symbol}\n"
        f"Trader's proposal: {trade_decision.action.value} {trade_decision.size} "
        f"(confidence {trade_decision.confidence:.2f}). Rationale: {trade_decision.rationale}\n\n"
        f"Current position size in {symbol}: {current_position_size}\n"
        f"Current price: {current_price:.2f}\n"
        f"Cash: {cash:.2f}\n"
        f"Portfolio equity: {equity:.2f}\n"
        f"Review the proposal and confirm or shrink it."
    )


def _hard_cap_size(action: Action, proposed_size: float, current_price: float, equity: float) -> float:
    """A BUY may never push this single symbol's exposure past
    MAX_POSITION_PCT_OF_EQUITY of total equity, independent of anything the
    LLM decides. SELL/HOLD are left alone -- reducing exposure is never the
    concentration risk this guards against."""
    if action != Action.BUY or current_price <= 0:
        return float(proposed_size)
    return float(min(proposed_size, max_affordable_units(equity, current_price)))


def finalize(
    symbol: str,
    trade_decision: TradeDecision,
    current_position_size: float,
    current_price: float,
    cash: float,
    equity: float,
    *,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[TradeDecision, str, str]:
    """Returns (final_decision, system_prompt, user_prompt). system_prompt/
    user_prompt are empty strings on the no-op hold pass-through."""
    if trade_decision.action == Action.HOLD:
        return trade_decision, "", ""

    client = client or get_client()
    user_prompt = build_prompt(symbol, trade_decision, current_position_size, current_price, cash, equity)
    hard_cap = _hard_cap_size(trade_decision.action, trade_decision.size, current_price, equity)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            final = TradeDecision.model_validate_json(raw)
            if final.action != trade_decision.action:
                raise ValueError(
                    f"action changed from {trade_decision.action.value!r} to {final.action.value!r}"
                )
            if final.size > trade_decision.size:
                raise ValueError(f"size {final.size} exceeds the Trader's proposed size {trade_decision.size}")
            final.size = min(final.size, hard_cap)
            return final, SYSTEM_PROMPT, user_prompt
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid TradeDecision after {max_retries + 1} attempts: {last_error}")
