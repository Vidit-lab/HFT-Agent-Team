"""Pure unit tests for memory record rendering -- no network involved."""

from datetime import datetime, timezone

from memory.schemas import (
    EventMemory,
    LessonMemory,
    Outcome,
    RegimeSnapshotMemory,
    Side,
    TradeMemory,
)


def test_trade_memory_content_and_metadata():
    trade = TradeMemory(
        trade_id="t-1",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        symbol="BTC",
        side=Side.BUY,
        size=0.5,
        price=60000,
        strategy="momentum",
        regime="high_vol_bull",
        outcome=Outcome.WIN,
        pnl=3.2,
        rationale="Breakout above resistance with volume confirmation.",
    )

    content = trade.to_content()
    assert "BTC" in content
    assert "momentum" in content
    assert "Breakout above resistance" in content

    metadata = trade.to_metadata()
    assert metadata == {
        "type": "trade",
        "trade_id": "t-1",
        "symbol": "BTC",
        "asset": "BTC",
        "side": "buy",
        "strategy": "momentum",
        "regime": "high_vol_bull",
        "outcome": "win",
        "pnl": 3.2,
    }


def test_lesson_memory_content_is_the_lesson_text():
    lesson = LessonMemory(
        strategy="momentum",
        regime="high_vol_bull",
        asset="BTC",
        outcome=Outcome.WIN,
        lesson_text="Momentum entries after 3+ green candles had strong follow-through.",
        source_trade_id="t-1",
    )

    assert lesson.to_content() == lesson.lesson_text
    metadata = lesson.to_metadata()
    assert metadata["type"] == "lesson"
    assert metadata["strategy"] == "momentum"
    assert metadata["regime"] == "high_vol_bull"
    assert metadata["asset"] == "BTC"
    assert metadata["outcome"] == "win"
    assert metadata["source_trade_id"] == "t-1"


def test_lesson_memory_omits_unset_optional_fields_from_metadata():
    lesson = LessonMemory(
        strategy="mean_reversion",
        regime="low_vol",
        lesson_text="Fade extremes only when volume confirms exhaustion.",
    )

    metadata = lesson.to_metadata()
    assert "asset" not in metadata
    assert "outcome" not in metadata
    assert "source_trade_id" not in metadata


def test_regime_snapshot_memory():
    snapshot = RegimeSnapshotMemory(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        regime="high_vol_bull",
        asset="BTC",
        summary="ATR elevated, price above 20/50 EMA.",
    )

    assert "high_vol_bull" in snapshot.to_content()
    assert "ATR elevated" in snapshot.to_content()
    assert snapshot.to_metadata() == {
        "type": "regime_snapshot",
        "regime": "high_vol_bull",
        "asset": "BTC",
    }


def test_event_memory():
    event = EventMemory(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        event_type="macro_news",
        asset="BTC",
        description="FOMC held rates steady.",
    )

    assert event.to_content() == "[macro_news] FOMC held rates steady."
    assert event.to_metadata() == {
        "type": "event",
        "event_type": "macro_news",
        "asset": "BTC",
    }
