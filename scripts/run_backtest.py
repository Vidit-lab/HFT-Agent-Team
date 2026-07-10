"""Phase 2 smoke test: run the SMA-crossover strategy through the full engine
and persist results to SQLite. Run with: python scripts/run_backtest.py
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sim.data_loader import load_ohlcv
from sim.db import get_engine, get_session, init_db
from sim.engine import BacktestEngine
from sim.metrics import compute_backtest_result
from sim.strategies.moving_average_crossover import generate_signals

SYMBOL = "AAPL"
START = "2023-01-01"
END = "2023-12-31"
INITIAL_CASH = 100_000.0


def main() -> int:
    bars = load_ohlcv(SYMBOL, START, END)
    signals = generate_signals(bars, SYMBOL)
    print(f"Loaded {len(bars)} bars, generated {len(signals)} signals")

    run_id = str(uuid.uuid4())
    engine = BacktestEngine(run_id=run_id, strategy="sma_crossover", initial_cash=INITIAL_CASH)
    engine.run(bars, signals, SYMBOL)

    result = compute_backtest_result(
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        strategy="sma_crossover",
        symbol=SYMBOL,
        start_date=bars["timestamp"].iloc[0],
        end_date=bars["timestamp"].iloc[-1],
        initial_cash=INITIAL_CASH,
        trades=engine.trades,
        equity_curve=engine.equity_curve,
        params={"short_window": 10, "long_window": 30},
    )

    db_engine = get_engine()
    init_db(db_engine)
    with get_session(db_engine) as session:
        engine.persist(session)
        session.add(result)
        session.commit()

    print(f"\nrun_id: {run_id}")
    print(f"trades: {result.num_trades}")
    print(f"final_equity: {result.final_equity:.2f}  (started at {INITIAL_CASH:.2f})")
    print(f"total_pnl: {result.total_pnl:.2f} ({result.total_pnl_pct:.2%})")
    print(f"max_drawdown: {result.max_drawdown:.2%}")
    print(f"sharpe_ratio: {result.sharpe_ratio:.3f}")
    print(f"win_rate: {result.win_rate:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
