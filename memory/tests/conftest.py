"""Shared fixtures for the memory/ integration tests.

These tests run against a real, live Supermemory server (no mocks -- the
engine's fact-extraction/contradiction-resolution behavior is exactly what
needs verifying and isn't meaningfully mockable). They're skipped, not
failed, when no server is reachable so the suite stays usable on machines
without the local binary running.
"""

from __future__ import annotations

import time
import uuid

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

from memory.client import SupermemoryClient  # noqa: E402


def _server_reachable(base_url: str) -> bool:
    try:
        httpx.get(base_url, timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_local_server():
    import os

    base_url = os.environ.get("SUPERMEMORY_BASE_URL", "http://localhost:6767")
    if not os.environ.get("SUPERMEMORY_API_KEY"):
        pytest.skip("SUPERMEMORY_API_KEY not set; skipping live-server integration tests")
    if not _server_reachable(base_url):
        pytest.skip(f"Supermemory server not reachable at {base_url}; skipping integration tests")


@pytest.fixture(scope="module")
def client() -> SupermemoryClient:
    # Unique per test-module run so runs never collide with each other or
    # with manual dev poking at the default `trading_system` container.
    container_tag = f"trading_system_test_{uuid.uuid4().hex[:10]}"
    return SupermemoryClient(container_tag=container_tag)


def wait_for_processing(client: SupermemoryClient, expected_count: int, timeout: float = 180.0, interval: float = 5.0) -> int:
    """Poll until `expected_count` documents in the client's container have left the
    queued/processing state. Uses one bulk `documents.list` call per poll cycle
    rather than per-document status checks, so this stays cheap for large batches.
    Returns the number of documents observed as settled (status not queued/processing).
    """
    deadline = time.time() + timeout
    settled = 0
    while time.time() < deadline:
        page = client._sdk.documents.list(container_tags=[client.container_tag], limit=max(expected_count, 10))
        statuses = [m.status for m in page.memories]
        settled = sum(1 for s in statuses if s not in ("queued", "processing"))
        if settled >= expected_count:
            break
        time.sleep(interval)
    return settled
