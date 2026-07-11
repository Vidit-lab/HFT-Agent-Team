"""Phase 5 node: Risk Manager. Sets the risk envelope BEFORE sizing
(shift-left risk management), not a veto after the fact -- reads the regime
and both researchers' theses and either approves this cycle for new
exposure (with a hard cap on size) or vetoes it outright, short-circuiting
straight to a HOLD without ever invoking the Trader.
"""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import MarketAnalysis, ResearchThesis, RiskDecision

SYSTEM_PROMPT = """You are the Risk Manager for a paper-trading system. You do not decide what to \
trade -- you decide whether this cycle is even allowed to take new exposure, and if so, the \
maximum position size (in units of the symbol) the Trader may propose. Weigh the market regime, \
the Bull and Bear theses, and the current position size. Veto (approved=false) when the regime is \
high_volatility with no clear directional edge, when both theses are weak/low-confidence, or when \
the current position is already large relative to a prudent single-symbol allocation. Respond with \
ONLY a JSON object matching this schema, no other text:
{"approved": true | false, "max_position_size": number (>=0, units of the symbol; ignored if not \
approved), "reasoning": string (1-3 sentences)}"""


def build_prompt(
    symbol: str,
    market_analysis: MarketAnalysis,
    bull_thesis: ResearchThesis,
    bear_thesis: ResearchThesis,
    current_position_size: float,
    equity: float,
) -> str:
    return (
        f"Symbol: {symbol}\n"
        f"Regime: {market_analysis.regime.value} (confidence {market_analysis.confidence:.2f}). "
        f"{market_analysis.summary}\n\n"
        f"Bull thesis (confidence {bull_thesis.confidence:.2f}): {bull_thesis.thesis}\n"
        f"Bear thesis (confidence {bear_thesis.confidence:.2f}): {bear_thesis.thesis}\n\n"
        f"Current position size in {symbol}: {current_position_size}\n"
        f"Current portfolio equity: {equity:.2f}\n"
        "Decide: approve or veto new exposure this cycle, and if approved, the max position size."
    )


def assess(
    symbol: str,
    market_analysis: MarketAnalysis,
    bull_thesis: ResearchThesis,
    bear_thesis: ResearchThesis,
    current_position_size: float,
    equity: float,
    *,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[RiskDecision, str, str]:
    """Returns (decision, system_prompt, user_prompt)."""
    client = client or get_client()
    user_prompt = build_prompt(symbol, market_analysis, bull_thesis, bear_thesis, current_position_size, equity)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            decision = RiskDecision.model_validate_json(raw)
            return decision, SYSTEM_PROMPT, user_prompt
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid RiskDecision after {max_retries + 1} attempts: {last_error}")
