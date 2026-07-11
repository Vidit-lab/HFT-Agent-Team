"""The single Phase 4 agent: one LLM call that looks at recent price action
plus retrieved long-term memories and decides buy/sell/hold. No debate, no
risk manager, no reflection -- that's Phase 5/6. This is the whole brain.
"""

from __future__ import annotations

import json

import pandas as pd
from openai import OpenAI
from pydantic import ValidationError

from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import TradeDecision

SYSTEM_PROMPT = """You are a disciplined trading analyst for a paper-trading system. \
You decide whether to buy, sell, or hold a single position based on recent price action \
and lessons retrieved from past trades. Respond with ONLY a JSON object matching this \
schema, no other text:
{"action": "buy" | "sell" | "hold", "size": number (0 if holding), "rationale": string \
(1-3 sentences), "confidence": number between 0 and 1}

Prefer strategies that worked in similar past situations, described in the retrieved \
memory below. Avoid repeating patterns from memories describing losses. Be conservative: \
default to "hold" unless there is a clear signal. You may never sell more than the \
current position size."""


def _format_market_state(symbol: str, bars: pd.DataFrame, lookback: int = 20) -> str:
    recent = bars.tail(lookback)
    lines = [f"{row.timestamp.date()}: close={row.close:.2f}" for row in recent.itertuples(index=False)]
    latest_close = bars.iloc[-1].close
    first_close = recent.iloc[0].close
    pct_change = (latest_close - first_close) / first_close * 100
    return (
        f"Symbol: {symbol}\n"
        f"Last {len(recent)} trading days (close price):\n" + "\n".join(lines) + "\n"
        f"Current price: {latest_close:.2f}\n"
        f"{len(recent)}-day change: {pct_change:+.2f}%"
    )


def _format_memories(memories: list) -> str:
    if not memories:
        return "No relevant past lessons or trades found."
    lines = []
    for m in memories:
        metadata = m.metadata or {}
        lines.append(f"- [{metadata.get('type', 'memory')}] {m.chunk}")
    return "\n".join(lines)


def build_prompt(symbol: str, bars: pd.DataFrame, retrieved_memories: list, current_position_size: float) -> str:
    return (
        f"{_format_market_state(symbol, bars)}\n\n"
        f"Relevant memory (past lessons and trades):\n{_format_memories(retrieved_memories)}\n\n"
        f"Current position size in {symbol}: {current_position_size}\n"
        f"Decide: buy, sell, or hold."
    )


def decide(
    symbol: str,
    bars: pd.DataFrame,
    retrieved_memories: list,
    *,
    current_position_size: float = 0.0,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[TradeDecision, str, str]:
    """Returns (decision, system_prompt, user_prompt). Prompts are returned
    alongside the decision so the caller can log exactly what the agent saw."""
    client = client or get_client()
    user_prompt = build_prompt(symbol, bars, retrieved_memories, current_position_size)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            decision = TradeDecision.model_validate_json(raw)
            if decision.action.value == "sell" and decision.size > current_position_size:
                raise ValueError(
                    f"sell size {decision.size} exceeds current position size {current_position_size}"
                )
            return decision, SYSTEM_PROMPT, user_prompt
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid TradeDecision after {max_retries + 1} attempts: {last_error}")
