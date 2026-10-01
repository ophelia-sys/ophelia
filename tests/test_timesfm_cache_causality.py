import time
import pytest
from control_plane import db
from control_plane.forecast_service import ForecastService


def test_forecast_cache_no_collision_different_causal_cutoffs(monkeypatch):
    """
    Test 2: Strengthen Forecast Cache Correctness.
    Verifies that forecasts generated from different causal market-data cutoffs
    cannot incorrectly collide inside the same nominal validity bucket.

    Forecast A:
      instrument = BTC-USDT
      timeframe = 5m
      market cutoff = T1

    Forecast B:
      instrument = BTC-USDT
      timeframe = 5m
      market cutoff = T2 (T2 > T1, both within the same 60s validity bucket)

    The system must NOT accidentally serve Forecast A as Forecast B.
    """
    svc = ForecastService.get_instance()
    svc.cache.clear()

    # Freeze time during test to ensure test execution does not roll over wall-clock boundary
    fixed_now_sec = 1790858100.0
    monkeypatch.setattr(time, "time", lambda: fixed_now_sec)

    sym = "BTC-USDT"
    now_ms = int(fixed_now_sec * 1000)
    base_ts = (now_ms // 60000) * 60000

    # Populate 50 candles ending at T1
    t1 = base_ts + 10000
    t2 = base_ts + 20000  # 10s later, strictly in same validity bucket (time_bucket = base_ts // 60000)

    # Clean test candles
    conn = db._connect()
    with db._lock:
        conn.execute("DELETE FROM candles WHERE symbol=?", (sym,))
        candles_t1 = []
        for i in range(40):
            ts = t1 - (40 - i) * 60000
            price = 60000.0 + i * 10.0
            candles_t1.append(("bingx", sym, ts, price, price + 5, price - 5, price, 100.0, 50.0, 10))
        conn.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)", candles_t1)
        conn.commit()

    # 1. Generate Forecast A with market cutoff T1
    res_a = svc.generate_forecast(instrument=sym, timeframe="5m", cutoff_ts=t1)
    assert res_a.data_timestamp <= t1, "Forecast A data_timestamp must not exceed cutoff T1"
    cutoff_a = res_a.data_timestamp

    # 2. Add newer candle at T2
    with db._lock:
        conn.execute("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                     ("bingx", sym, t2, 65000.0, 65100.0, 64900.0, 65050.0, 200.0, 120.0, 25))
        conn.commit()

    # 3. Generate Forecast B with market cutoff T2 (in same nominal validity bucket)
    res_b = svc.generate_forecast(instrument=sym, timeframe="5m", cutoff_ts=t2)
    assert res_b.data_timestamp <= t2, "Forecast B data_timestamp must not exceed cutoff T2"
    cutoff_b = res_b.data_timestamp

    # 4. Strict assertions:
    assert cutoff_b > cutoff_a, f"Market cutoff for B ({cutoff_b}) must be newer than A ({cutoff_a})"
    assert res_a.forecast_id != res_b.forecast_id, "Forecast B must NOT return cached Forecast A"
    assert res_a.data_timestamp != res_b.data_timestamp, "Forecast A and B must reflect distinct market states"

    # 5. Verify Cache Hits for exact matching cutoffs:
    # Querying T1 again within validity window must hit Forecast A
    res_a_cached = svc.generate_forecast(instrument=sym, timeframe="5m", cutoff_ts=t1)
    assert res_a_cached.forecast_id == res_a.forecast_id, "Exact cutoff T1 query must return cached Forecast A"

    # Querying T2 again within validity window must hit Forecast B
    res_b_cached = svc.generate_forecast(instrument=sym, timeframe="5m", cutoff_ts=t2)
    assert res_b_cached.forecast_id == res_b.forecast_id, "Exact cutoff T2 query must return cached Forecast B"
