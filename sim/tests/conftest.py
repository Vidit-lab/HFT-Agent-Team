"""Shared fixtures for sim/ tests."""

from __future__ import annotations

import math

import pandas as pd
import pytest


def make_synthetic_bars(n: int = 120, start_price: float = 100.0) -> pd.DataFrame:
    """Deterministic, network-free OHLCV bars: a sum-of-sines price path that
    oscillates enough to trigger multiple SMA crossovers. Same `n` always
    produces the same DataFrame -- no RNG involved.
    """
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    closes = [start_price + 10 * math.sin(i / 8) + 5 * math.sin(i / 3) + 0.05 * i for i in range(n)]
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": closes,
            "high": [c + 1.0 for c in closes],
            "low": [c - 1.0 for c in closes],
            "close": closes,
            "volume": [1_000_000] * n,
        }
    )
    df["timestamp"] = df["timestamp"].astype("datetime64[us]")
    return df


@pytest.fixture
def synthetic_bars() -> pd.DataFrame:
    return make_synthetic_bars()
