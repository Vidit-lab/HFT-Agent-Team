"""Market data for the frontend price chart.

Bars come from sim/market_data.py, which routes on the symbol: crypto goes to a
live ccxt feed, equities to the yfinance/Parquet loader. Either way the frontend
gets the same shape, plus enough metadata (`exchange`, `stale`, `fetched_at`) to
be honest about where the numbers came from and how fresh they are.

The run's fills are overlaid as chart markers.
"""

from __future__ import annotations

import bisect

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from api.deps import get_session
from api.schemas import OHLCVBar, OHLCVOut, QuoteOut, TradeMarker
from sim.market_data import DEFAULT_TIMEFRAME, TIMEFRAMES, get_bars, get_quote
from sim.models import Trade

router = APIRouter(prefix="/api/market", tags=["market"])


def _unix(ts) -> int:
    return int(pd.Timestamp(ts).timestamp())


@router.get("/ohlcv", response_model=OHLCVOut)
def get_ohlcv(
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query(DEFAULT_TIMEFRAME),
    limit: int = Query(300, ge=20, le=1000),
    session: Session = Depends(get_session),
):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=422, detail=f"timeframe must be one of {list(TIMEFRAMES)}")

    try:
        df = get_bars(symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No market data for {symbol}: {exc}") from exc

    bars = [
        OHLCVBar(
            time=_unix(row.timestamp),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in df.itertuples(index=False)
    ]

    # A marker whose time doesn't land exactly on a bar simply won't render, so
    # snap each fill back to the bar it happened during. Cycle trades already
    # carry the bar's own timestamp; seeded and legacy trades may not.
    bar_times = [b.time for b in bars]
    markers: list[TradeMarker] = []
    if bar_times:
        trades = session.exec(select(Trade).where(Trade.symbol == symbol).order_by(Trade.timestamp)).all()
        for t in trades:
            ts = _unix(t.timestamp)
            if ts < bar_times[0]:
                continue  # older than the window on screen
            idx = bisect.bisect_right(bar_times, ts) - 1
            markers.append(
                TradeMarker(time=bar_times[idx], price=t.price, side=t.side.value, size=t.size, trade_id=t.id)
            )

    resolved_tf = df.attrs.get("timeframe", timeframe)
    return OHLCVOut(
        symbol=symbol,
        timeframe=resolved_tf,
        exchange=df.attrs.get("exchange", "unknown"),
        intraday=resolved_tf != "1d",
        last_bar_time=bar_times[-1] if bar_times else None,
        fetched_at=pd.Timestamp.utcnow().isoformat(),
        stale=bool(df.attrs.get("stale", False)),
        bars=bars,
        markers=markers,
    )


@router.get("/quote", response_model=QuoteOut)
def get_market_quote(symbol: str = Query("BTC/USDT")):
    """The live ticker the frontend polls every 5s. TTL-cached in market_data,
    so N open tabs still cost the exchange at most one call per window."""
    try:
        quote = get_quote(symbol)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No quote for {symbol}: {exc}") from exc
    return QuoteOut(**quote.__dict__)
