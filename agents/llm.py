"""Thin LLM client wrapper -- independent of the Supermemory server's own
(currently broken) memory-agent LLM call. This is our own direct call for
agent reasoning, via Groq's OpenAI-compatible endpoint.

Verified empirically before building anything on top of it: JSON mode
(`response_format={"type": "json_object"}`) works cleanly with
`llama-3.1-8b-instant` through the standard `openai` SDK pointed at Groq.
"""

from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = "llama-3.1-8b-instant"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def get_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def complete_json(client: OpenAI, *, system: str, user: str, model: str = DEFAULT_MODEL, temperature: float = 0.2) -> str:
    """One JSON-mode completion call. Returns the raw content string --
    callers are responsible for parsing/validating it against their schema."""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return response.choices[0].message.content
