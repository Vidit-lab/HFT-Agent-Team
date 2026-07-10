"""Trivial mechanical strategy used to validate the engine: SMA crossover.

Pure function of `bars` -- rolling means only, no randomness, no external
state -- so the same input bars always produce the same signals.
"""

from __future__ import annotations

import pandas as pd

from sim.models import Side, Signal


def generate_signals(
    bars: pd.DataFrame,
    symbol: str,
    *,
    short_window: int = 10,
    long_window: int = 30,
    size: float = 1.0,
) -> list[Signal]:
    """Buy `size` units when the short SMA crosses above the long SMA; sell the
    full position when it crosses back below."""
    if len(bars) < long_window + 1:
        return []

    df = bars.sort_values("timestamp").reset_index(drop=True)
    df["sma_short"] = df["close"].rolling(window=short_window).mean()
    df["sma_long"] = df["close"].rolling(window=long_window).mean()
    above = df["sma_short"] > df["sma_long"]
    crossed_up = above & ~above.shift(1, fill_value=False)
    crossed_down = ~above & above.shift(1, fill_value=False)

    signals: list[Signal] = []
    in_position = False
    for row, is_up, is_down in zip(df.itertuples(index=False), crossed_up, crossed_down):
        if pd.isna(row.sma_long):
            continue
        if is_up and not in_position:
            signals.append(Signal(timestamp=row.timestamp, symbol=symbol, side=Side.BUY, size=size))
            in_position = True
        elif is_down and in_position:
            signals.append(Signal(timestamp=row.timestamp, symbol=symbol, side=Side.SELL, size=size))
            in_position = False

    return signals
