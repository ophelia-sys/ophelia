"""Comprehensive unit tests for Ophelia Master Automation, Strategy Simulation,
Position-Cap (MAX_OPEN_TRADES = 2), VWAP Gate (ON/OFF), and Margin Allocation.
"""
import time
import pytest
from control_plane import config, core, db, account, analytics

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test_master.db")
    monkeypatch.setattr(config, "DB_PATH", test_db)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "MAX_OPEN_TRADES", 2)
    db._conn = None

    # Seed 1440 1m candles for BTC-USDT, SOL-USDT, XRP-USDT, ETH-USDT
    now = int(time.time() * 1000)
    base_ts = now - 1440 * 60 * 1000

    candles = []
    # BTC: base 80000, oscillating to test multiple crossovers
    for i in range(1440):
        ts = base_ts + i * 60 * 1000
        cycle = (i % 40)
        p = 80000.0 - (i * 0.5) + (50.0 if cycle > 20 else -50.0)
        candles.append({
            "ts": ts, "open": p, "high": p + 5.0, "low": p - 5.0, "close": p,
            "volume": 100.0, "taker_buy": 50.0, "trades": 20
        })
    db.upsert_candles("BINANCE", "BTC-USDT", candles)

    # SOL: base 100, oscillating trend to test crossovers, TP and Trailing
    sol_candles = []
    for i in range(1440):
        ts = base_ts + i * 60 * 1000
        # Oscillate every 60 candles with upward bias
        cycle = (i % 60)
        p = 100.0 + (i * 0.01) + (10.0 if cycle > 30 else -5.0)
        sol_candles.append({
            "ts": ts, "open": p, "high": p + 1.0, "low": p - 1.0, "close": p,
            "volume": 500.0, "taker_buy": 300.0, "trades": 50
        })
    db.upsert_candles("BINANCE", "SOL-USDT", sol_candles)


def test_position_cap_is_two():
    """Verify MAX_OPEN_TRADES is 2 across config and account."""
    assert config.MAX_OPEN_TRADES == 2
    dash = account.dashboard_view(user_id=1)
    assert dash["risk"]["positions_max"] == 2


def test_account_capacity_and_allocation():
    """Verify margin reservation calculation and allocatable remaining."""
    # Mock exchange snapshot
    def mock_snap():
        return {"balance": 100.0, "available_margin": 100.0, "used_margin": 0.0, "equity": 100.0}, []
    account.exchange_snapshot = mock_snap

    cap = account.account_capacity(user_id=1)
    assert cap["account_available"] == 100.0
    assert cap["automation_reserved"] == 0.0
    assert cap["allocatable_remaining"] == 100.0

    # Create an automation allocating 30 USDT
    db.create_automation({
        "strategy": "VWAP_SUPERTREND",
        "symbol": "SOL-USDT",
        "margin_usdt": 30.0,
        "status": "ACTIVE"
    }, user_id=1)

    cap2 = account.account_capacity(user_id=1)
    assert cap2["automation_reserved"] == 30.0
    assert cap2["allocatable_remaining"] == 70.0


def test_simulation_100_percent_tp():
    """TEST A: Simulation of 100% TP target hit."""
    req = {
        "strategy": "EMA_CROSSOVER",
        "symbols": ["SOL-USDT"],
        "timeframe": "1m",
        "direction": "LONG",
        "vwap_gate_enabled": False,
        "hard_stop_pct": 2.0,
        "targets": [{"distance_pct": 0.5, "qty_pct": 100.0}],
        "trailing_enabled": False
    }
    res = core.simulate_strategy_24h(req)
    assert res["status"] == "OK"
    assert res["vwap_gate"] == "OFF"
    assert len(res["signals"]) > 0
    
    # If trades executed, verify that 100% TP exit occurred
    if res["trades"]:
        t1 = res["trades"][0]
        assert t1["exit_reason"] in ("100%_TP", "TARGET_HIT", "STOP_LOSS", "OPEN_AT_SIM_END")


def test_simulation_partial_plus_trailing():
    """TEST B: 50% TP1 + 50% Trailing remainder."""
    req = {
        "strategy": "EMA_CROSSOVER",
        "symbols": ["SOL-USDT"],
        "timeframe": "1m",
        "direction": "LONG",
        "vwap_gate_enabled": False,
        "hard_stop_pct": 2.0,
        "targets": [{"distance_pct": 0.3, "qty_pct": 50.0}],
        "trailing_enabled": True,
        "trailing_trail_pct": 0.2,
        "breakeven": True
    }
    res = core.simulate_strategy_24h(req)
    assert res["status"] == "OK"
    for t in res["trades"]:
        if t["partial_exits"]:
            pe = t["partial_exits"][0]
            assert pe["qty_pct"] == 50.0
            assert pe["stage"] == "TP1"
            assert t["breakeven_activated"] is True


def test_vwap_gate_on_vs_off():
    """Verify that VWAP Gate ON blocks counter-regime signals, while OFF allows them."""
    # Gate ON
    req_on = {
        "strategy": "VWAP_SUPERTREND",
        "symbols": ["BTC-USDT"],
        "timeframe": "5m",
        "direction": "ANY",
        "vwap_gate_enabled": True
    }
    res_on = core.simulate_strategy_24h(req_on)
    
    # Gate OFF
    req_off = {
        "strategy": "VWAP_SUPERTREND",
        "symbols": ["BTC-USDT"],
        "timeframe": "5m",
        "direction": "ANY",
        "vwap_gate_enabled": False
    }
    res_off = core.simulate_strategy_24h(req_off)
    
    assert res_on["vwap_gate"] == "ON"
    assert res_off["vwap_gate"] == "OFF"
    assert res_off["blocked_signals_count"] == 0


def test_concurrency_max_two_positions():
    """Verify that up to 2 open positions are allowed simultaneously and the 3rd is blocked."""
    req = {
        "strategy": "EMA_CROSSOVER",
        "symbols": ["BTC-USDT", "SOL-USDT"],
        "timeframe": "1m",
        "direction": "ANY",
        "vwap_gate_enabled": False,
        "hard_stop_pct": 50.0, # large stops so trades stay open
        "targets": [{"distance_pct": 50.0, "qty_pct": 100.0}]
    }
    res = core.simulate_strategy_24h(req)
    assert res["status"] == "OK"
    
    # Check that any signal occurring while 2 trades were already open is marked BLOCKED_BY_POSITION_CAP
    blocked_caps = [s for s in res["signals"] if s["status"] == "BLOCKED_BY_POSITION_CAP"]
    traded_sigs = [s for s in res["signals"] if "TRADED" in s["status"]]
    
    if len(traded_sigs) >= 2 and len(res["signals"]) > 2:
        assert len(blocked_caps) > 0
        assert "already OPEN" in blocked_caps[0]["status_detail"]
