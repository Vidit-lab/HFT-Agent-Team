"""Shared prompt-formatting helpers for turning bars/memories into the text
blocks every node's user prompt is built from. Extracted from Phase 4's
trader.py once Phase 5 needed the same formatting in more than one node
(Market Analyst, Researcher Bull/Bear, Trader all describe recent price
action; Researcher Bull/Bear and Trader all describe retrieved memories).
"""

from __future__ import annotations

import pandas as pd


def bar_granularity(bars: pd.DataFrame) -> tuple[bool, str]:
    """(is_intraday, strftime_format), inferred from the spacing of the bars.

    Inferring beats threading a `timeframe` argument through every node: the
    frame already knows what it is. Without this, hourly bars would render as
    the same date printed 24 times over -- the model would see a day of price
    action and be told it was a day of *closes*.
    """
    step = bars["timestamp"].diff().median()
    intraday = pd.notna(step) and step < pd.Timedelta(days=1)
    return intraday, "%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"


def format_market_state(symbol: str, bars: pd.DataFrame, lookback: int = 20) -> str:
    recent = bars.tail(lookback)
    intraday, fmt = bar_granularity(bars)
    unit = "bars" if intraday else "days"
    lines = [f"{row.timestamp.strftime(fmt)}: close={row.close:.2f}" for row in recent.itertuples(index=False)]
    latest_close = bars.iloc[-1].close
    first_close = recent.iloc[0].close
    pct_change = (latest_close - first_close) / first_close * 100
    return (
        f"Symbol: {symbol}\n"
        f"Last {len(recent)} {unit} (close price):\n" + "\n".join(lines) + "\n"
        f"Current price: {latest_close:.2f}\n"
        f"{len(recent)}-{'bar' if intraday else 'day'} change: {pct_change:+.2f}%"
    )


def format_memories(memories: list) -> str:
    if not memories:
        return "No relevant past lessons or trades found."
    lines = []
    for m in memories:
        metadata = m.metadata or {}
        lines.append(f"- [{metadata.get('type', 'memory')}] {m.chunk}")
    return "\n".join(lines)
