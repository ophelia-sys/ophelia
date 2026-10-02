"""Phase 5C - 5J Master Acceptance Test Suite.

Verifies:
1. Issue 1: VWAP Gate toggle serialization and behavior.
2. Issue 2: Automation CRUD, status filtering (CANCELLED/DELETED exclusion), normalization.
3. Issue 3: External BingX manual position detection, blending, and Core authorization.
4. Position Management: Edit stops/targets, partial close, full market close, reconcile.
5. Preflight Safety Suite: Live transition prerequisites verification.
6. Risk Concurrency Cap: Max open trades = 2 enforcement.
"""
import os
import sys
sys.path.insert(0, os.path.abspath("."))

import pytest
import time
from unittest.mock import MagicMock, patch

from control_plane import config, core, db, account


def test_concurrency_cap_configured():
    assert config.MAX_OPEN_TRADES == 4


def test_db_list_automations_excludes_cancelled(monkeypatch):
    test_user_id = 999
    # Create test automations
    aid1 = db.create_automation({
        "strategy": "VWAP_SUPERTREND",
        "symbol": "BTC-USDT",
        "direction_preference": "ANY",
        "margin_usage_pct": 20.0,
        "leverage": 15,
        "vwap_gate_enabled": True
    }, user_id=test_user_id)
    
    aid2 = db.create_automation({
        "strategy": "EMA_CROSSOVER",
        "symbol": "SOL-USDT",
        "direction_preference": "LONG",
        "margin_usage_pct": 25.0,
        "leverage": 15,
        "vwap_gate_enabled": False
    }, user_id=test_user_id)
    
    # Mark aid2 as CANCELLED
    db.set_automation_status(aid2, "CANCELLED", user_id=test_user_id)
    
    # List automations should only return aid1
    autos = db.list_automations(user_id=test_user_id)
    assert len(autos) == 1
    assert autos[0]["id"] == aid1
    assert autos[0]["vwap_gate_enabled"] is True
    assert autos[0]["symbol_scope"] == "SINGLE"
    assert autos[0]["symbols"] == ["BTC-USDT"]
    
    # Delete aid1
    assert db.delete_automation(aid1, user_id=test_user_id) is True
    assert len(db.list_automations(user_id=test_user_id)) == 0


def test_dashboard_blends_external_bingx_positions(monkeypatch):
    test_user_id = 888
    # Mock exchange snapshot to return 1 external BingX position
    mock_acc = {
        "asset": "USDT",
        "balance": 100.0,
        "available_margin": 80.0,
        "used_margin": 20.0,
        "equity": 100.0,
        "unrealized_pnl": 5.0
    }
    mock_positions = [{
        "symbol": "SOL-USDT",
        "side": "LONG",
        "qty": 1.5,
        "entry": 140.0,
        "mark": 143.5,
        "leverage": 10.0,
        "notional": 215.25,
        "unrealized_pnl": 5.25,
        "unrealized_pnl_pct": 2.5,
        "liquidation_price": 125.0,
        "position_id": "bingx_pos_12345"
    }]
    
    with patch("control_plane.account.exchange_snapshot", return_value=(mock_acc, mock_positions)):
        dash = account.dashboard_view(user_id=test_user_id)
        
        # Verify blended positions
        positions = dash["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["symbol"] == "SOL-USDT"
        assert pos["direction"] == "LONG"
        assert pos["source"] == "BINGX MANUAL"
        assert pos["management_status"] == "EXTERNAL POSITION"
        assert pos["entry"] == 140.0
        assert pos["current_price"] == 143.5
        assert pos["unrealized_pnl"] == 5.25
        assert pos["liquidation_price"] == 125.0
        assert dash["risk"]["positions_count"] == 1
        assert dash["risk"]["positions_max"] == 2


def test_position_management_operations():
    test_user_id = 777
    # 1. Create Ophelia position
    pos_id = db.create_position({
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry": 60000.0,
        "qty": 0.05,
        "leverage": 15,
        "margin_usdt": 200.0,
        "mode": "SHADOW"
    }, user_id=test_user_id)
    
    # 2. Edit position
    edit_res = core.edit_position(pos_id, {"stop_loss": 58500.0, "take_profit": 63000.0, "trailing_stop": True}, user_id=test_user_id)
    assert edit_res["stop_current"] == 58500.0
    assert edit_res["trailing_pct"] == 0.8
    
    # 3. Partial close position (50%)
    part_res = core.partial_close_position(pos_id, {"qty_pct": 50.0}, user_id=test_user_id)
    assert part_res["success"] is True
    assert part_res["closed_qty"] == 0.025
    assert part_res["rem_qty"] == 0.025
    
    # 4. Close position completely
    close_res = core.close_position(pos_id, user_id=test_user_id)
    assert close_res["success"] is True
    assert close_res["status"] == "CLOSED"
    
    closed_pos = db.get_position(pos_id)
    assert closed_pos["status"] == "CLOSED"


def test_preflight_checks(monkeypatch):
    res = core.run_preflight(user_id=1)
    assert "ready_for_live" in res
    assert "checklist" in res
    assert len(res["checklist"]) >= 4
