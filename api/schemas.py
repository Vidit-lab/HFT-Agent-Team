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
    symbol: str = "AAPL"
    run_id: str = "paper-agent-v1"
    initial_cash: float = 100_000.0
    as_of: str | None = Field(default=None, description="YYYY-MM-DD, defaults to today")


class RunCycleOut(BaseModel):
    run_id: str
    symbol: str
    action: str
    size: float
    rationale: str
    confidence: float
    trade_id: int | None
    executed_price: float | None
    equity: float
    memories_considered: int
    memory_write_id: str | None
