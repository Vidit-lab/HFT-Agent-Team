"""Shared prompt-formatting helpers for turning bars/memories into the text
blocks every node's user prompt is built from. Extracted from Phase 4's
trader.py once Phase 5 needed the same formatting in more than one node
(Market Analyst, Researcher Bull/Bear, Trader all describe recent price
action; Researcher Bull/Bear and Trader all describe retrieved memories).
"""

from __future__ import annotations

import pandas as pd


def format_market_state(symbol: str, bars: pd.DataFrame, lookback: int = 20) -> str:
    recent = bars.tail(lookback)
    lines = [f"{row.timestamp.date()}: close={row.close:.2f}" for row in recent.itertuples(index=False)]
    latest_close = bars.iloc[-1].close
    first_close = recent.iloc[0].close
    pct_change = (latest_close - first_close) / first_close * 100
    return (
        f"Symbol: {symbol}\n"
        f"Last {len(recent)} trading days (close price):\n" + "\n".join(lines) + "\n"
        f"Current price: {latest_close:.2f}\n"
        f"{len(recent)}-day change: {pct_change:+.2f}%"
    )


def format_memories(memories: list) -> str:
    if not memories:
        return "No relevant past lessons or trades found."
    lines = []
    for m in memories:
        metadata = m.metadata or {}
        lines.append(f"- [{metadata.get('type', 'memory')}] {m.chunk}")
    return "\n".join(lines)
