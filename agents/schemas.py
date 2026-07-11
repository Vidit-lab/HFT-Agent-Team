from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradeDecision(BaseModel):
    action: Action
    size: float = Field(ge=0, description="Units to buy/sell; 0 if holding")
    rationale: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class Regime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    HIGH_VOLATILITY = "high_volatility"
    RANGE_BOUND = "range_bound"
    LOW_VOLATILITY = "low_volatility"


class MarketAnalysis(BaseModel):
    regime: Regime
    summary: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class Stance(str, Enum):
    BULL = "bull"
    BEAR = "bear"


class ResearchThesis(BaseModel):
    stance: Stance
    thesis: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class RiskDecision(BaseModel):
    approved: bool
    max_position_size: float = Field(ge=0.0, default=0.0, description="Ignored if not approved")
    reasoning: str = Field(min_length=1, max_length=1000)


class Reflection(BaseModel):
    """Phase 6's Reflection Agent output. Deliberately has no verdict field --
    whether a trade won or lost is a deterministic calculation done in code
    (see agents/reflection.py:compute_outcome), not something asked of the
    LLM. Its job is purely to diagnose why and generalize a lesson."""

    diagnosis: str = Field(min_length=1, max_length=500, description="Which node's reasoning was most responsible")
    lesson_text: str = Field(min_length=1, max_length=500, description="A generalizable, natural-language rule")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
