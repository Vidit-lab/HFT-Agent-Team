from datetime import datetime

import pytest

from sim.engine import BacktestEngine
from sim.models import Side, Signal
from sim.strategies.moving_average_crossover import generate_signals


def _ts(day: int = 2) -> datetime:
    return datetime(2023, 1, day)


def test_buy_applies_slippage_and_fee_and_reduces_cash():
    engine = BacktestEngine(run_id="t1", strategy="test", initial_cash=10_000.0, fee_bps=10, slippage_bps=5)
    trade = engine.process_signal(Signal(timestamp=_ts(), symbol="AAPL", side=Side.BUY, size=10), mark_price=100.0)

    assert trade.price == pytest.approx(100.05)  # +5bps slippage on a buy
    assert trade.fee == pytest.approx(100.05 * 10 * 10 / 10_000)
    assert trade.realized_pnl is None
    assert engine.cash == pytest.approx(10_000.0 - (trade.price * 10 + trade.fee))


def test_sell_applies_negative_slippage_and_increases_cash():
    engine = BacktestEngine(run_id="t2", strategy="test", initial_cash=10_000.0, fee_bps=10, slippage_bps=5)
    engine.process_signal(Signal(timestamp=_ts(2), symbol="AAPL", side=Side.BUY, size=10), mark_price=100.0)
    trade = engine.process_signal(Signal(timestamp=_ts(3), symbol="AAPL", side=Side.SELL, size=10), mark_price=110.0)

    assert trade.price == pytest.approx(110.0 - 110.0 * 5 / 10_000)  # -5bps slippage on a sell
    assert trade.realized_pnl == pytest.approx((trade.price - 100.05) * 10)


def test_closing_a_long_position_computes_realized_pnl_and_flat_position():
    engine = BacktestEngine(run_id="t3", strategy="test", initial_cash=10_000.0, fee_bps=0, slippage_bps=0)
    engine.process_signal(Signal(timestamp=_ts(2), symbol="AAPL", side=Side.BUY, size=5), mark_price=100.0)
    trade = engine.process_signal(Signal(timestamp=_ts(3), symbol="AAPL", side=Side.SELL, size=5), mark_price=120.0)

    assert trade.realized_pnl == pytest.approx((120.0 - 100.0) * 5)
    assert engine._positions["AAPL"].size == 0
    assert engine.final_positions() == []  # flat positions aren't reported


def test_mark_to_market_tracks_equity_and_drawdown():
    engine = BacktestEngine(run_id="t4", strategy="test", initial_cash=10_000.0, fee_bps=0, slippage_bps=0)
    engine.process_signal(Signal(timestamp=_ts(2), symbol="AAPL", side=Side.BUY, size=10), mark_price=100.0)

    snap_up = engine.mark_to_market(_ts(3), {"AAPL": 110.0})
    assert snap_up.equity == pytest.approx(9_000.0 + 1_100.0)
    assert snap_up.drawdown == 0.0

    snap_down = engine.mark_to_market(_ts(4), {"AAPL": 90.0})
    assert snap_down.equity == pytest.approx(9_000.0 + 900.0)
    assert snap_down.drawdown > 0


def test_run_processes_every_bar_and_every_signal(synthetic_bars):
    signals = generate_signals(synthetic_bars, "SYN")
    engine = BacktestEngine(run_id="t5", strategy="sma", initial_cash=100_000.0)
    engine.run(synthetic_bars, signals, "SYN")

    assert len(engine.portfolio_snapshots) == len(synthetic_bars)
    assert len(engine.trades) == len(signals)
    assert len(signals) > 0  # sanity: the fixture should actually trigger crossovers
