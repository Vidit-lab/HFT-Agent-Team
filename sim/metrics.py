"""Backtest metrics: max drawdown, Sharpe ratio, win rate, and the aggregate result.

Pure functions of (trades, equity_curve) only -- no wall-clock, no randomness -- so
the same trade/equity sequence always produces the same metrics. `run_id` and
`created_at` are run-instance bookkeeping, not trading outputs, so
compute_backtest_result takes them as explicit caller-supplied arguments rather
than generating them internally.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime

from sim.models import BacktestResult, Trade


def max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return worst


def sharpe_ratio(equity_curve: list[float], *, periods_per_year: int = 252, risk_free_rate: float = 0.0) -> float:
    if len(equity_curve) < 2:
        return 0.0
    returns = [
        (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] != 0
    ]
    if len(returns) < 2:
        return 0.0
    mean_return = statistics.mean(returns)
    std_return = statistics.pstdev(returns)
    if std_return == 0:
        return 0.0
    period_sharpe = (mean_return - risk_free_rate / periods_per_year) / std_return
    return period_sharpe * (periods_per_year**0.5)


def win_rate(trades: list[Trade]) -> float:
    closed = [t for t in trades if t.realized_pnl is not None]
    if not closed:
        return 0.0
    wins = sum(1 for t in closed if t.realized_pnl > 0)
    return wins / len(closed)


def compute_backtest_result(
    *,
    run_id: str,
    created_at: datetime,
    strategy: str,
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    initial_cash: float,
    trades: list[Trade],
    equity_curve: list[float],
    params: dict | None = None,
) -> BacktestResult:
    final_equity = equity_curve[-1] if equity_curve else initial_cash
    total_pnl = final_equity - initial_cash
    total_pnl_pct = total_pnl / initial_cash if initial_cash else 0.0

    return BacktestResult(
        run_id=run_id,
        created_at=created_at,
        strategy=strategy,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        max_drawdown=max_drawdown(equity_curve),
        sharpe_ratio=sharpe_ratio(equity_curve),
        win_rate=win_rate(trades),
        num_trades=len(trades),
        params_json=json.dumps(params or {}, sort_keys=True),
    )
