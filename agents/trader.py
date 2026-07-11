"""Phase 5 node: Trader. Synthesizes the Market Analyst's regime call and
both Researchers' theses into a single buy/sell/hold decision, constrained
by the Risk Manager's size cap. Only reached when the Risk Manager approves
new exposure -- a veto short-circuits the graph straight to HOLD without
ever invoking this node. Not the final word: the Portfolio Manager reviews
this decision afterward and may shrink it further.
"""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from agents.formatting import format_market_state
from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import MarketAnalysis, ResearchThesis, RiskDecision, TradeDecision

SYSTEM_PROMPT = """You are the Trader for a paper-trading system. The Risk Manager has already \
approved new exposure this cycle and given you a maximum position size -- your job is to decide \
whether to buy, sell, or hold, and how much, by weighing the Bull and Bear theses against the \
market regime. Respond with ONLY a JSON object matching this schema, no other text:
{"action": "buy" | "sell" | "hold", "size": number (0 if holding), "rationale": string \
(1-3 sentences), "confidence": number between 0 and 1}

You may never propose a size greater than the Risk Manager's max_position_size. You may never sell \
more than the current position size. Be conservative: default to "hold" when the Bull and Bear \
theses are evenly matched or both low-confidence."""


def build_prompt(
    symbol: str,
    bars,
    market_analysis: MarketAnalysis,
    bull_thesis: ResearchThesis,
    bear_thesis: ResearchThesis,
    risk_decision: RiskDecision,
    current_position_size: float,
) -> str:
    return (
        f"{format_market_state(symbol, bars)}\n\n"
        f"Regime: {market_analysis.regime.value} (confidence {market_analysis.confidence:.2f}). "
        f"{market_analysis.summary}\n\n"
        f"Bull thesis (confidence {bull_thesis.confidence:.2f}): {bull_thesis.thesis}\n"
        f"Bear thesis (confidence {bear_thesis.confidence:.2f}): {bear_thesis.thesis}\n\n"
        f"Risk Manager's max position size this cycle: {risk_decision.max_position_size} "
        f"({risk_decision.reasoning})\n"
        f"Current position size in {symbol}: {current_position_size}\n"
        f"Decide: buy, sell, or hold."
    )


def decide(
    symbol: str,
    bars,
    market_analysis: MarketAnalysis,
    bull_thesis: ResearchThesis,
    bear_thesis: ResearchThesis,
    risk_decision: RiskDecision,
    *,
    current_position_size: float = 0.0,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[TradeDecision, str, str]:
    """Returns (decision, system_prompt, user_prompt)."""
    client = client or get_client()
    user_prompt = build_prompt(
        symbol, bars, market_analysis, bull_thesis, bear_thesis, risk_decision, current_position_size
    )

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            decision = TradeDecision.model_validate_json(raw)
            if decision.action.value == "sell" and decision.size > current_position_size:
                raise ValueError(
                    f"sell size {decision.size} exceeds current position size {current_position_size}"
                )
            if decision.action.value != "hold" and decision.size > risk_decision.max_position_size:
                raise ValueError(
                    f"size {decision.size} exceeds Risk Manager's max_position_size "
                    f"{risk_decision.max_position_size}"
                )
            return decision, SYSTEM_PROMPT, user_prompt
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid TradeDecision after {max_retries + 1} attempts: {last_error}")
