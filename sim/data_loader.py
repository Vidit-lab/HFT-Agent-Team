"""OHLCV loading with local Parquet caching.

Caching to Parquet is what makes backtests deterministic and offline-repeatable:
the first call for a given (symbol, start, end) hits the network; every call
after that reads the identical cached bars back off disk, so a strategy fed
the same cache produces the same signals and the same trades every time.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path("data")


def _cache_path(symbol: str, start: str, end: str, cache_dir: Path) -> Path:
    return cache_dir / f"{symbol}_{start}_{end}.parquet"


def _fetch_yfinance(symbol: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
    if raw.empty:
        raise ValueError(f"yfinance returned no data for {symbol} between {start} and {end}")

    # yfinance returns MultiIndex columns (Price, Ticker) even for a single symbol.
    raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename_axis("timestamp").reset_index()
    raw.columns = [str(c).lower() for c in raw.columns]
    return _normalize(raw[["timestamp", "open", "high", "low", "close", "volume"]])


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    # Parquet round-trips can shift the timestamp column's stored resolution
    # (e.g. datetime64[s] -> datetime64[ms]) depending on the pyarrow version,
    # even though the underlying instants are identical. Pin it explicitly so
    # a freshly-fetched frame and a cache-read frame always compare equal.
    df = df.copy()
    df["timestamp"] = df["timestamp"].astype("datetime64[us]")
    return df


def load_ohlcv(
    symbol: str,
    start: str,
    end: str,
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Load daily OHLCV bars for `symbol` between `start` and `end` (YYYY-MM-DD).

    Returns a DataFrame with columns: timestamp, open, high, low, close, volume,
    sorted ascending by timestamp. Cached to `cache_dir` as Parquet.
    """
    cache_dir = Path(cache_dir)
    path = _cache_path(symbol, start, end, cache_dir)

    if path.exists() and not force_refresh:
        return _normalize(pd.read_parquet(path))

    df = _fetch_yfinance(symbol, start, end)
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df
