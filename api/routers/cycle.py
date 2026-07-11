"""POST /api/run-cycle -- Phase 4: the real thing, no longer a stub.

query memory -> agent decides -> engine executes -> ledger + memory both update.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from agents.orchestrator import run_cycle
from api.deps import get_memory_client, get_session
from api.schemas import NodeTraceOut, RunCycleOut, RunCycleRequest
from memory.client import SupermemoryClient

router = APIRouter(prefix="/api/run-cycle", tags=["cycle"])


@router.post("", response_model=RunCycleOut)
def run_cycle_endpoint(
    request: RunCycleRequest,
    session: Session = Depends(get_session),
    memory_client: SupermemoryClient = Depends(get_memory_client),
):
    try:
        result = run_cycle(
            session,
            memory_client,
            symbol=request.symbol,
            run_id=request.run_id,
            initial_cash=request.initial_cash,
            as_of=request.as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RunCycleOut(
        run_id=result.run_id,
        symbol=result.symbol,
        action=result.decision.action.value,
        size=result.decision.size,
        rationale=result.decision.rationale,
        confidence=result.decision.confidence,
        regime=result.market_analysis.regime.value,
        regime_summary=result.market_analysis.summary,
        trade_id=result.trade.id if result.trade else None,
        executed_price=result.trade.price if result.trade else None,
        equity=result.snapshot.equity,
        memories_considered=result.memories_considered,
        memory_write_id=result.memory_write_id,
        reasoning_trail=[
            NodeTraceOut(node=entry["node"], output=entry["raw_output"]) for entry in result.reasoning_trail
        ],
    )
