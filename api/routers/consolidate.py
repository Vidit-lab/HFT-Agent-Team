"""POST /api/consolidate -- Phase 7: on-demand trigger for the Consolidation
Agent batch. Groups the raw lessons already in Supermemory by (regime, outcome)
and distils each bucket into higher-order meta-lessons, written back into
Supermemory and recorded (with their source edges) in the Consolidation table.
Deliberately separate from POST /api/reflect; see agents/consolidation_loop.py.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from agents.consolidation_loop import run_consolidation_batch
from api.deps import get_memory_client, get_session
from api.schemas import ConsolidateOut, ConsolidateRequest, ConsolidationOut
from memory.client import SupermemoryClient

router = APIRouter(prefix="/api/consolidate", tags=["consolidate"])


@router.post("", response_model=ConsolidateOut)
def consolidate_endpoint(
    request: ConsolidateRequest,
    session: Session = Depends(get_session),
    memory_client: SupermemoryClient = Depends(get_memory_client),
):
    results = run_consolidation_batch(
        session,
        memory_client,
        scope=request.scope,
        min_group_size=request.min_group_size,
        max_groups=request.max_groups,
    )

    return ConsolidateOut(
        consolidated_count=len(results),
        consolidations=[
            ConsolidationOut(
                consolidated_memory_id=r.consolidated_memory_id,
                regime=r.regime,
                outcome=r.outcome,
                meta_lesson=r.meta_lesson,
                source_memory_ids=r.source_memory_ids,
                source_count=r.source_count,
                confidence=r.confidence,
            )
            for r in results
        ],
    )
