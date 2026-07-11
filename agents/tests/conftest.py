"""A fake OpenAI-shaped client for testing agents/trader.py's prompt-building
and retry logic without any network call. Mimics just enough of the real
`openai` SDK's response shape (`.chat.completions.create(...).choices[0]
.message.content`) that agents/llm.complete_json works against it unmodified.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()


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


class FakeChatCompletions:
    def __init__(self, responses: list[str]):
        self._responses = iter(responses)

    def create(self, **kwargs):
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
