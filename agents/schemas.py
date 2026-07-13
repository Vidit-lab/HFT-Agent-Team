from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradeDecision(BaseModel):
    action: Action
    size: float = Field(ge=0, description="Units to buy/sell; 0 if holding")
    rationale: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    @model_validator(mode="after")
    def _hold_has_no_size(self):
        # "0 if holding" was only ever a description, so the model could return
        # {"action": "hold", "size": 200} -- which then got logged and rendered as
        # "HOLD 200.00". The action is authoritative; a held position has no size.
        if self.action == Action.HOLD and self.size != 0:
            self.size = 0.0
        return self


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


class ConsolidatedLesson(BaseModel):
    """One higher-order lesson the Consolidation Agent distilled from a group
    of raw lessons. `source_indices` are 0-based positions into the exact list
    of lessons handed to the agent in the prompt -- the loop maps them back to
    the underlying Supermemory document ids to record the connection edges."""

    meta_lesson: str = Field(min_length=1, max_length=800, description="The consolidated, higher-order rule")
    source_indices: list[int] = Field(description="Which prompted lessons (by index) this was distilled from")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ConsolidationOutput(BaseModel):
    """The Consolidation Agent's full output for one group of related lessons.
    Wrapped in an object (not a bare array) so json_object mode parses cleanly
    -- this is exactly the object-vs-array contract Supermemory's own server-
    side agent tripped on; we control it here."""

    consolidated: list[ConsolidatedLesson] = Field(description="One or more higher-order lessons")
