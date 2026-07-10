"""Integration tests against the live local Supermemory server, skipped
(via the memory_test_client fixture) if it isn't reachable.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from memory.schemas import RegimeSnapshotMemory


def test_regime_empty_when_nothing_written(memory_test_client):
    response = memory_test_client.get("/api/regime")
    assert response.status_code == 200
    assert response.json()["snapshots"] == []


def test_regime_returns_written_snapshot_filtered_by_asset(memory_test_client):
    memory_test_client.memory_client.write_regime_snapshot(
        RegimeSnapshotMemory(
            timestamp=datetime.now(timezone.utc),
            regime="high_vol_bear",
            asset="BTC",
            summary="Elevated realized volatility, price below the 50-day moving average.",
        )
    )
    time.sleep(8)  # async chunk embedding

    response = memory_test_client.get("/api/regime", params={"q": "volatility regime", "asset": "BTC"})
    assert response.status_code == 200
    snapshots = response.json()["snapshots"]
    assert len(snapshots) >= 1
    assert snapshots[0]["asset"] == "BTC"
    assert snapshots[0]["regime"] == "high_vol_bear"
