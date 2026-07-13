"""One entry point for bars, routing on the symbol.

    "BTC/USDT" -> ccxt (live, 24/7, intraday)
    "AAPL"     -> the yfinance/Parquet loader in sim/data_loader.py

Both paths return the *identical* frame -- columns [timestamp, open, high, low,
close, volume], naive-UTC timestamps, ascending -- which is the whole point:
every agent node reads `bars["close"]` and `bars["timestamp"]` and nothing else
(see agents/graph.py), so swapping the data source underneath changes nothing
upstream of this file.

Response metadata (which exchange served it, whether it came off the network or
off the offline snapshot) rides along on `df.attrs` so the API layer can be
honest about freshness without polluting the signature the agents call.

Two caches, and they do different jobs:

  * The **TTL cache** is what makes browser polling safe. The frontend refetches
    bars every 20s and the ticker every 5s; without a TTL, N open tabs would mean
    N times the exchange calls. With it, the exchange sees at most one call per
    window no matter how many clients are watching.

  * The **Parquet snapshot** is the offline net. Every successful fetch overwrites
    it; any failed fetch reads it back and flags `stale`. If the venue wifi dies
    mid-demo, the chart still renders real (if slightly old) candles rather than
    an error state.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

from sim.data_loader import DEFAULT_CACHE_DIR, load_ohlcv

BAR_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

DEFAULT_EXCHANGE = "binance"
# Probed from this network: binance/bybit/kucoin/coinbase all reachable;
# kraken and okx time out, so they are deliberately not in the chain.
FALLBACK_EXCHANGES = ["bybit", "kucoin", "coinbase"]

DEFAULT_TIMEFRAME = "1h"
DEFAULT_LIMIT = 500

# Crypto trades 24/7, so a year holds far more bars than an equity year's 252.
# Kept here for whenever backtest metrics (sim/metrics.py) go crypto.
BARS_PER_YEAR = {"15m": 35_040, "1h": 8_760, "4h": 2_190, "1d": 365}

TIMEFRAMES = tuple(BARS_PER_YEAR)

_BARS_TTL_SECONDS = 20.0
_QUOTE_TTL_SECONDS = 5.0

_SNAPSHOT_DIR = Path(DEFAULT_CACHE_DIR) / "ccxt"

# ccxt's sync clients are plain `requests` wrappers; FastAPI runs sync endpoints
# in a threadpool, so serialise access rather than reason about their thread
# safety. Fetches are short and TTL-cached, so contention is negligible.
_lock = threading.Lock()
_bars_cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
_quote_cache: dict[tuple, tuple[float, "Quote"]] = {}


@dataclass
class Quote:
    """The live ticker -- what makes the chart feel alive."""

    symbol: str
    last: float
    change_24h_pct: float
    quote_volume: float
    exchange: str
    fetched_at: str
    stale: bool


def is_crypto(symbol: str) -> bool:
    """`BTC/USDT` -> True, `AAPL` -> False. The base/quote slash is the tell."""
    return "/" in symbol


def slug(symbol: str) -> str:
    """`BTC/USDT` -> `BTC-USDT`. A slash is not legal in a filename."""
    return symbol.replace("/", "-")


@lru_cache(maxsize=8)
def _exchange(name: str):
    import ccxt

    # `load_markets` is heavy, so the instance is cached rather than rebuilt per
    # request. enableRateLimit makes ccxt self-throttle if we ever do burst.
    return getattr(ccxt, name)({"enableRateLimit": True, "timeout": 8000})


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Naive UTC, microsecond-pinned. Load-bearing: agents/reflection_loop.py
    # compares `trade.timestamp <= cutoff` against a naive datetime, and a
    # tz-aware value would raise there.
    df["timestamp"] = df["timestamp"].astype("datetime64[us]")
    return df.sort_values("timestamp").reset_index(drop=True)


# ── snapshots: the offline net ────────────────────────────────────────────────


def _snapshot_path(exchange: str, symbol: str, timeframe: str) -> Path:
    return _SNAPSHOT_DIR / f"{exchange}_{slug(symbol)}_{timeframe}.parquet"


def _write_snapshot(exchange: str, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    try:
        _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(_snapshot_path(exchange, symbol, timeframe), index=False)
    except Exception:
        # A snapshot is a nicety; never fail a live request over one.
        pass


def _read_snapshot(symbol: str, timeframe: str) -> tuple[pd.DataFrame, str] | None:
    """Newest snapshot for this symbol+timeframe from any exchange we've used."""
    candidates = sorted(
        _SNAPSHOT_DIR.glob(f"*_{slug(symbol)}_{timeframe}.parquet"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            return _normalize(pd.read_parquet(path)), path.name.split("_")[0]
        except Exception:
            continue
    return None


# ── the crypto path ───────────────────────────────────────────────────────────


def _fetch_ccxt_bars(symbol: str, timeframe: str, limit: int) -> tuple[pd.DataFrame, str]:
    errors: list[str] = []
    for name in [DEFAULT_EXCHANGE, *FALLBACK_EXCHANGES]:
        try:
            raw = _exchange(name).fetch_ohlcv(symbol, timeframe, limit=limit)
            if not raw:
                errors.append(f"{name}: empty")
                continue
            df = pd.DataFrame(raw, columns=BAR_COLUMNS)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
            return _normalize(df), name
        except Exception as exc:  # network, geo-block, delisted symbol...
            errors.append(f"{name}: {type(exc).__name__}")
    raise ConnectionError(f"no exchange could serve {symbol} {timeframe} ({'; '.join(errors)})")


# ── the equity path (yfinance, still live under the hood, never charted) ───────


def _fetch_equity_bars(symbol: str, limit: int, force_refresh: bool) -> pd.DataFrame:
    # yfinance treats `end` as EXCLUSIVE, so `end=today` can never include
    # today's bar even after the session closes. +1 day fixes that.
    end = (date.today() + timedelta(days=1)).isoformat()
    # ~252 trading days per 365 calendar days, plus slack for holidays.
    start = (date.today() - timedelta(days=int(limit * 1.6) + 40)).isoformat()
    return load_ohlcv(symbol, start, end, force_refresh=force_refresh).tail(limit).reset_index(drop=True)


def _richest_cached_parquet(symbol: str) -> Path | None:
    """Largest cached window for an equity -- the reflection loop leaves tiny
    10-day buffer caches behind that we don't want to pick for a chart."""
    candidates = list(Path(DEFAULT_CACHE_DIR).glob(f"{slug(symbol)}_*.parquet"))
    return max(candidates, key=lambda p: p.stat().st_size) if candidates else None


# ── the public API ────────────────────────────────────────────────────────────


def get_bars(
    symbol: str,
    *,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Bars for `symbol`, newest last. Never raises on a network blip if a
    snapshot exists -- it degrades to the last known-good frame and says so via
    `df.attrs["stale"]`.

    `timeframe` only applies to crypto; equities are daily bars by definition.
    """
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unsupported timeframe {timeframe!r}; expected one of {list(TIMEFRAMES)}")

    if not is_crypto(symbol):
        try:
            df = _fetch_equity_bars(symbol, limit, force_refresh)
            df.attrs.update(symbol=symbol, timeframe="1d", exchange="yfinance", stale=False)
            return df
        except Exception:
            path = _richest_cached_parquet(symbol)
            if path is None:
                raise
            df = _normalize(pd.read_parquet(path)).tail(limit).reset_index(drop=True)
            df.attrs.update(symbol=symbol, timeframe="1d", exchange="yfinance", stale=True)
            return df

    key = (symbol, timeframe, limit)
    with _lock:
        if not force_refresh:
            hit = _bars_cache.get(key)
            if hit and (time.monotonic() - hit[0]) < _BARS_TTL_SECONDS:
                return hit[1]

        try:
            df, exchange = _fetch_ccxt_bars(symbol, timeframe, limit)
            df.attrs.update(symbol=symbol, timeframe=timeframe, exchange=exchange, stale=False)
            _write_snapshot(exchange, symbol, timeframe, df)
            _bars_cache[key] = (time.monotonic(), df)
            return df
        except Exception:
            snapshot = _read_snapshot(symbol, timeframe)
            if snapshot is None:
                raise
            df, exchange = snapshot
            df = df.tail(limit).reset_index(drop=True)
            df.attrs.update(symbol=symbol, timeframe=timeframe, exchange=exchange, stale=True)
            return df


def get_quote(symbol: str) -> Quote:
    """Live last price + 24h change. Crypto only -- the ticking heartbeat."""
    if not is_crypto(symbol):
        bars = get_bars(symbol, timeframe="1d", limit=2)
        last = float(bars.iloc[-1].close)
        prev = float(bars.iloc[0].close) if len(bars) > 1 else last
        return Quote(
            symbol=symbol,
            last=last,
            change_24h_pct=((last - prev) / prev * 100) if prev else 0.0,
            quote_volume=float(bars.iloc[-1].volume),
            exchange="yfinance",
            fetched_at=pd.Timestamp.utcnow().isoformat(),
            stale=bool(bars.attrs.get("stale")),
        )

    with _lock:
        hit = _quote_cache.get(symbol)
        if hit and (time.monotonic() - hit[0]) < _QUOTE_TTL_SECONDS:
            return hit[1]

        for name in [DEFAULT_EXCHANGE, *FALLBACK_EXCHANGES]:
            try:
                t = _exchange(name).fetch_ticker(symbol)
                quote = Quote(
                    symbol=symbol,
                    last=float(t["last"]),
                    change_24h_pct=float(t.get("percentage") or 0.0),
                    quote_volume=float(t.get("quoteVolume") or 0.0),
                    exchange=name,
                    fetched_at=pd.Timestamp.utcnow().isoformat(),
                    stale=False,
                )
                _quote_cache[symbol] = (time.monotonic(), quote)
                return quote
            except Exception:
                continue

    # Every exchange failed. Fall back to the newest snapshot bar so the UI shows
    # a real (stale-flagged) price instead of a dash.
    snapshot = _read_snapshot(symbol, DEFAULT_TIMEFRAME)
    if snapshot is None:
        raise ConnectionError(f"no exchange could serve a quote for {symbol}")
    df, exchange = snapshot
    last = float(df.iloc[-1].close)
    day_ago = float(df.iloc[-25].close) if len(df) >= 25 else float(df.iloc[0].close)
    return Quote(
        symbol=symbol,
        last=last,
        change_24h_pct=((last - day_ago) / day_ago * 100) if day_ago else 0.0,
        quote_volume=float(df.iloc[-1].volume),
        exchange=exchange,
        fetched_at=pd.Timestamp.utcnow().isoformat(),
        stale=True,
    )
