"""Unit and Integration tests for Binance Data Engine & Causal Aggregator.

Layer: tests/test_binance_data_engine.py
"""
import time
import pytest
from control_plane import db
from control_plane.binance_data import (
    BinanceCandle1m,
    BinanceMarketDataProvider,
    CausalCandleAggregator,
    BinanceHistoricalBackfill,
)


def test_binance_candle_1m_model():
    c = BinanceCandle1m(
        symbol="BTCUSDT",
        ts=1700000000000,
        open=86000.0,
        high=86100.0,
        low=85950.0,
        close=86050.0,
        volume=12.5,
        close_ts=1700000059999,
        quote_volume=1075000.0,
        trade_count=350,
        taker_buy_volume=6.5,
        taker_buy_quote_volume=559000.0,
        is_closed=True,
    )
    d = c.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["open"] == 86000.0
    assert d["close"] == 86050.0
    assert d["venue"] == "BINANCE"


def test_causal_aggregation_5m_window():
    base_ts = 1700000000000  # aligned
    bars = []
    for i in range(5):
        bars.append({
            "symbol": "BTCUSDT",
            "ts": base_ts + (i * 60_000),
            "close_ts": base_ts + (i * 60_000) + 59_999,
            "open": 86000.0 + i,
            "high": 86050.0 + (i * 2),
            "low": 85950.0 - i,
            "close": 86010.0 + i,
            "volume": 10.0,
            "quote_volume": 860000.0,
            "trade_count": 100,
            "taker_buy_volume": 5.0,
            "is_closed": True,
        })

    candle_5m = CausalCandleAggregator.aggregate_window(bars, "5m")
    assert candle_5m is not None
    assert candle_5m["symbol"] == "BTCUSDT"
    assert candle_5m["resolution"] == "5m"
    assert candle_5m["ts"] == base_ts
    assert candle_5m["open"] == 86000.0
    assert candle_5m["close"] == 86014.0
    assert candle_5m["high"] == 86058.0  # max of 86050, 86052, 86054, 86056, 86058
    assert candle_5m["low"] == 85946.0   # min of 85950, 85949, 85948, 85947, 85946
    assert candle_5m["volume"] == 50.0
    assert candle_5m["trade_count"] == 500
    assert candle_5m["taker_buy_volume"] == 25.0
    assert candle_5m["is_closed"] is True


def test_causal_aggregation_rejects_partial_bar():
    base_ts = 1700000000000
    bars = []
    for i in range(5):
        bars.append({
            "symbol": "BTCUSDT",
            "ts": base_ts + (i * 60_000),
            "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0,
            "volume": 1.0,
            "is_closed": (i < 4),  # bar 4 is not closed!
        })
    candle_5m = CausalCandleAggregator.aggregate_window(bars, "5m")
    assert candle_5m is None  # Must reject partial candle


def test_causal_aggregation_rejects_sequence_gap():
    base_ts = 1700000000000
    bars = []
    # Missing bar at index 2 (skips 60s)
    timestamps = [base_ts, base_ts + 60_000, base_ts + 180_000, base_ts + 240_000, base_ts + 300_000]
    for ts in timestamps:
        bars.append({
            "symbol": "BTCUSDT",
            "ts": ts,
            "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0,
            "volume": 1.0,
            "is_closed": True,
        })
    candle_5m = CausalCandleAggregator.aggregate_window(bars, "5m")
    assert candle_5m is None  # Sequence gap must fail


def test_causal_aggregate_series():
    base_ts = 1700000100000  # unaligned
    # Create 15 continuous closed 1m bars
    bars = []
    start_aligned = (base_ts // 300_000) * 300_000
    for i in range(15):
        bars.append({
            "symbol": "ETHUSDT",
            "ts": start_aligned + (i * 60_000),
            "close_ts": start_aligned + (i * 60_000) + 59_999,
            "open": 3000.0 + i,
            "high": 3010.0 + i,
            "low": 2990.0 + i,
            "close": 3005.0 + i,
            "volume": 2.0,
            "quote_volume": 6000.0,
            "trade_count": 20,
            "taker_buy_volume": 1.0,
            "is_closed": True,
        })

    series_5m = CausalCandleAggregator.aggregate_series(bars, "5m")
    assert len(series_5m) == 3
    for c in series_5m:
        assert c["volume"] == 10.0
        assert c["source_bar_count"] == 5

    series_15m = CausalCandleAggregator.aggregate_series(bars, "15m")
    assert len(series_15m) == 1
    assert series_15m[0]["volume"] == 30.0
    assert series_15m[0]["source_bar_count"] == 15


def test_binance_db_storage_and_query():
    ts_now = int(time.time() * 1000)
    raw_sample = [{
        "symbol": "SOLUSDT",
        "ts": ts_now - (i * 60_000),
        "open": 140.0 + i,
        "high": 142.0 + i,
        "low": 139.0 + i,
        "close": 141.0 + i,
        "volume": 50.0,
        "quote_volume": 7000.0,
        "trade_count": 80,
        "taker_buy_volume": 25.0,
        "is_closed": True,
        "data_quality": "VALID",
    } for i in range(5)]

    inserted = db.insert_binance_raw_1m(raw_sample)
    assert inserted == 5

    queried = db.get_binance_raw_1m("SOLUSDT", start_ts=ts_now - 400_000, limit=10)
    assert len(queried) >= 5
    assert queried[0]["symbol"] == "SOLUSDT"


def test_binance_provider_live_rest():
    provider = BinanceMarketDataProvider()
    server_time = provider.fetch_server_time()
    assert server_time > 1700000000000

    klines = provider.fetch_klines("BTCUSDT", limit=5)
    assert len(klines) == 5
    assert klines[0].symbol == "BTCUSDT"
    assert klines[0].open > 0
    assert klines[0].close > 0
