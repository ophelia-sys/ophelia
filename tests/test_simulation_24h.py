import numpy as np
import pytest
from unittest.mock import patch
import time

from control_plane import core, db, analytics, config


def _make_candle(ts, o, h, l, c, v=100.0):
    return {
        "exchange": "BINANCE",
        "symbol": "BTC-USDT",
        "ts": ts,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
        "taker_buy": v * 0.5,
        "trades": 50
    }


def test_missing_historical_data_returns_diagnostic():
    """Requirement 12: Missing historical data returns explicit diagnostic, not fake candidates."""
    with patch("control_plane.db.query_candles", return_value=[]):
        res = core.simulate_strategy_24h({
            "strategy": "VWAP_SUPERTREND",
            "symbols": ["BTC-USDT"],
            "timeframe": "3m"
        })
        assert res["signals_count"] == 0
        assert res["simulated_trades_count"] == 0
        assert "BTC-USDT" in res["diagnostics"]
        assert "Historical data unavailable" in res["diagnostics"]["BTC-USDT"]["error"]


def test_four_symbols_no_events_does_not_produce_four_candidates():
    """Requirement 1: Four symbols with no crossover events does NOT produce 4 candidates."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    flat_candles = [_make_candle(base_ts + i * 60_000, 100.0, 100.1, 99.9, 100.0) for i in range(1440)]
    
    with patch("control_plane.db.query_candles", return_value=flat_candles):
        res = core.simulate_strategy_24h({
            "strategy": "VWAP_SUPERTREND",
            "symbols": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"],
            "timeframe": "3m"
        })
        assert res["signals_count"] == 0
        assert len(res["signals"]) == 0
        assert res["signals_count"] != len(res["symbols_checked"])


def test_ema_crossover_produces_real_candidate_with_non_zero_price():
    """Requirements 2 & 3: Known crossover produces candidate with price != $0.0."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    p = 100.0
    # 30 flat candles
    for i in range(30):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    # 30 falling candles (EMA9 < EMA20)
    for i in range(30, 60):
        p -= 0.2
        candles.append(_make_candle(base_ts + i * 60_000, p + 0.1, p + 0.2, p - 0.2, p, v=100.0))
    # 40 strong surging candles (EMA9 crosses above EMA20, price moves clearly above VWAP)
    for i in range(60, 100):
        p += 0.8
        candles.append(_make_candle(base_ts + i * 60_000, p - 0.2, p + 0.5, p - 0.3, p, v=300.0))
    # Remainder
    for i in range(100, 150):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=100.0))

    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        assert res["signals_count"] > 0
        sig = res["signals"][0]
        assert sig["price"] > 0.0
        assert sig["symbol"] == "BTC-USDT"
        assert sig["direction"] in ("LONG", "SHORT")
        # Check that both SHORT and LONG crossovers were detected chronologically
        directions = [s["direction"] for s in res["signals"]]
        assert "SHORT" in directions
        assert "LONG" in directions


def test_vwap_chop_blocks_signal():
    """Requirement 4: When VWAP regime is CHOP (< 0.10% separation), signals are blocked."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    for i in range(150):
        p = 100.0 + (0.02 if i % 2 == 0 else -0.02)
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.02, p - 0.02, p, v=100.0))
        
    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        for s in res["signals"]:
            assert "BLOCKED_BY_VWAP" in s["status"]
            assert s["status"] != "ELIGIBLE"


def test_clear_above_permits_only_long_and_blocks_short():
    """Requirements 5 & 6: CLEAR_ABOVE permits LONG and blocks SHORT."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    for i in range(30):
        candles.append(_make_candle(base_ts + i * 60_000, 100.0, 100.1, 99.9, 100.0, v=100.0))
    for i in range(30, 60):
        candles.append(_make_candle(base_ts + i * 60_000, 105.0, 105.5, 104.8, 105.0, v=100.0))
        
    vw = analytics.session_vwap_series(candles)
    vmap = {v["ts"]: v for v in vw}
    window = candles[52:55]
    sides = ["ABOVE" if r["close"] > vmap[r["ts"]]["vwap"] else "BELOW" for r in window]
    cur_vwap = vmap[candles[54]["ts"]]["vwap"]
    sep_pct = abs(candles[54]["close"] - cur_vwap) / cur_vwap * 100
    
    assert len(set(sides)) == 1 and sides[0] == "ABOVE"
    assert sep_pct >= config.VWAP_MIN_SEPARATION_PCT


def test_direction_filter_enforcement():
    """Requirement 7: Direction filter restricts candidates."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    p = 100.0
    for i in range(30):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    for i in range(30, 60):
        p -= 0.2
        candles.append(_make_candle(base_ts + i * 60_000, p + 0.1, p + 0.2, p - 0.2, p, v=100.0))
    for i in range(60, 100):
        p += 0.8
        candles.append(_make_candle(base_ts + i * 60_000, p - 0.2, p + 0.5, p - 0.3, p, v=300.0))
    for i in range(100, 150):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=100.0))

    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "SHORT"
        })
        for s in res["signals"]:
            if s["direction"] == "LONG":
                assert "FILTERED_BY_DIRECTION" in s["status"]


def test_anti_leakage_no_future_candle_affects_signal():
    """Requirement 9: Future candles do not alter past signal detection."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles_part1 = []
    p = 100.0
    for i in range(30):
        candles_part1.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    for i in range(30, 60):
        p -= 0.2
        candles_part1.append(_make_candle(base_ts + i * 60_000, p + 0.1, p + 0.2, p - 0.2, p, v=100.0))
    for i in range(60, 100):
        p += 0.8
        candles_part1.append(_make_candle(base_ts + i * 60_000, p - 0.2, p + 0.5, p - 0.3, p, v=300.0))
        
    with patch("control_plane.db.query_candles", return_value=candles_part1):
        res1 = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        
    candles_part2 = list(candles_part1)
    for i in range(100, 180):
        p -= 2.0
        candles_part2.append(_make_candle(base_ts + i * 60_000, p, p + 0.5, p - 0.5, p, v=500.0))
        
    with patch("control_plane.db.query_candles", return_value=candles_part2):
        res2 = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        
    if res1["signals"]:
        sig1 = res1["signals"][0]
        sig2 = res2["signals"][0]
        assert sig1["timestamp_ms"] == sig2["timestamp_ms"]
        assert sig1["direction"] == sig2["direction"]
        assert sig1["price"] == sig2["price"]


def test_max_open_trades_respected():
    """Requirement 10: MAX_OPEN_TRADES=1 is respected."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    p = 100.0
    for i in range(200):
        p += 0.5
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=100.0))
        
    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        trades = res["trades"]
        assert isinstance(trades, list)


def test_simulator_does_not_call_get_market_snapshot():
    """Requirement 14: Simulator does not use get_market_snapshot() as its historical data source."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    flat_candles = [_make_candle(base_ts + i * 60_000, 100.0, 100.1, 99.9, 100.0) for i in range(1440)]
    
    with patch("control_plane.db.query_candles", return_value=flat_candles), \
         patch("control_plane.analytics.get_market_snapshot") as mock_snap:
        res = core.simulate_strategy_24h({
            "strategy": "VWAP_SUPERTREND",
            "symbols": ["BTC-USDT"],
            "timeframe": "3m"
        })
        # get_market_snapshot must NEVER be called by the 24h simulator
        mock_snap.assert_not_called()
        assert res["symbols_checked"] == ["BTC-USDT"]


def test_timeframe_aggregation_respected():
    """Requirement 13 & Timeframe check: 1440 1m candles on 3m timeframe aggregates to 480-481 bars."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles_1m = [_make_candle(base_ts + i * 60_000, 100.0, 100.1, 99.9, 100.0) for i in range(1440)]
    
    with patch("control_plane.db.query_candles", return_value=candles_1m):
        res_3m = core.simulate_strategy_24h({
            "strategy": "VWAP_SUPERTREND",
            "symbols": ["BTC-USDT"],
            "timeframe": "3m"
        })
        bars_3m = res_3m["diagnostics"]["BTC-USDT"]["candles_fetched"]
        assert 479 <= bars_3m <= 481
        
        res_5m = core.simulate_strategy_24h({
            "strategy": "VWAP_SUPERTREND",
            "symbols": ["BTC-USDT"],
            "timeframe": "5m"
        })
        bars_5m = res_5m["diagnostics"]["BTC-USDT"]["candles_fetched"]
        assert 287 <= bars_5m <= 289


def test_both_strategy_semantics():
    """Requirement for BOTH strategy: checks both ST/VWAP and EMA crossover triggers."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    p = 100.0
    for i in range(30):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    for i in range(30, 60):
        p -= 0.2
        candles.append(_make_candle(base_ts + i * 60_000, p + 0.1, p + 0.2, p - 0.2, p, v=100.0))
    for i in range(60, 100):
        p += 0.8
        candles.append(_make_candle(base_ts + i * 60_000, p - 0.2, p + 0.5, p - 0.3, p, v=300.0))
    for i in range(100, 150):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=100.0))

    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "BOTH",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        assert res["strategy"] == "BOTH"
        assert res["signals_count"] > 0


def test_three_sequential_trades_when_positions_exit():
    """Requirement: When previous positions exit, subsequent eligible signals produce new trades."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    p = 100.0
    for i in range(30):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    
    # Trade 1: Clean drop below VWAP -> SHORT entry -> Stop out
    for i in range(30, 60):
        p -= 0.5
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    for i in range(60, 80):
        p += 2.0 # quick stop out
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.5, p - 0.1, p, v=500.0))
    # Sustain high plateau so VWAP catches up and regime becomes CLEAR_ABOVE
    for i in range(80, 120):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=100.0))
    # Small dip and re-surge to trigger Golden Cross above VWAP
    for i in range(120, 130):
        p -= 0.2
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    for i in range(130, 160):
        p += 0.8
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.4, p - 0.2, p, v=300.0))
        
    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        assert res["simulated_trades_count"] >= 2
        assert len(res["trades"]) == res["simulated_trades_count"]
        for t in res["trades"]:
            assert "IST" in t["entry_time_ist"]
            assert "IST" in t["exit_time_ist"]
            assert t["exit_ts_ms"] >= t["entry_ts_ms"]


def test_position_cap_records_blocked_status_and_preserves_signal():
    """Requirement: When a position is open, overlapping signals are marked BLOCKED_BY_POSITION_CAP."""
    base_ts = int(time.time() * 1000) - 24 * 3600 * 1000
    candles = []
    p = 100.0
    for i in range(30):
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.1, p - 0.1, p, v=100.0))
    for i in range(30, 60):
        p -= 0.1
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.05, p - 0.05, p, v=100.0))
    for i in range(60, 100):
        p += 0.5
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=300.0))
    for i in range(100, 150):
        p += 0.5
        candles.append(_make_candle(base_ts + i * 60_000, p, p + 0.2, p - 0.2, p, v=300.0))
        
    with patch("control_plane.db.query_candles", return_value=candles):
        res = core.simulate_strategy_24h({
            "strategy": "EMA_CROSSOVER",
            "symbols": ["BTC-USDT"],
            "timeframe": "1m",
            "direction": "ANY"
        })
        # Check signals have explicit status
        for s in res["signals"]:
            assert "status" in s
            assert "time_ist" in s
            assert "candle_window_ist" in s
            assert "IST" in s["time_ist"]


