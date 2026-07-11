"""POST /api/reflect -- Phase 6: on-demand trigger for the Reflection Agent
batch. Deliberately separate from POST /api/run-cycle; see
agents/reflection_loop.py for why. A scheduler can call this on its own
cadence once one exists (the ccxt/live-data phase).
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from agents.reflection_loop import run_reflection_batch
from api.deps import get_memory_client, get_session
from api.schemas import ReflectionOut, ReflectOut, ReflectRequest
from memory.client import SupermemoryClient

router = APIRouter(prefix="/api/reflect", tags=["reflect"])


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
