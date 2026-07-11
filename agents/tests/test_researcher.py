from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.researcher import build_prompt, document_id, research, retrieve_memories
from agents.schemas import MarketAnalysis, Regime, ResearchThesis, Stance

from .conftest import FakeMemoryClient, make_bars, make_fake_client, make_memory

_ANALYSIS = MarketAnalysis(regime=Regime.TRENDING_UP, summary="steady climb", confidence=0.8)


def test_document_id_uses_parent_document_id_when_present():
    # Search results are chunk-level; result.id alone is a chunk id in a
    # different namespace from what write_lesson()/write_trade_memory()
    # returns -- result.documents[0].id is the one that's actually traceable.
    result = SimpleNamespace(id="chunk-abc", documents=[SimpleNamespace(id="doc-xyz")])
    assert document_id(result) == "doc-xyz"


def test_document_id_falls_back_to_result_id_without_documents():
    result = make_memory("no documents field on this fake", type="lesson")
    assert document_id(result) == result.id


def test_build_prompt_includes_regime_and_memories():
    prompt = build_prompt("AAPL", make_bars(), _ANALYSIS, [make_memory("won big", type="trade")], Stance.BULL)
    assert "trending_up" in prompt
    assert "won big" in prompt
    assert "Make your case." in prompt


def test_retrieve_memories_bull_filters_on_win_outcome():
    memory_client = FakeMemoryClient(results_by_call=[[make_memory("a win", type="trade")], []])
    result = retrieve_memories(memory_client, "AAPL", Stance.BULL)

    assert len(result.results) == 1
    assert len(memory_client.calls) == 2
    assert memory_client.calls[0]["filters"]["AND"] == [
        {"key": "asset", "value": "AAPL", "filterType": "metadata"},
        {"key": "outcome", "value": "win", "filterType": "metadata"},
    ]
    assert memory_client.calls[1]["filters"] is None


def test_retrieve_memories_bear_filters_on_loss_outcome():
    memory_client = FakeMemoryClient(results_by_call=[[make_memory("a loss", type="trade")], []])
    retrieve_memories(memory_client, "AAPL", Stance.BEAR)

    assert memory_client.calls[0]["filters"]["AND"][1] == {
        "key": "outcome",
        "value": "loss",
        "filterType": "metadata",
    }


def test_retrieve_memories_merges_filtered_and_unfiltered_results():
    memory_client = FakeMemoryClient(results_by_call=[[], [make_memory("anything", type="trade")]])
    result = retrieve_memories(memory_client, "AAPL", Stance.BULL)

    assert len(result.results) == 1
    assert len(memory_client.calls) == 2
    assert memory_client.calls[0]["filters"] is not None
    assert memory_client.calls[1]["filters"] is None


def test_retrieve_memories_dedupes_ids_present_in_both_queries():
    shared = make_memory("shared", type="trade", id="mem-1")
    only_unfiltered = make_memory("unique", type="trade", id="mem-2")
    memory_client = FakeMemoryClient(results_by_call=[[shared], [shared, only_unfiltered]])
    result = retrieve_memories(memory_client, "AAPL", Stance.BULL)

    assert [m.id for m in result.results] == ["mem-1", "mem-2"]


def test_retrieve_memories_caps_merged_results_at_limit():
    filtered = [make_memory(f"f{i}", type="trade", id=f"f{i}") for i in range(3)]
    unfiltered = [make_memory(f"u{i}", type="trade", id=f"u{i}") for i in range(3)]
    memory_client = FakeMemoryClient(results_by_call=[filtered, unfiltered])
    result = retrieve_memories(memory_client, "AAPL", Stance.BULL, limit=4)

    assert len(result.results) == 4
    assert [m.id for m in result.results] == ["f0", "f1", "f2", "u0"]


def test_research_parses_valid_bull_response():
    client = make_fake_client('{"stance": "bull", "thesis": "strong momentum", "confidence": 0.7}')
    thesis, system_prompt, user_prompt = research("AAPL", make_bars(), _ANALYSIS, [], Stance.BULL, client=client)

    assert isinstance(thesis, ResearchThesis)
    assert thesis.stance == Stance.BULL
    assert "Bull Researcher" in system_prompt
    assert "AAPL" in user_prompt


def test_research_parses_valid_bear_response():
    client = make_fake_client('{"stance": "bear", "thesis": "overbought", "confidence": 0.6}')
    thesis, system_prompt, _ = research("AAPL", make_bars(), _ANALYSIS, [], Stance.BEAR, client=client)

    assert thesis.stance == Stance.BEAR
    assert "Bear Researcher" in system_prompt


def test_research_retries_when_stance_mismatches_the_assigned_role():
    client = make_fake_client(
        '{"stance": "bear", "thesis": "wrong side", "confidence": 0.5}',
        '{"stance": "bull", "thesis": "corrected", "confidence": 0.5}',
    )
    thesis, _, _ = research("AAPL", make_bars(), _ANALYSIS, [], Stance.BULL, client=client, max_retries=1)
    assert thesis.stance == Stance.BULL
    assert thesis.thesis == "corrected"


def test_research_raises_after_exhausting_retries():
    client = make_fake_client("bad", "still bad", "still bad")
    with pytest.raises(RuntimeError):
        research("AAPL", make_bars(), _ANALYSIS, [], Stance.BULL, client=client, max_retries=2)


@pytest.mark.live
def test_research_with_real_llm_returns_well_formed_thesis():
    thesis, _, _ = research("AAPL", make_bars(n=30), _ANALYSIS, [], Stance.BEAR)
    assert isinstance(thesis, ResearchThesis)
    assert thesis.stance == Stance.BEAR
    assert thesis.thesis
    assert 0.0 <= thesis.confidence <= 1.0
