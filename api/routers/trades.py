from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from api.deps import get_session, resolve_run_id
from api.schemas import TradeListOut, TradeOut
from sim.models import Trade

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=TradeListOut)
def list_trades(
    run_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    resolved = resolve_run_id(session, run_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="no backtest runs found -- run POST /api/backtest first")

    total = session.exec(select(func.count()).select_from(Trade).where(Trade.run_id == resolved)).one()
    trades = session.exec(
        select(Trade).where(Trade.run_id == resolved).order_by(Trade.timestamp).offset(offset).limit(limit)
    ).all()

    return TradeListOut(run_id=resolved, total=total, limit=limit, offset=offset, trades=list(trades))


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, session: Session = Depends(get_session)):
    trade = session.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"trade '{trade_id}' not found")
    return trade
