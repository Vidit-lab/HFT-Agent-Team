"""Phase 5 nodes: Researcher Bull and Researcher Bear. Same prompting
machinery, opposite mandate and oppositely-biased memory retrieval -- Bull
retrieves past winning trades, Bear retrieves past losing trades, so each
starts the debate from a different slice of the same long-term memory
store. Single-round: each produces exactly one thesis, no rebuttal.
"""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from agents.formatting import format_market_state, format_memories
from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import MarketAnalysis, ResearchThesis, Stance
from memory.client import SupermemoryClient, and_filters
from supermemory.types.search_memories_response import SearchMemoriesResponse

_MANDATE = {
    Stance.BULL: (
        "You are the Bull Researcher. Build the strongest reasonable case FOR buying or "
        "increasing exposure to this symbol right now. Do not fabricate optimism where none is "
        "warranted -- if the evidence is weak, say so and keep your confidence low."
    ),
    Stance.BEAR: (
        "You are the Bear Researcher. Build the strongest reasonable case FOR selling, reducing "
        "exposure, or staying out of this symbol right now. Do not fabricate pessimism where none "
        "is warranted -- if the evidence is weak, say so and keep your confidence low."
    ),
}


def _system_prompt(stance: Stance) -> str:
    return (
        f"{_MANDATE[stance]} Ground your thesis in the market regime and any retrieved past "
        "trades/lessons below. Respond with ONLY a JSON object matching this schema, no other text:\n"
        f'{{"stance": "{stance.value}", "thesis": string (2-4 sentences), "confidence": number '
        "between 0 and 1}"
    )


def build_prompt(
    symbol: str,
    bars,
    market_analysis: MarketAnalysis,
    retrieved_memories: list,
    stance: Stance,
) -> str:
    return (
        f"{format_market_state(symbol, bars)}\n\n"
        f"Market Analyst's regime classification: {market_analysis.regime.value} "
        f"(confidence {market_analysis.confidence:.2f}). {market_analysis.summary}\n\n"
        f"Relevant memory (past lessons and trades):\n{format_memories(retrieved_memories)}\n\n"
        f"Make your case."
    )


def retrieve_memories(
    memory_client: SupermemoryClient, symbol: str, stance: Stance, limit: int = 5
) -> SearchMemoriesResponse:
    """Bull is biased toward past wins, Bear toward past losses. Falls back to
    an unfiltered query when the outcome-filtered search comes up empty (a
    cold memory store shouldn't starve the debate of any context at all)."""
    outcome = "win" if stance == Stance.BULL else "loss"
    q = f"{'bullish' if stance == Stance.BULL else 'bearish'} lessons and past trades for {symbol}"
    result = memory_client.query_similar(q, filters=and_filters(asset=symbol, outcome=outcome), limit=limit)
    if not result.results:
        result = memory_client.query_similar(q, limit=limit)
    return result


def research(
    symbol: str,
    bars,
    market_analysis: MarketAnalysis,
    retrieved_memories: list,
    stance: Stance,
    *,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> tuple[ResearchThesis, str, str]:
    """Returns (thesis, system_prompt, user_prompt)."""
    client = client or get_client()
    system_prompt = _system_prompt(stance)
    user_prompt = build_prompt(symbol, bars, market_analysis, retrieved_memories, stance)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=system_prompt, user=user_prompt, model=model)
        try:
            thesis = ResearchThesis.model_validate_json(raw)
            if thesis.stance != stance:
                raise ValueError(f"expected stance {stance.value!r}, got {thesis.stance.value!r}")
            return thesis, system_prompt, user_prompt
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )

    raise RuntimeError(f"LLM failed to produce a valid ResearchThesis after {max_retries + 1} attempts: {last_error}")
