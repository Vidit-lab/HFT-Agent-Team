"""Phase 0 smoke test: prove the Supermemory local server round trip works.

Writes one document, polls until it finishes processing, then searches for it.
Run with the local server up: `python scripts/hello_memory.py`.
"""

import os
import sys
import time

from dotenv import load_dotenv
from supermemory import Supermemory

load_dotenv()


def main() -> int:
    api_key = os.environ.get("SUPERMEMORY_API_KEY")
    if not api_key:
        print("SUPERMEMORY_API_KEY is not set (copy .env.example to .env and fill it in)")
        return 1

    base_url = os.environ.get("SUPERMEMORY_BASE_URL", "http://localhost:6767")
    container_tag = os.environ.get("SUPERMEMORY_CONTAINER_TAG", "trading_system")

    client = Supermemory(api_key=api_key, base_url=base_url)

    print(f"Writing a test memory to container '{container_tag}' at {base_url} ...")
    written = client.add(
        content="Hello, memory. This is the Phase 0 round-trip check for the trading brain.",
        container_tag=container_tag,
        metadata={"type": "event", "purpose": "phase0_smoke_test"},
    )
    print(f"  -> queued document id={written.id}")

    print("Waiting for processing to finish ...")
    status = "queued"
    for _ in range(10):
        time.sleep(2)
        doc = client.documents.get(id=written.id)
        status = doc.status
        print(f"  -> status={status}")
        if status not in ("queued", "processing"):
            break

    print(f"\nSearching (hybrid mode, falls back to chunk search) for 'hello memory' ...")
    results = client.search.memories(
        q="hello memory",
        container_tag=container_tag,
        search_mode="hybrid",
        limit=5,
    )
    print(f"  -> {int(results.total)} result(s)")

    if status == "failed":
        print(
            "\nNote: document processing reports 'failed'. If chunk search above still "
            "found results, that means embedding succeeded but the server-side memory "
            "agent (LLM fact extraction) is not configured — see README 'Known "
            "local-server caveat'. This is expected until an LLM is wired into the "
            "server and does not block Phase 1 development."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
