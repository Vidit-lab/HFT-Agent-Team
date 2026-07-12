from __future__ import annotations

import pytest

from agents.consolidation import build_prompt, consolidate

from .conftest import make_fake_client

_VALID = (
    '{"consolidated": [{"meta_lesson": "In trending_up regimes, size up on strong conviction.", '
    '"source_indices": [0, 1], "confidence": 0.9}]}'
)


def test_build_prompt_numbers_lessons_and_names_the_group():
    prompt = build_prompt(["lesson A", "lesson B"], "trending_up", "win")
    assert "[0] lesson A" in prompt
    assert "[1] lesson B" in prompt
    assert "trending_up" in prompt
    assert "win" in prompt


def test_consolidate_parses_valid_output():
    client = make_fake_client(_VALID)
    out = consolidate(["a", "b"], "trending_up", "win", client=client)
    assert len(out.consolidated) == 1
    assert out.consolidated[0].source_indices == [0, 1]
    assert out.consolidated[0].confidence == 0.9


def test_consolidate_retries_on_invalid_json_then_succeeds():
    client = make_fake_client("not json", _VALID)
    out = consolidate(["a", "b"], "trending_up", "win", client=client)
    assert len(out.consolidated) == 1
    # the retry appended the error to the second user prompt
    assert "was invalid" in client.chat.completions.calls[1]["messages"][1]["content"]


def test_consolidate_raises_after_exhausting_retries():
    client = make_fake_client("bad", "bad", "bad")
    with pytest.raises(RuntimeError, match="failed to produce a valid ConsolidationOutput"):
        consolidate(["a", "b"], "trending_up", "win", client=client, max_retries=2)


def test_consolidate_drops_out_of_range_source_indices():
    # LLM references index 9 which wasn't in a 2-lesson prompt -- must be filtered out.
    resp = (
        '{"consolidated": [{"meta_lesson": "x", "source_indices": [0, 9, 1], "confidence": 0.5}]}'
    )
    out = consolidate(["a", "b"], "trending_up", "win", client=make_fake_client(resp))
    assert out.consolidated[0].source_indices == [0, 1]


@pytest.mark.live
def test_consolidate_live_produces_higher_order_lesson():
    out = consolidate(
        [
            "In trending_up regimes with a strong Bull thesis, sizing up tends to pay off.",
            "During AAPL uptrends, a confident Bull case justified sizing up to capture the move.",
        ],
        "trending_up",
        "win",
    )
    assert len(out.consolidated) >= 1
    assert out.consolidated[0].meta_lesson
    assert all(0 <= i < 2 for i in out.consolidated[0].source_indices)
