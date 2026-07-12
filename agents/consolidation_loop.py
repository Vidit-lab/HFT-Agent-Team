"""Phase 7: the batch process that drives agents/consolidation.py across the
raw lessons already in Supermemory. Deliberately separate and on-demand (via
POST /api/consolidate), the same shape as the reflection loop.

Grouping is deterministic: lessons are bucketed by (regime, outcome) -- the
dimensions LessonMemory actually persists -- and any bucket with at least
`min_group_size` lessons is consolidated. Idempotency is a `group_signature`
(a hash of the bucket's sorted source document ids) stored on every
Consolidation row: a bucket whose exact membership was already consolidated is
skipped, so re-running is safe and only newly-grown buckets produce new
meta-lessons.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from agents.consolidation import consolidate
from memory.client import SupermemoryClient
from memory.schemas import ConsolidatedLessonMemory, MemoryType, Outcome
from sim.models import Consolidation

DEFAULT_MIN_GROUP_SIZE = 2
DEFAULT_MAX_GROUPS = 20
_UNKNOWN = "unclassified"


@dataclass
class RawLesson:
    memory_id: str
    text: str
    regime: str
    outcome: str
    strategy: str
    asset: str | None


@dataclass
class ConsolidationResult:
    consolidated_memory_id: str
    regime: str
    outcome: str
    meta_lesson: str
    source_memory_ids: list[str]
    source_count: int
    confidence: float


def _group_signature(regime: str, outcome: str, source_ids: list[str]) -> str:
    payload = f"{regime}|{outcome}|" + "|".join(sorted(source_ids))
    return hashlib.sha256(payload.encode()).hexdigest()


def _fetch_raw_lessons(memory_client: SupermemoryClient, limit: int) -> list[RawLesson]:
    docs = memory_client.list_documents(limit=limit, include_content=True)
    lessons: list[RawLesson] = []
    for m in docs.memories:
        metadata = m.metadata or {}
        if metadata.get("type") != MemoryType.LESSON.value:
            continue
        text = (m.content or "").strip()
        if not text:
            continue
        lessons.append(
            RawLesson(
                memory_id=m.id,
                text=text,
                regime=str(metadata.get("regime", _UNKNOWN)),
                outcome=str(metadata.get("outcome", _UNKNOWN)),
                strategy=str(metadata.get("strategy", "agent_graph_v1")),
                asset=metadata.get("asset"),
            )
        )
    return lessons


def _bucket(lessons: list[RawLesson]) -> dict[tuple[str, str], list[RawLesson]]:
    buckets: dict[tuple[str, str], list[RawLesson]] = {}
    for lesson in lessons:
        buckets.setdefault((lesson.regime, lesson.outcome), []).append(lesson)
    return buckets


def _outcome_or_none(outcome: str) -> Outcome | None:
    try:
        return Outcome(outcome)
    except ValueError:
        return None


def run_consolidation_batch(
    session: Session,
    memory_client: SupermemoryClient,
    *,
    scope: str = "all",
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
    max_groups: int = DEFAULT_MAX_GROUPS,
    fetch_limit: int = 200,
    llm_client=None,
) -> list[ConsolidationResult]:
    lessons = _fetch_raw_lessons(memory_client, fetch_limit)
    buckets = _bucket(lessons)

    results: list[ConsolidationResult] = []
    groups_done = 0

    for (regime, outcome), group in buckets.items():
        if groups_done >= max_groups:
            break
        if len(group) < min_group_size:
            continue

        source_ids = [lesson.memory_id for lesson in group]
        signature = _group_signature(regime, outcome, source_ids)

        already = session.exec(
            select(Consolidation).where(Consolidation.group_signature == signature)
        ).first()
        if already is not None:
            continue  # this exact bucket membership was already consolidated

        output = consolidate([lesson.text for lesson in group], regime, outcome, client=llm_client)
        groups_done += 1

        strategy = group[0].strategy
        asset = next((lesson.asset for lesson in group if lesson.asset), None)
        outcome_enum = _outcome_or_none(outcome)

        for meta in output.consolidated:
            meta_source_ids = [source_ids[i] for i in meta.source_indices] or source_ids

            consolidated_memory_id = memory_client.write_consolidated_lesson(
                ConsolidatedLessonMemory(
                    strategy=strategy,
                    regime=regime,
                    meta_lesson=meta.meta_lesson,
                    outcome=outcome_enum,
                    asset=asset,
                    source_count=len(meta_source_ids),
                    confidence=meta.confidence,
                )
            )

            session.add(
                Consolidation(
                    created_at=datetime.now(timezone.utc),
                    scope=scope,
                    group_signature=signature,
                    regime=regime,
                    outcome=outcome,
                    meta_lesson=meta.meta_lesson,
                    consolidated_memory_id=consolidated_memory_id,
                    source_memory_ids=json.dumps(meta_source_ids),
                    source_count=len(meta_source_ids),
                    confidence=meta.confidence,
                )
            )
            session.commit()

            results.append(
                ConsolidationResult(
                    consolidated_memory_id=consolidated_memory_id,
                    regime=regime,
                    outcome=outcome,
                    meta_lesson=meta.meta_lesson,
                    source_memory_ids=meta_source_ids,
                    source_count=len(meta_source_ids),
                    confidence=meta.confidence,
                )
            )

    return results
