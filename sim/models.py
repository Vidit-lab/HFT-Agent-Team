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
