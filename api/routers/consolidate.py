"""POST /api/consolidate -- Phase 7: on-demand trigger for the Consolidation
Agent batch. Groups the raw lessons already in Supermemory by (regime, outcome)
and distils each bucket into higher-order meta-lessons, written back into
Supermemory and recorded (with their source edges) in the Consolidation table.
Deliberately separate from POST /api/reflect; see agents/consolidation_loop.py.
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from agents.consolidation_loop import (
    DEFAULT_MIN_GROUP_SIZE,
    _bucket,
    _fetch_raw_lessons,
    _group_signature,
    run_consolidation_batch,
)
from api.deps import get_memory_client, get_session
from api.schemas import (
    ConsolidateOut,
    ConsolidateRequest,
    ConsolidationOut,
    PendingBucketOut,
    PendingConsolidationOut,
)
from memory.client import SupermemoryClient
from sim.models import Consolidation

router = APIRouter(prefix="/api/consolidate", tags=["consolidate"])


@router.get("/pending", response_model=PendingConsolidationOut)
def pending_consolidation(
    min_group_size: int = Query(DEFAULT_MIN_GROUP_SIZE, ge=2),
    session: Session = Depends(get_session),
    memory_client: SupermemoryClient = Depends(get_memory_client),
):
    """The raw lessons currently in Supermemory, bucketed by (regime, outcome) --
    the exact grouping the Consolidation Agent uses. A bucket is `ready` once it
    holds at least `min_group_size` lessons AND that exact membership hasn't been
    consolidated before (same group_signature idempotency key as the batch loop)."""
    lessons = _fetch_raw_lessons(memory_client, 200)
    buckets = _bucket(lessons)

    out: list[PendingBucketOut] = []
    for (regime, outcome), group in buckets.items():
        signature = _group_signature(regime, outcome, [lesson.memory_id for lesson in group])
        done = session.exec(
            select(Consolidation).where(Consolidation.group_signature == signature)
        ).first() is not None
        out.append(
            PendingBucketOut(
                regime=regime,
                outcome=outcome,
                lesson_count=len(group),
                ready=len(group) >= min_group_size and not done,
                already_consolidated=done,
            )
        )

    out.sort(key=lambda b: (not b.ready, -b.lesson_count))
    return PendingConsolidationOut(
        min_group_size=min_group_size,
        ready_count=sum(1 for b in out if b.ready),
        total_lessons=len(lessons),
        buckets=out,
    )


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
