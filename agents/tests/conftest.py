"""A fake OpenAI-shaped client for testing agents/trader.py's prompt-building
and retry logic without any network call. Mimics just enough of the real
`openai` SDK's response shape (`.chat.completions.create(...).choices[0]
.message.content`) that agents/llm.complete_json works against it unmodified.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(autouse=True)
def _skip_live_without_key(request):
    if "live" in request.keywords and not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set; skipping live LLM test")


def make_bars(n: int = 25, start_price: float = 100.0) -> pd.DataFrame:
    """Small deterministic OHLCV frame for prompt-building tests -- doesn't
    need to be realistic, just shaped right."""
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    closes = [start_price + i * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1_000_000] * n,
        }
    )


def make_memory(chunk: str, **metadata) -> SimpleNamespace:
    """A fake retrieved-memory object shaped like what SupermemoryClient.query_similar
    returns (`.chunk`, `.metadata`, `.id`) -- used across agent node tests that need
    to hand the LLM some retrieved memory without a real Supermemory server."""
    return SimpleNamespace(chunk=chunk, metadata=metadata, id=metadata.get("id", "mem-1"))


class FakeChatCompletions:
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = next(self._responses)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeClient:
    def __init__(self, responses: list[str]):
        self.chat = SimpleNamespace(completions=FakeChatCompletions(responses))


def make_fake_client(*responses: str) -> FakeClient:
    return FakeClient(list(responses))


@pytest.fixture
def fake_client():
    return make_fake_client


class DispatchFakeClient:
    """A fake OpenAI-shaped client that routes each `.create()` call to a
    canned response based on a substring match against the *system* prompt,
    rather than call order. LangGraph's parallel fan-out (Bull/Bear both run
    in the same superstep) doesn't guarantee call order, so a plain queue
    (see FakeClient above) isn't safe for multi-node graph tests -- this is.
    """

    def __init__(self, *, default: str | None = None):
        self._rules: list[tuple[str, str]] = []
        self._default = default
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def when(self, system_prompt_substring: str, response: str) -> "DispatchFakeClient":
        self._rules.append((system_prompt_substring, response))
        return self

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs["messages"][0]["content"]
        for substring, response in self._rules:
            if substring in system:
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))])
        if self._default is not None:
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._default))])
        raise AssertionError(f"DispatchFakeClient: no rule matched system prompt: {system[:200]!r}")


@pytest.fixture
def dispatch_fake_client():
    return DispatchFakeClient


def make_document(id: str, content: str, **metadata) -> SimpleNamespace:
    """A fake document shaped like what SupermemoryClient.list_documents returns
    (`.id`, `.content`, `.metadata`) -- used by consolidation-loop tests."""
    return SimpleNamespace(id=id, content=content, metadata=metadata)


class FakeMemoryClient:
    """A fake SupermemoryClient double for graph-level tests -- returns
    `results_by_call` in order (one list of fake memories per query_similar
    call), so a test can script what each node's retrieval sees without a
    real Supermemory server. `documents` scripts what list_documents returns
    (for consolidation tests)."""

    def __init__(self, results_by_call: list[list] | None = None, documents: list | None = None):
        self._results = iter(results_by_call or [])
        self._default: list = []
        self._documents = documents or []
        self.calls: list[dict] = []
        self.consolidated_writes: list = []
        self._consolidated_counter = 0

    def query_similar(self, q: str, *, filters=None, limit: int = 10, search_mode: str = "hybrid"):
        self.calls.append({"q": q, "filters": filters, "limit": limit})
        results = next(self._results, self._default)
        return SimpleNamespace(results=results)

    def list_documents(self, limit: int = 50, include_content: bool = True):
        return SimpleNamespace(memories=self._documents)

    def write_regime_snapshot(self, *_args, **_kwargs) -> str:
        return "fake-regime-id"

    def write_trade_memory(self, *_args, **_kwargs) -> str:
        return "fake-trade-memory-id"

    def write_lesson(self, *_args, **_kwargs) -> str:
        return "fake-lesson-id"

    def write_consolidated_lesson(self, consolidated) -> str:
        self.consolidated_writes.append(consolidated)
        self._consolidated_counter += 1
        return f"fake-consolidated-id-{self._consolidated_counter}"


@pytest.fixture
def db_session(tmp_path):
    from sqlmodel import Session, SQLModel, create_engine

    from sim import models  # noqa: F401 -- registers table metadata

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
