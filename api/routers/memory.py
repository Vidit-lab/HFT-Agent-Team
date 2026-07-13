"""Memory Explorer endpoints (Phase 7). Everything the frontend needs to show
how AlphaMemoir uses Supermemory: the raw document store, live semantic search,
the learning-provenance graph (reflection + consolidation edges, id-traceable
through our own tables), and aggregate stats. Read-only.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from api.deps import get_memory_client, get_session
from api.schemas import (
    ConsolidationRowOut,
    ConsolidationsOut,
    GraphEdgeOut,
    GraphNodeOut,
    MemoryDocumentOut,
    MemoryDocumentsOut,
    MemoryGraphOut,
    MemorySearchOut,
    MemorySearchResultOut,
    MemoryStatsOut,
    ReflectionRowOut,
    ReflectionsOut,
)
from memory.client import SupermemoryClient, and_filters
from sim.models import AgentDecisionLog, Consolidation, Reflection, Trade

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _snippet(text: str | None, n: int = 90) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


_FETCH_CAP = 500


@router.get("/documents", response_model=MemoryDocumentsOut)
def list_memory_documents(
    type: str | None = Query(None, description="Filter by memory type"),
    limit: int = Query(200, ge=1, le=500),
    client: SupermemoryClient = Depends(get_memory_client),
):
    """`limit` caps the documents RETURNED, applied *after* the type filter --
    not the raw fetch. (Capping the fetch first meant a small limit could filter
    down to zero: e.g. ?limit=5&type=lesson fetched 5 arbitrary docs and returned
    none of them.) `counts_by_type` is always computed over the whole container
    so the UI's filter chips show true totals, not just what this page returned.
    """
    docs = client.list_documents(limit=_FETCH_CAP, include_content=True)
    memories = getattr(docs, "memories", []) or []

    counts: dict[str, int] = {}
    out: list[MemoryDocumentOut] = []
    for m in memories:
        meta = dict(m.metadata or {})
        mtype = str(meta.get("type", "unknown"))
        counts[mtype] = counts.get(mtype, 0) + 1
        if type and mtype != type:
            continue
        created = getattr(m, "created_at", None)
        out.append(
            MemoryDocumentOut(
                id=m.id,
                type=mtype,
                title=getattr(m, "title", None),
                content=getattr(m, "content", None),
                status=getattr(m, "status", "unknown"),
                metadata=meta,
                created_at=str(created) if created else None,
            )
        )

    out = out[:limit]
    return MemoryDocumentsOut(total=len(out), counts_by_type=counts, documents=out)


@router.get("/documents/{document_id}", response_model=MemoryDocumentOut)
def get_memory_document(
    document_id: str,
    client: SupermemoryClient = Depends(get_memory_client),
):
    """One full document, for the Memory Explorer's detail view -- search only
    ever returns a matching *chunk*, so opening a result needs the parent doc."""
    try:
        m = client.get_document(document_id)
    except Exception as exc:  # noqa: BLE001 -- surface a clean 404 to the UI
        raise HTTPException(status_code=404, detail=f"No document {document_id}") from exc

    meta = dict(getattr(m, "metadata", None) or {})
    created = getattr(m, "created_at", None)
    return MemoryDocumentOut(
        id=m.id,
        type=str(meta.get("type", "unknown")),
        title=getattr(m, "title", None),
        content=getattr(m, "content", None),
        status=getattr(m, "status", "unknown"),
        metadata=meta,
        created_at=str(created) if created else None,
    )


@router.get("/search", response_model=MemorySearchOut)
def search_memory(
    q: str = Query(..., min_length=1, description="Natural-language query"),
    type: str | None = Query(None, description="Restrict to one memory type"),
    limit: int = Query(10, ge=1, le=30),
    client: SupermemoryClient = Depends(get_memory_client),
):
    filters = and_filters(type=type) if type else None
    response = client.query_similar(q, filters=filters, limit=limit, search_mode="hybrid")

    results: list[MemorySearchResultOut] = []
    for r in response.results:
        meta = dict(getattr(r, "metadata", None) or {})
        documents = getattr(r, "documents", None)
        document_id = documents[0].id if documents else r.id
        results.append(
            MemorySearchResultOut(
                id=r.id,
                document_id=document_id,
                type=meta.get("type"),
                content=getattr(r, "chunk", None) or getattr(r, "memory", None) or "",
                similarity=float(getattr(r, "similarity", 0.0) or 0.0),
                metadata=meta,
            )
        )

    return MemorySearchOut(query=q, count=len(results), results=results)


@router.get("/stats", response_model=MemoryStatsOut)
def memory_stats(
    session: Session = Depends(get_session),
    client: SupermemoryClient = Depends(get_memory_client),
):
    docs = client.list_documents(limit=500, include_content=False)
    memories = getattr(docs, "memories", []) or []
    counts: dict[str, int] = {}
    for m in memories:
        mtype = str((m.metadata or {}).get("type", "unknown"))
        counts[mtype] = counts.get(mtype, 0) + 1

    trades = session.exec(select(Trade)).all()
    closed = [t for t in trades if t.realized_pnl is not None]
    wins = [t for t in closed if (t.realized_pnl or 0) > 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

    return MemoryStatsOut(
        total_memories=len(memories),
        counts_by_type=counts,
        total_trades=len(trades),
        closed_trades=len(closed),
        win_rate=round(win_rate, 1),
        total_reflections=len(session.exec(select(Reflection)).all()),
        total_consolidations=len(session.exec(select(Consolidation)).all()),
    )


@router.get("/graph", response_model=MemoryGraphOut)
def memory_graph(
    session: Session = Depends(get_session),
    client: SupermemoryClient = Depends(get_memory_client),
):
    """The learning-provenance graph. Nodes are trades, lessons, and
    consolidated meta-lessons; edges are the real, id-traceable relationships:
    source lessons → the meta-lesson that consolidated them, a trade → the
    lesson reflection distilled from it, and a past lesson → a later trade whose
    decision actually cited it (memory changing a future decision).

    Lesson and consolidated nodes are read from Supermemory (the durable store),
    so the graph is complete even when the local ledger only holds a subset of
    the reflection/consolidation history; edges come from our own tables."""
    nodes: dict[str, GraphNodeOut] = {}
    edges: list[GraphEdgeOut] = []

    # Lesson + consolidated nodes from Supermemory (ids match the edge ids below).
    docs = client.list_documents(limit=500, include_content=True)
    for m in getattr(docs, "memories", []) or []:
        meta = dict(m.metadata or {})
        mtype = meta.get("type")
        if mtype == "lesson":
            nodes[m.id] = GraphNodeOut(
                id=m.id, kind="lesson", label=_snippet(getattr(m, "content", None) or getattr(m, "title", "")),
                regime=meta.get("regime"), outcome=meta.get("outcome"),
            )
        elif mtype == "consolidated_lesson":
            nodes[m.id] = GraphNodeOut(
                id=m.id, kind="consolidated", label=_snippet(getattr(m, "content", None) or getattr(m, "title", "")),
                regime=meta.get("regime"), outcome=meta.get("outcome"),
                detail=f"{meta.get('source_count', '?')} lessons consolidated",
            )

    trades = {t.id: t for t in session.exec(select(Trade)).all()}
    reflections = session.exec(select(Reflection)).all()
    consolidations = session.exec(select(Consolidation)).all()
    decision_logs = session.exec(select(AgentDecisionLog)).all()

    def trade_node(tid: int) -> str | None:
        node_id = f"trade:{tid}"
        if tid not in trades:
            return None
        if node_id not in nodes:
            t = trades[tid]
            nodes[node_id] = GraphNodeOut(
                id=node_id, kind="trade", label=f"Trade #{tid} · {t.side.value} {t.symbol}",
                regime=t.regime_at_entry, detail=t.rationale_summary,
            )
        return node_id

    # consolidated_into: source lessons -> meta-lesson
    for c in consolidations:
        try:
            source_ids = json.loads(c.source_memory_ids)
        except (json.JSONDecodeError, TypeError):
            source_ids = []
        for sid in source_ids:
            if sid in nodes and c.consolidated_memory_id in nodes:
                edges.append(GraphEdgeOut(source=sid, target=c.consolidated_memory_id, kind="consolidated_into"))

    # reflected_from: trade -> lesson
    for r in reflections:
        tnode = trade_node(r.trade_id)
        if tnode and r.lesson_memory_id in nodes:
            edges.append(GraphEdgeOut(source=tnode, target=r.lesson_memory_id, kind="reflected_from"))

    # cited_by: a lesson retrieved into a later trade's decision
    lesson_ids = {n.id for n in nodes.values() if n.kind in ("lesson", "consolidated")}
    for log in decision_logs:
        if not log.trade_id:
            continue
        try:
            retrieved = json.loads(log.retrieved_memory_ids)
        except (json.JSONDecodeError, TypeError):
            retrieved = []
        tnode = trade_node(log.trade_id)
        for mem_id in retrieved:
            if mem_id in lesson_ids and tnode:
                edges.append(GraphEdgeOut(source=mem_id, target=tnode, kind="cited_by"))

    return MemoryGraphOut(nodes=list(nodes.values()), edges=edges)


@router.get("/reflections", response_model=ReflectionsOut)
def list_reflections(session: Session = Depends(get_session)):
    rows = session.exec(select(Reflection).order_by(Reflection.id.desc())).all()
    return ReflectionsOut(total=len(rows), reflections=[ReflectionRowOut.model_validate(r) for r in rows])


@router.get("/consolidations", response_model=ConsolidationsOut)
def list_consolidations(session: Session = Depends(get_session)):
    rows = session.exec(select(Consolidation).order_by(Consolidation.id.desc())).all()
    return ConsolidationsOut(total=len(rows), consolidations=[ConsolidationRowOut.model_validate(r) for r in rows])
