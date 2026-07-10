from datetime import datetime

import pytest

from sim.metrics import max_drawdown, sharpe_ratio, win_rate
from sim.models import Side, Trade


def _trade(realized_pnl: float | None) -> Trade:
    return Trade(
        run_id="r",
        timestamp=datetime(2023, 1, 1),
        symbol="X",
        side=Side.BUY,
        size=1,
        price=1,
        fee=0,
        slippage_cost=0,
        strategy="s",
        realized_pnl=realized_pnl,
    )


def test_max_drawdown_no_drawdown_when_monotonically_rising():
    assert max_drawdown([100, 110, 120]) == 0.0


def test_max_drawdown_measures_peak_to_trough():
    # peak 120, trough 90 -> (120 - 90) / 120
    assert max_drawdown([100, 120, 90, 130]) == pytest.approx(0.25)


def test_max_drawdown_empty_curve():
    assert max_drawdown([]) == 0.0


def test_sharpe_ratio_zero_variance_is_zero():
    assert sharpe_ratio([100, 100, 100]) == 0.0


def test_sharpe_ratio_positive_for_steady_uptrend():
    assert sharpe_ratio([100, 101, 102, 103, 104, 105]) > 0


def test_sharpe_ratio_negative_for_steady_downtrend():
    assert sharpe_ratio([105, 104, 103, 102, 101, 100]) < 0


def test_sharpe_ratio_too_short_curve_is_zero():
    assert sharpe_ratio([100]) == 0.0


def test_win_rate_only_counts_closed_trades():
    trades = [_trade(None), _trade(5.0), _trade(-2.0), _trade(3.0)]
    assert win_rate(trades) == pytest.approx(2 / 3)


def test_win_rate_no_closed_trades_is_zero():
    assert win_rate([_trade(None)]) == 0.0


def test_win_rate_no_trades_is_zero():
    assert win_rate([]) == 0.0
