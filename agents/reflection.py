"""Phase 6: the Reflection Agent -- runs after a trade's outcome is knowable
(closed, or aged past a lookback window), diagnoses why the debate/sizing
did or didn't work out, and generalizes a lesson. Deliberately decoupled
from run_cycle's hot path; see agents/reflection_loop.py for the batch
process that finds eligible trades and drives this per-trade.

`compute_outcome` is the load-bearing design decision here: WIN/LOSS/NEUTRAL
is a deterministic calculation from realized or forward return, never
something the LLM is asked to judge -- the same defense-in-depth instinct
already used for Portfolio Manager's hard concentration cap. The LLM's job
is purely to explain why and write a generalizable rule.
"""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import Reflection
from memory.schemas import Outcome
from sim.models import Side, Trade

NOISE_THRESHOLD_PCT = 0.5

SYSTEM_PROMPT = """You are the Reflection Agent for a paper-trading system. A trade's outcome is \
already known and computed for you (win/loss/neutral, with a return percentage) -- your job is NOT \
to judge whether it worked, only to diagnose WHY, using the original multi-agent reasoning trail \
(what the Market Analyst called the regime, what the Bull and Bear argued, what the Risk Manager \
and Trader decided). Pin the diagnosis to a specific cause where you can: a regime misread, a \
debate thesis that was right but got underweighted (or wrong but got overweighted), sizing that \
amplified or muted the result, or good reasoning undone by timing. Then write ONE crisp, \
generalizable lesson that would help a future decision in a similar regime -- not a restatement of \
this specific trade. Respond with ONLY a JSON object matching this schema, no other text:
{"diagnosis": string (1-2 sentences, name the responsible node/cause), "lesson_text": string \
(1-2 sentences, generalizable), "confidence": number between 0 and 1}"""


def compute_outcome(
    trade: Trade, current_price: float | None, *, noise_threshold_pct: float = NOISE_THRESHOLD_PCT
) -> tuple[Outcome, float]:
    """Returns (outcome, return_pct). Uses realized PnL (relative to the
    trade's notional value) for a closed trade; otherwise the forward return
    from entry to `current_price`, sign-adjusted by side so a positive
    number always means "the bet paid off," regardless of BUY vs SELL."""
    if trade.realized_pnl is not None:
        notional = trade.price * trade.size
        return_pct = (trade.realized_pnl / notional) * 100 if notional else 0.0
    else:
        if current_price is None:
            raise ValueError("current_price is required to evaluate a still-open trade")
        raw_return_pct = (current_price - trade.price) / trade.price * 100
        return_pct = raw_return_pct if trade.side == Side.BUY else -raw_return_pct

    if return_pct > noise_threshold_pct:
        outcome = Outcome.WIN
    elif return_pct < -noise_threshold_pct:
        outcome = Outcome.LOSS
    else:
        outcome = Outcome.NEUTRAL
    return outcome, return_pct


def _format_reasoning_trail(reasoning_trail: list[dict]) -> str:
    if not reasoning_trail:
        return "No reasoning trail available for this trade."
    lines = [f"- {entry['node']}: {entry['raw_output']}" for entry in reasoning_trail]
    return "\n".join(lines)


def build_prompt(trade: Trade, reasoning_trail: list[dict], outcome: Outcome, return_pct: float) -> str:
    is_closed = trade.realized_pnl is not None
    outcome_line = (
        f"Realized outcome: {outcome.value} ({return_pct:+.2f}% of notional)"
        if is_closed
        else f"Unrealized outcome (still open, evaluated forward): {outcome.value} ({return_pct:+.2f}%)"
    )
    return (
        f"Trade: {trade.side.value} {trade.size} {trade.symbol} @ {trade.price:.2f}, "
        f"regime at entry: {trade.regime_at_entry or 'unknown'}\n"
        f"Original rationale: {trade.rationale_summary or 'none recorded'}\n"
        f"{outcome_line}\n\n"
        f"Full reasoning trail from that cycle:\n{_format_reasoning_trail(reasoning_trail)}\n\n"
        "Diagnose why, and write a generalizable lesson."
    )


def reflect(
    trade: Trade,
    reasoning_trail: list[dict],
    outcome: Outcome,
    return_pct: float,
    *,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[Reflection, str, str]:
    """Returns (reflection, system_prompt, user_prompt)."""
    client = client or get_client()
    user_prompt = build_prompt(trade, reasoning_trail, outcome, return_pct)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            return Reflection.model_validate_json(raw), SYSTEM_PROMPT, user_prompt
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid Reflection after {max_retries + 1} attempts: {last_error}")
