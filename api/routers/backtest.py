"""POST /api/backtest -- deliberately a real implementation, not a stub.

The plan calls this a stub for Phase 3, but the whole capability (data
loading, engine, metrics) is already built and tested as of Phase 2 -- the
only "stub" left would be a fake response for something that fully works.
POST /api/run-cycle (cycle.py) is the one that's genuinely a stub, because
the agent orchestrator it depends on doesn't exist until Phase 4.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.deps import get_session
from api.schemas import BacktestRequest, BacktestRunOut
from sim.data_loader import load_ohlcv
from sim.engine import BacktestEngine
from sim.metrics import compute_backtest_result
from sim.strategies.moving_average_crossover import generate_signals

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("", response_model=BacktestRunOut)
def run_backtest(request: BacktestRequest, session: Session = Depends(get_session)):
    try:
        bars = load_ohlcv(request.symbol, request.start, request.end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    signals = generate_signals(
        bars, request.symbol, short_window=request.short_window, long_window=request.long_window
    )

    run_id = str(uuid.uuid4())
    engine = BacktestEngine(
        run_id=run_id,
        strategy=request.strategy,
        initial_cash=request.initial_cash,
        fee_bps=request.fee_bps,
        slippage_bps=request.slippage_bps,
    )
    engine.run(bars, signals, request.symbol)

    result = compute_backtest_result(
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        strategy=request.strategy,
        symbol=request.symbol,
        start_date=bars["timestamp"].iloc[0],
        end_date=bars["timestamp"].iloc[-1],
        initial_cash=request.initial_cash,
        trades=engine.trades,
        equity_curve=engine.equity_curve,
        params=request.model_dump(exclude={"symbol", "start", "end"}),
    )

    engine.persist(session)
    session.add(result)
    session.commit()

    return result
