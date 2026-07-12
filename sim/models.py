"""Data models for the simulation engine -- the source of truth for money.

Unlike memory/ (fuzzy, self-organizing, semantic), everything here is exact:
SQLModel tables persisted to SQLite so a backtest run's ledger is durable and
queryable. `Signal` is the one non-table model -- it's a strategy's output,
consumed by the engine, never persisted on its own (it becomes a `Trade` once
filled).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Signal(SQLModel):
    """A strategy's trade intent for one bar. Not persisted directly."""

    timestamp: datetime
    symbol: str
    side: Side
    size: float


class Trade(SQLModel, table=True):
    """One fill. Append-only -- this is the ledger."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    timestamp: datetime
    symbol: str
    side: Side
    size: float
    price: float
    fee: float
    slippage_cost: float
    strategy: str
    realized_pnl: float | None = None
    regime_at_entry: str | None = None
    rationale_summary: str | None = None


class Position(SQLModel, table=True):
    """Current holdings per (run, symbol). Upserted as trades land, not append-only."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    symbol: str = Field(index=True)
    size: float
    avg_entry_price: float
    unrealized_pnl: float
    updated_at: datetime


class Portfolio(SQLModel, table=True):
    """Equity-curve snapshot, one row per processed bar. Append-only."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    timestamp: datetime
    cash: float
    equity: float
    total_pnl: float
    drawdown: float


class AgentDecisionLog(SQLModel, table=True):
    """Every agent decision, whether or not it became a trade -- a "hold" has
    no Trade row to attach reasoning to, so this is its own table. Captures
    the full multi-agent reasoning trail (one entry per graph node: Market
    Analyst, Researcher Bull/Bear, Risk Manager, Trader, Portfolio Manager)
    as JSON, plus the final decision and every memory id retrieved along
    the way -- the visible reasoning trail Phase 5's DoD calls for."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    timestamp: datetime
    symbol: str
    action: str
    regime: str | None = Field(default=None, index=True)
    trade_id: int | None = Field(default=None, foreign_key="trade.id")
    raw_decision_json: str
    reasoning_trail_json: str = "[]"
    retrieved_memory_ids: str = "[]"


class Reflection(SQLModel, table=True):
    """Phase 6: one row per trade the Reflection Agent has looked back on.
    Doubles as the idempotency ledger (a trade with no Reflection row is
    still eligible) and as the audit trail behind every LessonMemory --
    `outcome` is a deterministic calculation (sign of realized/forward
    return past a noise threshold), never something the LLM is asked to
    judge; `diagnosis`/`lesson_text`/`confidence` are its structured output."""

    id: int | None = Field(default=None, primary_key=True)
    trade_id: int = Field(foreign_key="trade.id", unique=True, index=True)
    run_id: str = Field(index=True)
    created_at: datetime
    outcome: str
    return_pct: float
    diagnosis: str
    lesson_text: str
    lesson_memory_id: str
    confidence: float


class Consolidation(SQLModel, table=True):
    """Phase 7: one row per higher-order lesson the Consolidation Agent distilled
    from a group of raw lessons sharing a (regime, outcome). This table is the
    source of truth for the consolidation edges the Memory Explorer graph draws
    (`consolidated_memory_id` -> each id in `source_memory_ids`), and its
    `group_signature` (a hash of the group's sorted source ids) is the
    idempotency key -- a group whose exact membership was already consolidated
    is skipped, so re-running the batch is safe."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime
    scope: str = Field(index=True, description="run_id this batch was scoped to, or 'all'")
    group_signature: str = Field(index=True, description="hash of the group's sorted source memory ids")
    regime: str
    outcome: str
    meta_lesson: str
    consolidated_memory_id: str
    source_memory_ids: str = Field(default="[]", description="JSON list of the Supermemory doc ids consolidated")
    source_count: int
    confidence: float


class BacktestResult(SQLModel, table=True):
    """Aggregate metrics for a completed run."""

    run_id: str = Field(primary_key=True)
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
    params_json: str = "{}"
