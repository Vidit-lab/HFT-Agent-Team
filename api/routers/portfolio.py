from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from api.deps import get_session, resolve_run_id
from api.schemas import PortfolioOut
from sim.models import BacktestResult, Portfolio, Position

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioOut)
def get_portfolio(run_id: str | None = None, session: Session = Depends(get_session)):
    resolved = resolve_run_id(session, run_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="no backtest runs found -- run POST /api/backtest first")

    snapshots = session.exec(
        select(Portfolio).where(Portfolio.run_id == resolved).order_by(Portfolio.timestamp)
    ).all()
    if not snapshots:
        raise HTTPException(status_code=404, detail=f"no portfolio snapshots for run '{resolved}'")

    positions = session.exec(select(Position).where(Position.run_id == resolved)).all()
    run = session.get(BacktestResult, resolved)

    return PortfolioOut(
        run_id=resolved,
        strategy=run.strategy if run else "",
        symbol=run.symbol if run else "",
        latest=snapshots[-1],
        positions=list(positions),
        equity_curve=list(snapshots),
    )
