"""Phase 5 node: Market Analyst. First node in every cycle -- classifies the
current regime from recent price action alone (no memory, no debate). Its
output (`MarketAnalysis`) is fanned out to both Researchers and later used
to label the Trade row (`regime_at_entry`) and written back to memory as a
`RegimeSnapshotMemory` by the orchestrator, so future cycles can see how
regimes evolved over time.
"""

from __future__ import annotations

import json

import pandas as pd
from openai import OpenAI
from pydantic import ValidationError

from agents.formatting import format_market_state
from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import MarketAnalysis

SYSTEM_PROMPT = """You are a market regime classification analyst for a paper-trading system. \
Given recent daily closing prices and a realized-volatility estimate, classify the current \
regime. Respond with ONLY a JSON object matching this schema, no other text:
{"regime": "trending_up" | "trending_down" | "high_volatility" | "range_bound" | "low_volatility", \
"summary": string (1-3 sentences explaining the classification), "confidence": number between 0 and 1}

Guidance: "trending_up"/"trending_down" for a sustained directional move; "high_volatility" when \
day-to-day swings are large regardless of direction; "range_bound" when price oscillates without a \
clear trend; "low_volatility" when swings are unusually small. Pick the single best fit."""


def _realized_volatility(bars: pd.DataFrame, lookback: int = 20) -> float:
    """Annualized-ish realized volatility (stdev of daily returns, as a percent)
    over the lookback window -- a cheap, deterministic signal to ground the
    LLM's classification instead of asking it to eyeball a list of prices."""
    closes = bars["close"].tail(lookback + 1)
    returns = closes.pct_change().dropna()
    return float(returns.std() * 100) if len(returns) > 1 else 0.0


def build_prompt(symbol: str, bars: pd.DataFrame, lookback: int = 20) -> str:
    vol = _realized_volatility(bars, lookback)
    return (
        f"{format_market_state(symbol, bars, lookback)}\n\n"
        f"{lookback}-day realized volatility (stdev of daily returns): {vol:.2f}%\n"
        "Classify the current regime."
    )


def classify(
    symbol: str,
    bars: pd.DataFrame,
    *,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[MarketAnalysis, str, str]:
    """Returns (analysis, system_prompt, user_prompt)."""
    client = client or get_client()
    user_prompt = build_prompt(symbol, bars)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            analysis = MarketAnalysis.model_validate_json(raw)
            return analysis, SYSTEM_PROMPT, user_prompt
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid MarketAnalysis after {max_retries + 1} attempts: {last_error}")
