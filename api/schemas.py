"""API response contracts.

Deliberately separate from sim/models.py (the internal ledger schema): the
API's shape is a presentation concern and shouldn't change just because the
DB schema does, or vice versa. Models that wrap a DB row directly declare
`from_attributes=True` so route handlers can return SQLModel rows straight
through FastAPI's response_model validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    size: float
    avg_entry_price: float
    unrealized_pnl: float
    updated_at: datetime


class PortfolioSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    cash: float
    equity: float
    total_pnl: float
    drawdown: float


class PortfolioOut(BaseModel):
    run_id: str
    strategy: str
    symbol: str
    latest: PortfolioSnapshotOut
    positions: list[PositionOut]
    equity_curve: list[PortfolioSnapshotOut]


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    timestamp: datetime
    symbol: str
    side: str
    size: float
    price: float
    fee: float
    slippage_cost: float
    strategy: str
    realized_pnl: float | None
    regime_at_entry: str | None
    rationale_summary: str | None


class TradeListOut(BaseModel):
    run_id: str
    total: int
    limit: int
    offset: int
    trades: list[TradeOut]


class RegimeSnapshotOut(BaseModel):
    asset: str | None = None
    regime: str | None = None
    summary: str
    similarity: float | None = None


class RegimeOut(BaseModel):
    query: str
    snapshots: list[RegimeSnapshotOut]


class LessonOut(BaseModel):
    lesson_text: str
    strategy: str | None = None
    regime: str | None = None
    asset: str | None = None
    outcome: str | None = None
    similarity: float | None = None


class LessonsOut(BaseModel):
    query: str
    lessons: list[LessonOut]


class BacktestRequest(BaseModel):
    symbol: str = "AAPL"
    start: str = Field(description="YYYY-MM-DD")
    end: str = Field(description="YYYY-MM-DD")
    strategy: Literal["sma_crossover"] = "sma_crossover"
    initial_cash: float = 100_000.0
    short_window: int = 10
    long_window: int = 30
    fee_bps: float = 10.0
    slippage_bps: float = 5.0


class BacktestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    created_at: datetime
    strategy: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_cash: float
    final_equity: float
    total_pnl: float
    total_pnl_pct: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    num_trades: int


class RunCycleRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = Field(default="1h", description="Crypto bar size: 15m | 1h | 4h | 1d. Ignored for equities.")
    run_id: str = "paper-agent-v1"
    initial_cash: float = 100_000.0


class NodeTraceOut(BaseModel):
    node: str
    output: str


class RunCycleOut(BaseModel):
    run_id: str
    symbol: str
    action: str
    size: float
    rationale: str
    confidence: float
    regime: str
    regime_summary: str
    trade_id: int | None
    executed_price: float | None
    equity: float
    memories_considered: int
    memory_write_id: str | None
    reasoning_trail: list[NodeTraceOut]


class ReflectRequest(BaseModel):
    run_id: str | None = Field(default=None, description="Restrict to one run; defaults to all runs")
    max_trades: int = Field(default=10, ge=1, le=100)
    lookback_days: float = Field(
        default=5.0,
        ge=0,
        description="Days before an open trade is judged on forward return. Fractional is fine: 0.1667 == 4h, which is what 1h crypto bars want.",
    )
    as_of: str | None = Field(default=None, description="YYYY-MM-DD, defaults to today")


class ReflectionOut(BaseModel):
    trade_id: int
    symbol: str
    outcome: str
    return_pct: float
    diagnosis: str
    lesson_text: str
    lesson_memory_id: str
    confidence: float


class ReflectOut(BaseModel):
    reflected_count: int
    reflections: list[ReflectionOut]


class ConsolidateRequest(BaseModel):
    scope: str = Field(default="all", description="Label for this batch (e.g. a run_id); recorded on each row")
    min_group_size: int = Field(default=2, ge=2, description="Min raw lessons in a (regime, outcome) bucket to consolidate")
    max_groups: int = Field(default=20, ge=1, le=100)


class ConsolidationOut(BaseModel):
    consolidated_memory_id: str
    regime: str
    outcome: str
    meta_lesson: str
    source_memory_ids: list[str]
    source_count: int
    confidence: float


class ConsolidateOut(BaseModel):
    consolidated_count: int
    consolidations: list[ConsolidationOut]


# ── Memory Explorer (Phase 7 frontend) ────────────────────────────────────


class MemoryDocumentOut(BaseModel):
    id: str
    type: str
    title: str | None = None
    content: str | None = None
    status: str
    metadata: dict = Field(default_factory=dict)
    created_at: str | None = None


class MemoryDocumentsOut(BaseModel):
    total: int
    counts_by_type: dict[str, int]
    documents: list[MemoryDocumentOut]


class MemorySearchResultOut(BaseModel):
    id: str
    document_id: str
    type: str | None = None
    content: str
    similarity: float
    metadata: dict = Field(default_factory=dict)


class MemorySearchOut(BaseModel):
    query: str
    count: int
    results: list[MemorySearchResultOut]


class MemoryStatsOut(BaseModel):
    total_memories: int
    counts_by_type: dict[str, int]
    total_trades: int
    closed_trades: int
    win_rate: float
    total_reflections: int
    total_consolidations: int


class GraphNodeOut(BaseModel):
    id: str
    kind: str = Field(description="trade | lesson | consolidated")
    label: str
    regime: str | None = None
    outcome: str | None = None
    detail: str | None = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    kind: str = Field(description="reflected_from | consolidated_into | cited_by")


class MemoryGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class ReflectionRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_id: int
    run_id: str
    created_at: datetime
    outcome: str
    return_pct: float
    diagnosis: str
    lesson_text: str
    lesson_memory_id: str
    confidence: float


class ReflectionsOut(BaseModel):
    total: int
    reflections: list[ReflectionRowOut]


class ConsolidationRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    scope: str
    regime: str
    outcome: str
    meta_lesson: str
    consolidated_memory_id: str
    source_count: int
    confidence: float


class ConsolidationsOut(BaseModel):
    total: int
    consolidations: list[ConsolidationRowOut]


# ── Reflect & Consolidate workbench ──────────────────────────────────────


class PendingTradeOut(BaseModel):
    trade_id: int
    symbol: str
    side: str
    size: float
    price: float
    timestamp: datetime
    regime_at_entry: str | None = None
    realized_pnl: float | None = None
    days_held: int
    eligible: bool
    reason: str = Field(description="closed | aged | waiting")
    days_until_eligible: int = 0


class PendingReflectionOut(BaseModel):
    lookback_days: float
    eligible_count: int
    waiting_count: int
    trades: list[PendingTradeOut]


class PendingBucketOut(BaseModel):
    regime: str
    outcome: str
    lesson_count: int
    ready: bool
    already_consolidated: bool


class PendingConsolidationOut(BaseModel):
    min_group_size: int
    ready_count: int
    total_lessons: int
    buckets: list[PendingBucketOut]


class OHLCVBar(BaseModel):
    # UNIX seconds, not a date string. lightweight-charts reads a "YYYY-MM-DD"
    # as a *business day*, which would collapse 24 hourly bars onto one point.
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class TradeMarker(BaseModel):
    time: int
    price: float
    side: str
    size: float
    trade_id: int


class OHLCVOut(BaseModel):
    symbol: str
    timeframe: str
    exchange: str
    intraday: bool
    last_bar_time: int | None
    fetched_at: str
    stale: bool = Field(description="True when served from the offline snapshot rather than a live fetch")
    bars: list[OHLCVBar]
    markers: list[TradeMarker]


class QuoteOut(BaseModel):
    symbol: str
    last: float
    change_24h_pct: float
    quote_volume: float
    exchange: str
    fetched_at: str
    stale: bool


# ── Demo mode ─────────────────────────────────────────────────────────────


class DemoStatusOut(BaseModel):
    seeded: bool
    run_id: str
    symbol: str
    trades: int
    reflections: int
    consolidations: int


class DemoSeedOut(BaseModel):
    seeded: int = Field(description="Trades inserted by this call; 0 if it was already seeded")
    already_seeded: bool
    run_id: str
    symbol: str
    trades: int
