"""Event-driven backtest engine.

Feeds OHLCV bars through in order; any signal timestamped at a given bar is
filled at that bar's close (plus fees/slippage), then the portfolio is
marked to market. Fees and slippage are fixed-bps functions of price/size --
deterministic by construction, no randomness anywhere in the loop -- so the
same (bars, signals) input always produces the same trade sequence and
equity curve.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlmodel import func, select

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

    @classmethod
    def resume_or_create(
        cls,
        session,
        run_id: str,
        strategy: str,
        initial_cash: float,
        *,
        fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
    ) -> "BacktestEngine":
        """Rehydrate engine state from the DB for `run_id` if it already has
        history, otherwise start fresh. Used for live/paper cycles, where each
        call is a fresh process/request and the ledger -- not any in-memory
        object -- is the source of truth for what happened before."""
        engine = cls(
            run_id=run_id, strategy=strategy, initial_cash=initial_cash, fee_bps=fee_bps, slippage_bps=slippage_bps
        )

        latest_snapshot = session.exec(
            select(Portfolio).where(Portfolio.run_id == run_id).order_by(Portfolio.timestamp.desc()).limit(1)
        ).first()
        if latest_snapshot is None:
            return engine  # first cycle for this run_id

        engine.cash = latest_snapshot.cash
        max_equity = session.exec(select(func.max(Portfolio.equity)).where(Portfolio.run_id == run_id)).one()
        engine._peak_equity = max(initial_cash, max_equity or initial_cash)

        for pos in session.exec(select(Position).where(Position.run_id == run_id)).all():
            engine._positions[pos.symbol] = _PositionState(size=pos.size, avg_entry_price=pos.avg_entry_price)
            if pos.size:
                engine._last_price[pos.symbol] = pos.avg_entry_price + pos.unrealized_pnl / pos.size

        return engine

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

    def step(
        self, timestamp: datetime, symbol: str, mark_price: float, signal: Signal | None = None
    ) -> tuple[Trade | None, Portfolio]:
        """Process one live/paper cycle: optionally fill `signal` at
        `mark_price`, then mark to market. Thin orchestration over
        process_signal/mark_to_market -- no logic duplicated."""
        trade = self.process_signal(signal, mark_price) if signal is not None else None
        snapshot = self.mark_to_market(timestamp, {symbol: mark_price})
        return trade, snapshot

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

    def upsert_positions(self, session) -> None:
        """Position is "current holdings," not append-only (see its
        docstring) -- update existing rows in place rather than inserting a
        new one every call, and drop the row once a position is fully
        closed. This matters once an engine is resumed across multiple
        calls (step()); Phase 2's batch run() never needed it because it
        only ever persisted once, at the very end, with exactly one fresh
        row per open symbol."""
        open_symbols = {p.symbol for p in self.final_positions()}
        for new_position in self.final_positions():
            existing = session.exec(
                select(Position).where(Position.run_id == self.run_id, Position.symbol == new_position.symbol)
            ).first()
            if existing:
                existing.size = new_position.size
                existing.avg_entry_price = new_position.avg_entry_price
                existing.unrealized_pnl = new_position.unrealized_pnl
                existing.updated_at = new_position.updated_at
                session.add(existing)
            else:
                session.add(new_position)

        tracked_symbols = set(self._positions.keys())
        for symbol in tracked_symbols - open_symbols:
            existing = session.exec(
                select(Position).where(Position.run_id == self.run_id, Position.symbol == symbol)
            ).first()
            if existing:
                session.delete(existing)

    def persist(self, session) -> None:
        for trade in self.trades:
            session.add(trade)
        for snapshot in self.portfolio_snapshots:
            session.add(snapshot)
        self.upsert_positions(session)
        session.commit()
