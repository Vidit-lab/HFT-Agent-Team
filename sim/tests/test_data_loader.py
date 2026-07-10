"""Integration tests against real Yahoo Finance data. Skipped, not failed,
when the network isn't reachable, matching the pattern used for the
memory/ live-server tests.
"""

from __future__ import annotations

import httpx
import pytest

from sim.data_loader import load_ohlcv


def _network_available() -> bool:
    try:
        httpx.get("https://query1.finance.yahoo.com", timeout=3.0)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_network():
    if not _network_available():
        pytest.skip("network not reachable; skipping data loader integration tests")


def test_cache_roundtrip_is_byte_identical(tmp_path):
    fresh = load_ohlcv("AAPL", "2023-01-01", "2023-02-01", cache_dir=tmp_path, force_refresh=True)
    cached_a = load_ohlcv("AAPL", "2023-01-01", "2023-02-01", cache_dir=tmp_path)
    cached_b = load_ohlcv("AAPL", "2023-01-01", "2023-02-01", cache_dir=tmp_path)

    assert not fresh.empty
    assert fresh.equals(cached_a)
    assert cached_a.equals(cached_b)


def test_columns_and_ordering(tmp_path):
    df = load_ohlcv("AAPL", "2023-01-01", "2023-01-15", cache_dir=tmp_path)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df["timestamp"].is_monotonic_increasing
