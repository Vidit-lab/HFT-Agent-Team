"""Integration tests against a live local Supermemory server.

Covers the Phase 1 definition of done: write a batch of synthetic trades +
lessons across multiple strategy/regime combinations, then retrieve
"lessons/trades for strategy=momentum in regime=high_vol_bull" and confirm
the metadata filter correctly isolates only matching records.

Uses search_mode="hybrid" (the client's default): the self-hosted memory
agent (LLM fact extraction into consolidated memories) has no LLM configured
in this environment, so "memories"-mode search returns nothing, but chunk
embedding + metadata filtering work regardless. See README for the caveat.
"""

from __future__ import annotations

from datetime import datetime, timezone

from memory.client import and_filters
from memory.schemas import LessonMemory, Outcome, Side, TradeMemory

from .conftest import wait_for_processing

STRATEGIES = ["momentum", "mean_reversion", "breakout"]
REGIMES = ["high_vol_bull", "low_vol_bull", "high_vol_bear"]

TARGET_STRATEGY = "momentum"
TARGET_REGIME = "high_vol_bull"


def test_write_and_retrieve_single_trade_memory(client):
    trade = TradeMemory(
        trade_id="single-trade-1",
        timestamp=datetime.now(timezone.utc),
        symbol="BTC",
        side=Side.BUY,
        size=0.5,
        price=60000,
        strategy=TARGET_STRATEGY,
        regime=TARGET_REGIME,
        outcome=Outcome.WIN,
        pnl=3.2,
        rationale="Breakout above resistance with volume confirmation.",
    )

    doc_id = client.write_trade_memory(trade)
    assert doc_id

    settled = wait_for_processing(client, expected_count=1, timeout=60)
    assert settled >= 1

    results = client.query_similar("breakout entry on BTC with volume confirmation")
    assert results.total >= 1
    assert any(r.metadata.get("trade_id") == "single-trade-1" for r in results.results)


def test_metadata_filtering_isolates_target_strategy_and_regime(client):
    written = 0
    expected_matches = 0

    for i in range(50):
        strategy = STRATEGIES[i % len(STRATEGIES)]
        regime = REGIMES[i % len(REGIMES)]
        is_match = strategy == TARGET_STRATEGY and regime == TARGET_REGIME
        if is_match:
            expected_matches += 1

        if i % 2 == 0:
            record = TradeMemory(
                trade_id=f"synthetic-trade-{i}",
                timestamp=datetime.now(timezone.utc),
                symbol="BTC",
                side=Side.BUY if i % 4 == 0 else Side.SELL,
                size=1.0,
                price=100.0 + i,
                strategy=strategy,
                regime=regime,
                outcome=Outcome.WIN if i % 3 == 0 else Outcome.LOSS,
                pnl=float(i % 7) - 3,
                rationale=f"Synthetic rationale for trade {i} under {strategy}/{regime}.",
            )
            client.write_trade_memory(record)
        else:
            record = LessonMemory(
                strategy=strategy,
                regime=regime,
                asset="BTC",
                outcome=Outcome.WIN,
                lesson_text=f"Synthetic lesson {i}: {strategy} entries behave predictably in {regime} regimes.",
            )
            client.write_lesson(record)
        written += 1

    assert written == 50
    assert expected_matches > 0

    settled = wait_for_processing(client, expected_count=written, timeout=180)
    assert settled >= written * 0.9, (
        f"only {settled}/{written} documents finished processing within the timeout"
    )

    results = client.query_similar(
        "trades and lessons about momentum strategy in a high volatility bull regime",
        filters=and_filters(strategy=TARGET_STRATEGY, regime=TARGET_REGIME),
        limit=50,
    )

    assert results.total > 0, "expected at least one filtered match"
    for result in results.results:
        assert result.metadata.get("strategy") == TARGET_STRATEGY
        assert result.metadata.get("regime") == TARGET_REGIME
