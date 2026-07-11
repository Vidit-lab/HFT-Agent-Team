"""Shared state that flows through the Phase 5 LangGraph. `reasoning_trail`
uses an `operator.add` reducer because Bull and Bear both write to it in the
same parallel superstep -- without a reducer LangGraph would treat that as
a conflicting write and raise, since a plain dict key can only have one
writer per step. Every other field has exactly one writer, so the default
last-write-wins behavior is fine.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import pandas as pd

from agents.schemas import MarketAnalysis, ResearchThesis, RiskDecision, TradeDecision


class NodeTrace(TypedDict):
    node: str
    system_prompt: str
    user_prompt: str
    raw_output: str
    retrieved_memory_ids: list[str]


class AgentState(TypedDict, total=False):
    symbol: str
    bars: pd.DataFrame
    current_position_size: float
    current_price: float
    cash: float
    equity: float
    market_analysis: MarketAnalysis
    bull_thesis: ResearchThesis
    bear_thesis: ResearchThesis
    risk_decision: RiskDecision
    trade_decision: TradeDecision
    reasoning_trail: Annotated[list[NodeTrace], operator.add]
