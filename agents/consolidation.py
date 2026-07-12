"""Phase 7: the Consolidation Agent -- distills a group of related raw lessons
(sharing a regime + outcome) into one or more higher-order "meta-lessons," and
tracks which raw lessons each was distilled from.

Why this exists as our own agent rather than Supermemory's server-side one:
the self-hosted binary's memory-agent (which would normally consolidate) makes
its LLM calls on Groq's paid `flex` service tier, so on the free tier it never
runs (full diagnosis in memory_explorer.md). Rather than depend on it, we do the
consolidation ourselves through the same Groq `on_demand` client every other
agent already uses (agents/llm.py), and write the results back into Supermemory
as first-class, retrievable `ConsolidatedLessonMemory` documents. Supermemory
stays the storage + semantic-retrieval + embedding backbone; the consolidation
intelligence is ours and fully in our control.

Like the Reflection Agent, the LLM's job is bounded: it only distills text. The
grouping (which lessons go together) is deterministic and done in the loop, and
the connection edges are recorded in SQLite -- the LLM never decides membership
or persistence, only phrasing.
"""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from agents.llm import DEFAULT_MODEL, complete_json, get_client
from agents.schemas import ConsolidationOutput

SYSTEM_PROMPT = """You are the Consolidation Agent for a paper-trading memory system. You are given a \
numbered list of individual lessons that all come from the same market regime and outcome. Your job \
is to distil them into a SMALL number (usually 1-3) of higher-order "meta-lessons" that capture the \
shared, generalizable insight across the group -- merging duplicates and near-duplicates, and \
combining complementary points into a single stronger rule. Each meta-lesson must be genuinely more \
general than any single source lesson, not a copy of one. For each meta-lesson, list the 0-based \
indices of the source lessons it was distilled from. Respond with ONLY a JSON object matching this \
schema, no other text:
{"consolidated": [{"meta_lesson": string (1-3 sentences, generalizable), "source_indices": [int, ...], \
"confidence": number between 0 and 1}]}"""


def build_prompt(lesson_texts: list[str], regime: str, outcome: str) -> str:
    numbered = "\n".join(f"[{i}] {text}" for i, text in enumerate(lesson_texts))
    return (
        f"Regime: {regime}. Outcome across this group: {outcome}.\n"
        f"Lessons to consolidate ({len(lesson_texts)}):\n{numbered}\n\n"
        "Distil these into higher-order meta-lessons."
    )


def consolidate(
    lesson_texts: list[str],
    regime: str,
    outcome: str,
    *,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
) -> ConsolidationOutput:
    """Distil a group of raw lessons into higher-order meta-lessons. Retries on
    invalid JSON, appending the error -- same robustness pattern as reflect()."""
    client = client or get_client()
    user_prompt = build_prompt(lesson_texts, regime, outcome)

    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        raw = complete_json(client, system=SYSTEM_PROMPT, user=user_prompt, model=model)
        try:
            output = ConsolidationOutput.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            user_prompt += (
                f"\n\nYour previous response was invalid: {exc}. "
                "Respond again with ONLY valid JSON matching the schema."
            )
            continue

        # Guard against the LLM referencing lessons that weren't in the prompt.
        n = len(lesson_texts)
        for lesson in output.consolidated:
            lesson.source_indices = [i for i in lesson.source_indices if 0 <= i < n]
        return output

    raise RuntimeError(
        f"LLM failed to produce a valid ConsolidationOutput after {max_retries + 1} attempts: {last_error}"
    )
