from __future__ import annotations

import json

from sqlmodel import select

from agents.consolidation_loop import run_consolidation_batch
from sim.models import Consolidation

from .conftest import FakeMemoryClient, make_document, make_fake_client

_ONE_META = (
    '{"consolidated": [{"meta_lesson": "Higher-order rule for trending_up wins.", '
    '"source_indices": [0, 1], "confidence": 0.9}]}'
)


def _lessons(*texts, regime="trending_up", outcome="win"):
    return [
        make_document(f"mem-{i}", text, type="lesson", regime=regime, outcome=outcome, strategy="agent_graph_v1", asset="AAPL")
        for i, text in enumerate(texts)
    ]


def test_consolidates_a_bucket_and_records_edges(db_session):
    docs = _lessons("lesson one", "lesson two")
    mc = FakeMemoryClient(documents=docs)
    client = make_fake_client(_ONE_META)

    results = run_consolidation_batch(db_session, mc, llm_client=client)

    assert len(results) == 1
    assert results[0].source_count == 2
    assert results[0].source_memory_ids == ["mem-0", "mem-1"]

    rows = db_session.exec(select(Consolidation)).all()
    assert len(rows) == 1
    assert rows[0].consolidated_memory_id == "fake-consolidated-id-1"
    assert json.loads(rows[0].source_memory_ids) == ["mem-0", "mem-1"]
    assert rows[0].regime == "trending_up"
    assert rows[0].outcome == "win"


def test_bucket_below_min_group_size_is_skipped(db_session):
    mc = FakeMemoryClient(documents=_lessons("only one lesson"))
    results = run_consolidation_batch(db_session, mc, llm_client=make_fake_client(), min_group_size=2)
    assert results == []


def test_ignores_non_lesson_documents(db_session):
    docs = _lessons("lesson one", "lesson two") + [
        make_document("trade-1", "a trade", type="trade", regime="trending_up"),
        make_document("regime-1", "a snapshot", type="regime_snapshot", regime="trending_up"),
    ]
    mc = FakeMemoryClient(documents=docs)
    results = run_consolidation_batch(db_session, mc, llm_client=make_fake_client(_ONE_META))
    assert len(results) == 1
    assert results[0].source_memory_ids == ["mem-0", "mem-1"]  # only the two lessons


def test_separate_buckets_by_regime_and_outcome(db_session):
    docs = _lessons("up win a", "up win b", regime="trending_up", outcome="win") + _lessons(
        "down loss a", "down loss b", regime="trending_down", outcome="loss"
    )
    mc = FakeMemoryClient(documents=docs)
    client = make_fake_client(_ONE_META, _ONE_META)

    results = run_consolidation_batch(db_session, mc, llm_client=client)

    regimes = {(r.regime, r.outcome) for r in results}
    assert regimes == {("trending_up", "win"), ("trending_down", "loss")}


def test_idempotent_rerun_skips_already_consolidated_bucket(db_session):
    docs = _lessons("lesson one", "lesson two")

    run_consolidation_batch(db_session, FakeMemoryClient(documents=docs), llm_client=make_fake_client(_ONE_META))
    # exact same bucket membership -> second run produces nothing
    second = run_consolidation_batch(db_session, FakeMemoryClient(documents=docs), llm_client=make_fake_client(_ONE_META))

    assert second == []
    assert len(db_session.exec(select(Consolidation)).all()) == 1


def test_growing_a_bucket_changes_signature_and_reconsolidates(db_session):
    run_consolidation_batch(
        db_session, FakeMemoryClient(documents=_lessons("l1", "l2")), llm_client=make_fake_client(_ONE_META)
    )
    # a third lesson changes the bucket's signature -> eligible again
    grown = run_consolidation_batch(
        db_session, FakeMemoryClient(documents=_lessons("l1", "l2", "l3")), llm_client=make_fake_client(_ONE_META)
    )
    assert len(grown) == 1
    assert len(db_session.exec(select(Consolidation)).all()) == 2


def test_max_groups_caps_the_batch(db_session):
    docs = (
        _lessons("a1", "a2", regime="r1", outcome="win")
        + _lessons("b1", "b2", regime="r2", outcome="win")
        + _lessons("c1", "c2", regime="r3", outcome="win")
    )
    mc = FakeMemoryClient(documents=docs)
    results = run_consolidation_batch(db_session, mc, llm_client=make_fake_client(_ONE_META), max_groups=1)
    assert len({(r.regime, r.outcome) for r in results}) == 1
