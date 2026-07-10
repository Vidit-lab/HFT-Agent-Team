# Trading Brain

Memory-centric, self-improving multi-agent trading system built around
[Supermemory](https://supermemory.ai) as the semantic memory layer.

See [plan.md](plan.md) for the full phased roadmap and design rationale.

## Setup

1. Boot the Supermemory local server (binary listens on `http://localhost:6767`;
   prints an API key on first boot, cached at `~/.supermemory/api-key`).
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -e ".[dev]"`
4. `cp .env.example .env` and fill in `SUPERMEMORY_API_KEY` from step 1.
5. `python scripts/hello_memory.py` — verifies the write → search round trip
   against the local server.

## Known local-server caveat

The self-hosted "memory agent" (LLM-based fact extraction that turns raw text into
consolidated, queryable memories) requires an LLM to be configured on the
Supermemory server side. Without one, document chunks still embed and remain
searchable via `search_mode="hybrid"` or `"documents"`, but no consolidated
`memories` are extracted (`search_mode="memories"` returns empty results). You'll
see this in the server logs as:

```
[Workflow] Document <id> starting memory agent (1 chunks)
[Workflow] Document <id> memory agent failed (Nms)
WARN [Workflow] Self-hosted memory agent failed for document, skipping memory generation
```

This does not block development: `memory/client.py` defaults to `search_mode="hybrid"`
so retrieval degrades gracefully to chunk search either way, and will transparently
start returning richer consolidated memories once an LLM is wired into the server.
