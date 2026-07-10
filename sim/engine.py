"""Event-driven backtest engine.

Feeds OHLCV bars through in order; any signal timestamped at a given bar is
filled at that bar's close (plus fees/slippage), then the portfolio is
marked to market. Fees and slippage are fixed-bps functions of price/size --
deterministic by construction, no randomness anywhere in the loop -- so the
same (bars, signals) input always produces the same trade sequence and
equity curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from sim.models import Portfolio, Position, Side, Signal, Trade


@dataclass
class _PositionState:
    size: float = 0.0
    avg_entry_price: float = 0.0


class BacktestEngine:
    def __init__(
        self,
        run_id: str,
        strategy: str,
        initial_cash: float,
        *,
        fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
    ) -> None:
        self.run_id = run_id
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

        self._positions: dict[str, _PositionState] = {}
        self._last_price: dict[str, float] = {}
        self._peak_equity = initial_cash

        self.trades: list[Trade] = []
        self.portfolio_snapshots: list[Portfolio] = []

    def _fill_price(self, side: Side, mark_price: float) -> float:
        slip = mark_price * self.slippage_bps / 10_000
        return mark_price + slip if side == Side.BUY else mark_price - slip

    def process_signal(self, signal: Signal, mark_price: float) -> Trade:
        fill_price = self._fill_price(signal.side, mark_price)
        notional = fill_price * signal.size
        fee = notional * self.fee_bps / 10_000
        slippage_cost = abs(fill_price - mark_price) * signal.size

        pos = self._positions.setdefault(signal.symbol, _PositionState())
        realized_pnl: float | None = None
        signed_size = signal.size if signal.side == Side.BUY else -signal.size
        new_size = pos.size + signed_size

        same_direction_or_flat = (pos.size >= 0) if signal.side == Side.BUY else (pos.size <= 0)
        if same_direction_or_flat:
            if new_size != 0:
                pos.avg_entry_price = (
                    pos.avg_entry_price * pos.size + fill_price * signed_size
                ) / new_size
        else:
            closing_size = min(signal.size, abs(pos.size))
            if signal.side == Side.BUY:
                realized_pnl = (pos.avg_entry_price - fill_price) * closing_size
            else:
                realized_pnl = (fill_price - pos.avg_entry_price) * closing_size
            if new_size != 0 and (new_size > 0) != (pos.size > 0):
                # flipped through zero -- the remainder opens a fresh position at fill_price
                pos.avg_entry_price = fill_price
        pos.size = new_size

        if signal.side == Side.BUY:
            self.cash -= notional + fee
        else:
            self.cash += notional - fee

        trade = Trade(
            run_id=self.run_id,
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            side=signal.side,
            size=signal.size,
            price=fill_price,
            fee=fee,
            slippage_cost=slippage_cost,
            strategy=self.strategy,
            realized_pnl=realized_pnl,
        )
        self.trades.append(trade)
        self._last_price[signal.symbol] = mark_price
        return trade

    def mark_to_market(self, timestamp: datetime, prices: dict[str, float]) -> Portfolio:
        self._last_price.update(prices)
        # equity = cash + market value of open positions. `cash` already
        # reflects the money spent acquiring them, so this must be the
        # position's current market value (price * size), not unrealized PnL
        # alone -- adding just the PnL on top of cash would double-subtract
        # the cost basis.
        market_value = sum(
            self._last_price[symbol] * pos.size
            for symbol, pos in self._positions.items()
            if pos.size != 0 and symbol in self._last_price
        )
        equity = self.cash + market_value
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0.0

        snapshot = Portfolio(
            run_id=self.run_id,
            timestamp=timestamp,
            cash=self.cash,
            equity=equity,
            total_pnl=equity - self.initial_cash,
            drawdown=drawdown,
        )
        self.portfolio_snapshots.append(snapshot)
        return snapshot

    def run(self, bars: pd.DataFrame, signals: list[Signal], symbol: str) -> None:
        """Process `bars` (columns: timestamp, open, high, low, close, volume) in
        order. Any signal timestamped exactly at a bar is filled at that bar's
        close, then the portfolio is marked to market at that close."""
        signals_by_ts: dict = {}
        for sig in signals:
            signals_by_ts.setdefault(sig.timestamp, []).append(sig)

        for row in bars.itertuples(index=False):
            ts = row.timestamp
            for sig in signals_by_ts.get(ts, []):
                self.process_signal(sig, mark_price=row.close)
            self.mark_to_market(ts, {symbol: row.close})

    @property
    def equity_curve(self) -> list[float]:
        return [snap.equity for snap in self.portfolio_snapshots]

    def final_positions(self) -> list[Position]:
        last_ts = self.portfolio_snapshots[-1].timestamp if self.portfolio_snapshots else None
        result = []
        for symbol, pos in self._positions.items():
            if pos.size == 0:
                continue
            unrealized = (self._last_price.get(symbol, pos.avg_entry_price) - pos.avg_entry_price) * pos.size
            result.append(
                Position(
                    run_id=self.run_id,
                    symbol=symbol,
                    size=pos.size,
                    avg_entry_price=pos.avg_entry_price,
                    unrealized_pnl=unrealized,
                    updated_at=last_ts,
                )
            )
        return result

    def persist(self, session) -> None:
        for trade in self.trades:
            session.add(trade)
        for snapshot in self.portfolio_snapshots:
            session.add(snapshot)
        for position in self.final_positions():
            session.add(position)
        session.commit()
