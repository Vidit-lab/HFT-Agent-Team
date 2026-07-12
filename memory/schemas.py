"""Typed payloads for everything written to Supermemory.

Each record knows how to render itself as (a) a natural-language `content`
string -- so the engine's extraction/embedding step has something meaningful
to work with -- and (b) a flat `metadata` dict used for filtering at query
time. See plan.md section 3 for the schema rationale: `containerTag` is the
isolation scope, `metadata` carries the queryable dimensions (type/strategy/
regime/asset/outcome).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Union

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    TRADE = "trade"
    LESSON = "lesson"
    CONSOLIDATED_LESSON = "consolidated_lesson"
    REGIME_SNAPSHOT = "regime_snapshot"
    EVENT = "event"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Outcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    NEUTRAL = "neutral"


MetadataValue = Union[str, float, bool]


class MemoryRecord(BaseModel):
    """Base class for anything written to Supermemory."""

    type: MemoryType

    def to_content(self) -> str:
        raise NotImplementedError

    def to_metadata(self) -> dict[str, MetadataValue]:
        raise NotImplementedError


class TradeMemory(MemoryRecord):
    type: MemoryType = MemoryType.TRADE

    trade_id: str
    timestamp: datetime
    symbol: str
    side: Side
    size: float
    price: float
    strategy: str
    regime: str
    outcome: Outcome
    pnl: float
    rationale: str = Field(description="Why the agent(s) made this decision")

    def to_content(self) -> str:
        return (
            f"Trade {self.trade_id}: {self.side.value} {self.size} {self.symbol} "
            f"@ {self.price} using strategy '{self.strategy}' during a "
            f"'{self.regime}' regime. Outcome: {self.outcome.value} (PnL: {self.pnl}). "
            f"Rationale: {self.rationale}"
        )

    def to_metadata(self) -> dict[str, MetadataValue]:
        return {
            "type": self.type.value,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "asset": self.symbol,
            "side": self.side.value,
            "strategy": self.strategy,
            "regime": self.regime,
            "outcome": self.outcome.value,
            "pnl": self.pnl,
        }


class LessonMemory(MemoryRecord):
    type: MemoryType = MemoryType.LESSON

    strategy: str
    regime: str
    lesson_text: str = Field(description="The generalizable, natural-language rule learned")
    asset: str | None = None
    outcome: Outcome | None = None
    source_trade_id: str | None = None

    def to_content(self) -> str:
        return self.lesson_text

    def to_metadata(self) -> dict[str, MetadataValue]:
        metadata: dict[str, MetadataValue] = {
            "type": self.type.value,
            "strategy": self.strategy,
            "regime": self.regime,
        }
        if self.asset is not None:
            metadata["asset"] = self.asset
        if self.outcome is not None:
            metadata["outcome"] = self.outcome.value
        if self.source_trade_id is not None:
            metadata["source_trade_id"] = self.source_trade_id
        return metadata


class ConsolidatedLessonMemory(MemoryRecord):
    """A higher-order lesson distilled by our own Consolidation Agent from a
    group of raw LessonMemory documents sharing a (regime, outcome). Written
    back into Supermemory as a first-class, retrievable document -- this is how
    consolidation lands in a store that works, sidestepping the self-hosted
    binary's own (free-tier-blocked) consolidation engine. The source document
    ids are the connection edges; they live in sim.models.Consolidation (the
    source of truth for the Memory Explorer graph), with just a count carried in
    metadata here to keep metadata values scalar."""

    type: MemoryType = MemoryType.CONSOLIDATED_LESSON

    strategy: str
    regime: str
    meta_lesson: str = Field(description="The consolidated, higher-order rule")
    outcome: Outcome | None = None
    asset: str | None = None
    source_count: int = Field(ge=1, description="How many raw lessons this consolidates")
    confidence: float = 0.5

    def to_content(self) -> str:
        return self.meta_lesson

    def to_metadata(self) -> dict[str, MetadataValue]:
        metadata: dict[str, MetadataValue] = {
            "type": self.type.value,
            "strategy": self.strategy,
            "regime": self.regime,
            "source_count": self.source_count,
            "confidence": self.confidence,
        }
        if self.outcome is not None:
            metadata["outcome"] = self.outcome.value
        if self.asset is not None:
            metadata["asset"] = self.asset
        return metadata


class RegimeSnapshotMemory(MemoryRecord):
    type: MemoryType = MemoryType.REGIME_SNAPSHOT

    timestamp: datetime
    regime: str
    asset: str
    summary: str = Field(description="Narrative description of the indicators behind this classification")

    def to_content(self) -> str:
        return (
            f"Regime snapshot for {self.asset} at {self.timestamp.isoformat()}: "
            f"classified as '{self.regime}'. {self.summary}"
        )

    def to_metadata(self) -> dict[str, MetadataValue]:
        return {
            "type": self.type.value,
            "regime": self.regime,
            "asset": self.asset,
        }


class EventMemory(MemoryRecord):
    type: MemoryType = MemoryType.EVENT

    timestamp: datetime
    event_type: str
    description: str
    asset: str | None = None

    def to_content(self) -> str:
        return f"[{self.event_type}] {self.description}"

    def to_metadata(self) -> dict[str, MetadataValue]:
        metadata: dict[str, MetadataValue] = {
            "type": self.type.value,
            "event_type": self.event_type,
        }
        if self.asset is not None:
            metadata["asset"] = self.asset
        return metadata
