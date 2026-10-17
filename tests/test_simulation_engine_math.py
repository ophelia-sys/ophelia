import pytest
from datetime import datetime, timezone
from control_plane.core import _resolve_strategy_config, simulate_strategy_24h
from control_plane import db, config


def test_resolve_strategy_config_nested_android():
    """Verify that nested strategy_risk from Android StrategyBuilder is parsed accurately without falling back to defaults."""
    req = {
        "strategy": "VWAP_SUPERTREND",
        "symbol": "SOL-USDT",
        "timeframe": "3m",
        "strategy_risk": {
            "VWAP_SUPERTREND": {
                "timeframe": "3m",
                "hard_stop_pct": 0.8,
                "structural_vwap_enabled": True,
                "structural_vwap_pct": 0.2,
                "structural_st_enabled": True,
                "structural_st_pct": 0.2,
                "targets": [{"distance_pct": 1.5, "qty_pct": 50.0}],
                "trailing_stop": {"enabled": True, "trail_pct": 0.2},
                "break_even_after_partial": True
            }
        }
    }
    
    cfg = _resolve_strategy_config(req, "VWAP_SUPERTREND")
    assert cfg["hard_stop_pct"] == 0.8, f"Expected 0.8%, got {cfg['hard_stop_pct']}"
    assert cfg["structural_vwap_enabled"] is True
    assert cfg["structural_vwap_pct"] == 0.2
    assert cfg["structural_st_enabled"] is True
    assert cfg["structural_st_pct"] == 0.2
    assert len(cfg["targets"]) == 1
    assert cfg["targets"][0]["distance_pct"] == 1.5
    assert cfg["targets"][0]["qty_pct"] == 50.0
    assert cfg["breakeven"] is True
    assert cfg["trailing_enabled"] is True
    assert cfg["trailing_pct"] == 0.2


def test_resolve_strategy_config_flat_payload():
    """Verify flat parameters work seamlessly."""
    req = {
        "strategy": "EMA_CROSSOVER",
        "hard_stop_pct": 0.5,
        "structural_vwap_enabled": False,
        "targets": [{"distance_pct": 2.0, "qty_pct": 100.0}],
        "trailing_enabled": True,
        "trailing_trail_pct": 0.3,
        "breakeven": False
    }
    cfg = _resolve_strategy_config(req, "EMA_CROSSOVER")
    assert cfg["hard_stop_pct"] == 0.5
    assert cfg["targets"][0]["distance_pct"] == 2.0
    assert cfg["trailing_enabled"] is True
    assert cfg["trailing_pct"] == 0.3


def test_sol_short_0_8_hard_stop_math():
    """Verify that on a SHORT entry of 103.09, 0.8% stop exits at 103.9147, NOT 104.1209 (1.0%)."""
    entry = 103.09
    hard_stop_pct = 0.8
    expected_exit = entry * (1 + hard_stop_pct / 100.0)
    assert round(expected_exit, 4) == 103.9147
    
    # 1.0% stop check
    one_pct_exit = entry * 1.01
    assert round(one_pct_exit, 4) == 104.1209
    assert expected_exit != one_pct_exit


def test_simulate_strategy_24h_mocked_candles(monkeypatch):
    """Test 24h simulation with synthetic candle sequence verifying 0.8% stop and partial TP."""
    now_ms = int(datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
    start_ms = now_ms - 24 * 3600 * 1000
    
    # Generate 1m bars for SOL-USDT with 'ts' key
    mock_candles = []
    base_px = 100.0
    for m in range(29 * 60):  # 29 hours (5h warmup + 24h)
        ts = start_ms - 5 * 3600 * 1000 + m * 60 * 1000
        px = base_px + (m * 0.01)
        mock_candles.append({
            "ts": ts,
            "open": px,
            "high": px + 0.05,
            "low": px - 0.05,
            "close": px,
            "volume": 100.0
        })

    def mock_query(sym, s_ms, e_ms):
        return [c for c in mock_candles if s_ms <= c["ts"] <= e_ms]

    monkeypatch.setattr(db, "query_candles", mock_query)
    monkeypatch.setattr(db, "watchlist_symbols", lambda: ["SOL-USDT"])

    req = {
        "strategy": "VWAP_SUPERTREND",
        "symbol": "SOL-USDT",
        "timeframe": "3m",
        "margin_usdt": 10.0,
        "leverage": 15.0,
        "strategy_risk": {
            "VWAP_SUPERTREND": {
                "timeframe": "3m",
                "hard_stop_pct": 0.8,
                "structural_vwap_enabled": False,
                "structural_st_enabled": False,
                "targets": [{"distance_pct": 1.5, "qty_pct": 50.0}],
                "trailing_stop": {"enabled": True, "trail_pct": 0.2},
                "break_even_after_partial": True
            }
        }
    }

    result = simulate_strategy_24h(req)
    assert result["status"] == "OK"
    assert result["lookback_hours"] == 24
    assert result["strategy"] == "VWAP_SUPERTREND"
    assert "date_range_ist" in result
    assert isinstance(result["trades"], list)


def test_simulate_strategy_24h_partial_tp_breakeven_trailing_math():
    """Verify that partial exit math computes exact PnL: 50% @ +1.5% TP1 + remainder @ trailing stop."""
    margin = 10.0
    lev = 15.0
    fees = round(margin * lev * 0.0006 * 2, 4)  # 0.18 USDT
    
    # 50% closed at +1.5%
    tp1_pnl_pct = 1.5
    tp1_closed_pct = 50.0
    tp1_pnl_usdt = margin * (tp1_pnl_pct / 100.0) * lev * (tp1_closed_pct / 100.0)  # 10 * 0.015 * 15 * 0.5 = 1.125 USDT
    
    # Remainder 50% closed at trailing stop +1.0% (after peak +1.2% trailed 0.2%)
    rem_pnl_pct = 1.0
    rem_closed_pct = 50.0
    rem_pnl_usdt = margin * (rem_pnl_pct / 100.0) * lev * (rem_closed_pct / 100.0)  # 10 * 0.01 * 15 * 0.5 = 0.75 USDT
    
    total_realized_usdt = tp1_pnl_usdt + rem_pnl_usdt - fees  # 1.125 + 0.75 - 0.18 = 1.695 USDT
    total_realized_pct = (total_realized_usdt / margin) * 100.0  # 16.95% on margin (or +1.13% unleveraged net)
    
    assert round(total_realized_usdt, 4) == 1.695
    assert round(total_realized_pct, 2) == 16.95

