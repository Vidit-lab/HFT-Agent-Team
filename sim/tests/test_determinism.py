"""Phase 2 definition of done: running the mechanical strategy over a fixed
date range produces byte-identical results on every run.

`run_id` and `created_at` are run-instance bookkeeping (like a DB primary key
or a wall-clock timestamp), not trading outputs, so they're deliberately
excluded from the comparison here (and are exactly why compute_backtest_result
takes them as explicit caller-supplied arguments rather than generating them
internally -- see sim/metrics.py). Everything that reflects actual trading
logic -- every trade, the full equity curve, every computed metric -- must
match exactly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sim.engine import BacktestEngine
from sim.metrics import compute_backtest_result
from sim.strategies.moving_average_crossover import generate_signals

from .conftest import make_synthetic_bars


def _run_once(bars, run_id: str):
    signals = generate_signals(bars, "SYN")
    engine = BacktestEngine(run_id=run_id, strategy="sma_crossover", initial_cash=100_000.0)
    engine.run(bars, signals, "SYN")
    result = compute_backtest_result(
        run_id=run_id,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        strategy="sma_crossover",
        symbol="SYN",
        start_date=bars["timestamp"].iloc[0],
        end_date=bars["timestamp"].iloc[-1],
        initial_cash=100_000.0,
        trades=engine.trades,
        equity_curve=engine.equity_curve,
        params={"short_window": 10, "long_window": 30},
    )
    return engine, result


def _trade_fingerprint(trade) -> tuple:
    return (
        trade.timestamp,
        trade.symbol,
        trade.side,
        trade.size,
        trade.price,
        trade.fee,
        trade.slippage_cost,
        trade.realized_pnl,
    )


def test_backtest_is_byte_identical_across_independent_runs():
    bars = make_synthetic_bars(n=150)

    engine_a, result_a = _run_once(bars.copy(deep=True), run_id="run-a")
    engine_b, result_b = _run_once(bars.copy(deep=True), run_id="run-b")

    assert len(engine_a.trades) > 0, "fixture should actually generate trades to make this test meaningful"
    assert [_trade_fingerprint(t) for t in engine_a.trades] == [_trade_fingerprint(t) for t in engine_b.trades]
    assert engine_a.equity_curve == engine_b.equity_curve

    for attr in ("final_equity", "total_pnl", "total_pnl_pct", "max_drawdown", "sharpe_ratio", "win_rate", "num_trades"):
        assert getattr(result_a, attr) == getattr(result_b, attr), f"mismatch on {attr}"


def test_backtest_is_identical_across_three_independent_runs():
    bars = make_synthetic_bars(n=150)
    pnls = [_run_once(bars.copy(deep=True), run_id=f"run-{i}")[1].total_pnl for i in range(3)]
    assert len(set(pnls)) == 1
