"""
Verification of forecast scheduling, caching, and duplicate concurrent inference prevention.
"""

import time
import threading
import numpy as np
import pytest

from control_plane.forecast_service import (
    ForecastService,
    ForecastScheduler,
    ForecastResult,
    StatisticalBaselineProvider,
    STATUS_SUCCESS
)


def test_forecast_cache_validity_window():
    svc = ForecastService()
    svc.timesfm_provider = StatisticalBaselineProvider(mode="NAIVE_PERSISTENCE")

    # Insert mock candles in DB if needed or let baseline provider generate
    res1 = svc.generate_forecast("BTC-USDT", timeframe="15m", horizon=10, force_refresh=True)
    assert res1.status in (STATUS_SUCCESS, "INSUFFICIENT_DATA")

    # Immediate second call must hit cache (same forecast_id)
    res2 = svc.generate_forecast("BTC-USDT", timeframe="15m", horizon=10, force_refresh=False)
    assert res1.forecast_id == res2.forecast_id

    # Check cache entry metadata and verify strengthened 6-part cache key incorporating market cutoff
    matching_keys = [k for k in svc.cache.keys() if k[0] == "BTC-USDT" and k[1] == "15m"]
    assert len(matching_keys) == 1
    key = matching_keys[0]
    assert len(key) == 6
    assert key[0] == "BTC-USDT"
    assert key[1] == "15m"
    # key[2] is validity bucket
    # key[3] is market_cutoff
    assert key[4] == "3.0"
    assert key[5] == "TIMESFM_FEATURE_SCHEMA_V1"

    cache_entry = svc.cache[key]
    assert cache_entry is not None
    assert cache_entry["valid_until"] > cache_entry["generated_at"]
    assert cache_entry["valid_until"] == cache_entry["next_refresh_at"]


def test_duplicate_concurrent_inference_prevention():
    svc = ForecastService()
    inference_calls = 0
    lock = threading.Lock()

    class SlowProvider(StatisticalBaselineProvider):
        def forecast(self, *args, **kwargs):
            nonlocal inference_calls
            with lock:
                inference_calls += 1
            time.sleep(0.1)  # Simulate model compute latency
            return super().forecast(*args, **kwargs)

    svc.timesfm_provider = SlowProvider()
    results = []

    def call_worker():
        r = svc.generate_forecast("SOL-USDT", timeframe="15m", horizon=10, force_refresh=False)
        results.append(r)

    # Spawn 5 concurrent threads requesting forecast for the same instrument/timeframe simultaneously
    threads = [threading.Thread(target=call_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 5 callers must receive a valid result
    assert len(results) == 5
    # Because of lock and cache checking inside lock, only 1 actual inference should have been performed
    assert inference_calls == 1
    # All threads must share the exact same cached forecast_id
    assert all(r.forecast_id == results[0].forecast_id for r in results)


def test_scheduler_lifecycle():
    svc = ForecastService()
    scheduler = ForecastScheduler(service=svc, interval_seconds=1)
    assert scheduler.running is False
    scheduler.start()
    assert scheduler.running is True
    assert scheduler.thread is not None and scheduler.thread.is_alive()
    scheduler.stop()
    assert scheduler.running is False
