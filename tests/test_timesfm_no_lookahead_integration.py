"""
Integration-level verification of zero lookahead:
Ensures SQLite market database query cutoff (ts <= forecast_ts) and
TimesFMFeatureBuilder strictly prevent any future candle leakage.
"""

import time
import numpy as np
import pytest

from control_plane import db
from control_plane.forecast_service import TimesFMFeatureBuilder


def test_real_db_sql_cutoff_prevents_future_leakage():
    test_symbol = "INTEG-BTC-USDT"
    t_cutoff = 1700000000000  # Cutoff timestamp T
    
    # 1. Prepare historical candles: T - 60000*99 to T (100 candles)
    historical_rows = []
    for i in range(100):
        ts = t_cutoff - (99 - i) * 60000
        historical_rows.append({
            "exchange": "bingx",
            "symbol": test_symbol,
            "ts": ts,
            "open": 50000.0 + i * 10,
            "high": 50010.0 + i * 10,
            "low": 49990.0 + i * 10,
            "close": 50005.0 + i * 10,
            "volume": 10.0,
            "taker_buy": 5.0,
            "trades": 100
        })

    # 2. Prepare future candles: T + 60000 to T + 60000*50 (50 future candles with extreme anomaly price)
    future_rows = []
    for i in range(1, 51):
        ts = t_cutoff + i * 60000
        future_rows.append({
            "exchange": "bingx",
            "symbol": test_symbol,
            "ts": ts,
            "open": 999999.0,
            "high": 999999.0,
            "low": 999999.0,
            "close": 999999.0,
            "volume": 999.0,
            "taker_buy": 999.0,
            "trades": 999
        })

    try:
        # Insert all candles into SQLite
        db.upsert_candles("bingx", test_symbol, historical_rows + future_rows)

        # 3. Query with SQL cutoff max_ts = t_cutoff
        fetched = db.get_candles(test_symbol, limit=256, max_ts=t_cutoff)
        assert len(fetched) == 100

        # Assert no timestamp exceeds t_cutoff
        for c in fetched:
            assert c["ts"] <= t_cutoff
            assert c["close"] < 60000.0  # None of the 999999.0 future spikes leaked
            assert c["close"] >= 50000.0

        # 4. Feed fetched candles into TimesFMFeatureBuilder with forecast_ts = t_cutoff
        ctx_arr, past_covs, fut_covs, data_ts, freshness = TimesFMFeatureBuilder.build_context(
            candles=fetched,
            forecast_ts=t_cutoff,
            context_len=64,
            min_context_len=32
        )

        assert len(ctx_arr) == 64
        assert data_ts == t_cutoff
        assert np.all(ctx_arr < 60000.0)
        assert not np.any(ctx_arr == 999999.0)

        # 5. Adversarial check: Even if caller mistakenly passes future rows to feature builder,
        # feature builder's internal causal guard must prune them
        unfiltered_fetched = db.get_candles(test_symbol, limit=256, max_ts=None)
        assert len(unfiltered_fetched) == 150  # Contains 50 future candles

        adv_ctx, _, _, adv_data_ts, _ = TimesFMFeatureBuilder.build_context(
            candles=unfiltered_fetched,
            forecast_ts=t_cutoff,
            context_len=64,
            min_context_len=32
        )
        assert len(adv_ctx) == 64
        assert adv_data_ts == t_cutoff
        assert not np.any(adv_ctx == 999999.0)
        assert np.all(adv_ctx < 60000.0)

    finally:
        # Cleanup test candles from DB
        conn = db._connect()
        with db._lock:
            conn.execute("DELETE FROM candles WHERE symbol = ?", (test_symbol,))
            conn.commit()
