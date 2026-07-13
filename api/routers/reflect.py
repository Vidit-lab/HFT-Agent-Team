"""POST /api/reflect -- Phase 6: on-demand trigger for the Reflection Agent
batch. Deliberately separate from POST /api/run-cycle; see
agents/reflection_loop.py for why. A scheduler can call this on its own
cadence once one exists (the ccxt/live-data phase).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from agents.reflection_loop import DEFAULT_LOOKBACK_DAYS, run_reflection_batch
from api.deps import get_memory_client, get_session
from api.schemas import (
    PendingReflectionOut,
    PendingTradeOut,
    ReflectionOut,
    ReflectOut,
    ReflectRequest,
)
from memory.client import SupermemoryClient
from sim.models import Reflection, Trade

router = APIRouter(prefix="/api/reflect", tags=["reflect"])


@router.get("/pending", response_model=PendingReflectionOut)
def pending_reflection(
    lookback_days: float = Query(DEFAULT_LOOKBACK_DAYS, ge=0),
    session: Session = Depends(get_session),
):
    """Trades the Reflection Agent hasn't diagnosed yet, each tagged with why it
    is (or isn't) eligible. Mirrors agents.reflection_loop._find_eligible_trades'
    rule exactly: a trade is eligible once it's closed (realized PnL is known) or
    it has been open at least `lookback_days`."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(days=lookback_days)

    already = select(Reflection.trade_id)
    unreflected = session.exec(
        select(Trade).where(Trade.id.not_in(already)).order_by(Trade.timestamp)
    ).all()

    out: list[PendingTradeOut] = []
    for t in unreflected:
        days_held = max(0, (now - t.timestamp).days)
        if t.realized_pnl is not None:
            eligible, reason, wait = True, "closed", 0
        elif t.timestamp <= cutoff:
            eligible, reason, wait = True, "aged", 0
        else:
            eligible, reason = False, "waiting"
            wait = max(0, lookback_days - days_held)
        out.append(
            PendingTradeOut(
                trade_id=t.id,
                symbol=t.symbol,
                side=t.side.value,
                size=t.size,
                price=t.price,
                timestamp=t.timestamp,
                regime_at_entry=t.regime_at_entry,
                realized_pnl=t.realized_pnl,
                days_held=days_held,
                eligible=eligible,
                reason=reason,
                days_until_eligible=wait,
            )
        )

    return PendingReflectionOut(
        lookback_days=lookback_days,
        eligible_count=sum(1 for t in out if t.eligible),
        waiting_count=sum(1 for t in out if not t.eligible),
        trades=out,
    )


@router.post("", response_model=ReflectOut)
def reflect_endpoint(
    request: ReflectRequest,
    session: Session = Depends(get_session),
    memory_client: SupermemoryClient = Depends(get_memory_client),
):
    results = run_reflection_batch(
        session,
        memory_client,
        run_id=request.run_id,
        max_trades=request.max_trades,
        lookback_days=request.lookback_days,
        as_of=request.as_of,
    )

    return ReflectOut(
        reflected_count=len(results),
        reflections=[
            ReflectionOut(
                trade_id=r.trade_id,
                symbol=r.symbol,
                outcome=r.outcome,
                return_pct=r.return_pct,
                diagnosis=r.diagnosis,
                lesson_text=r.lesson_text,
                lesson_memory_id=r.lesson_memory_id,
                confidence=r.confidence,
            )
            for r in results
        ],
    )
