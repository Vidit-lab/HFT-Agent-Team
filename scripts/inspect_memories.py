"""Observability CLI: see exactly what's stored in Supermemory for a container.

The raw embedding vectors themselves aren't exposed by the API (they're
internal to the search engine's index) -- what you *can* see, and what this
tool shows, is: every document's processing status, its metadata, its stored
content, and (with --search) the ranked chunks + similarity scores a query
actually retrieves. That's the practical "how is this being stored and
retrieved" view during development.

Usage:
    python scripts/inspect_memories.py                          # list documents
    python scripts/inspect_memories.py --container trading_system
    python scripts/inspect_memories.py --search "momentum lessons in high vol"
    python scripts/inspect_memories.py --search "..." --mode memories
"""

from __future__ import annotations

import argparse
import os
import textwrap

from dotenv import load_dotenv

from memory.client import SupermemoryClient

load_dotenv()


def _truncate(text: str | None, width: int = 100) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ")
    return textwrap.shorten(text, width=width, placeholder="...")


def list_documents(client: SupermemoryClient, limit: int) -> None:
    response = client.list_documents(limit=limit)
    docs = response.memories

    counts: dict[str, int] = {}
    for doc in docs:
        counts[doc.status] = counts.get(doc.status, 0) + 1

    print(f"Container: {client.container_tag}")
    print(f"Documents: {len(docs)}  |  by status: {counts}\n")

    header = f"{'status':<10} {'type':<10} {'strategy':<14} {'regime':<16} {'id':<24} content"
    print(header)
    print("-" * len(header))
    for doc in docs:
        metadata = doc.metadata or {}
        print(
            f"{doc.status:<10} "
            f"{str(metadata.get('type', '')):<10} "
            f"{str(metadata.get('strategy', '')):<14} "
            f"{str(metadata.get('regime', '')):<16} "
            f"{doc.id:<24} "
            f"{_truncate(doc.content or doc.title)}"
        )


def search(client: SupermemoryClient, query: str, mode: str, limit: int) -> None:
    results = client.query_similar(query, search_mode=mode, limit=limit)
    print(f"Container: {client.container_tag}  |  mode: {mode}  |  query: {query!r}")
    print(f"Total results: {int(results.total)}  (search took {results.timing:.1f}ms)\n")

    for i, r in enumerate(results.results, start=1):
        print(f"[{i}] similarity={r.similarity:.4f}  metadata={r.metadata}")
        print(f"    {_truncate(r.chunk, width=140)}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--container",
        default=os.environ.get("SUPERMEMORY_CONTAINER_TAG", "trading_system"),
        help="Container tag to inspect (default: %(default)s)",
    )
    parser.add_argument("--search", dest="query", help="Run a search instead of listing documents")
    parser.add_argument(
        "--mode",
        choices=["memories", "hybrid", "documents"],
        default="hybrid",
        help="Search mode (default: %(default)s). 'memories' needs the LLM-based memory agent configured.",
    )
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    client = SupermemoryClient(container_tag=args.container)

    if args.query:
        search(client, args.query, args.mode, args.limit)
    else:
        list_documents(client, args.limit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
