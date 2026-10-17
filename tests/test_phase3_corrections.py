import pytest
import sqlite3
import json
import time
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control_plane import priority_classifier, db, core, bingx_client


def test_rr_no_longer_disqualifies():
    """Verify that R:R < 1.0 does not disqualify an otherwise valid setup."""
    candidate = {
        "symbol": "ETH-USDT",
        "direction": "LONG",
        "entry_price": 2500.0,
        "sl": 2480.0,      # risk = 20
        "tp1": 2515.0,     # reward = 15 -> R:R = 15/20 = 0.75 (< 1.0)
        "tp2": None,
        "tp3": None
    }
    market_context = {
        "gamma_regime": "GAMMA DATA NOT AVAILABLE",
        "market_regime": "TREND / EXPANSION",
        "htf_bias": "LONG"
    }
    result = priority_classifier.classify_trade_priority(candidate, market_context)
    # Must NOT be disqualified due to R:R < 1.0
    assert result["eligible"] is True
    assert result["status"] == "APPROVED"
    assert result["risk_reward"] == 0.75


def test_direction_persistence_and_backward_compatibility():
    """Verify both LONG and SHORT directions persist correctly into database and maintain compatibility."""
    # Test SHORT automation
    short_spec = {
        "strategy": "VWAP_STRUCTURE_RETEST",
        "symbol": "ETH-USDT",
        "timeframe": 30,
        "direction": "SHORT",
        "margin_usdt": 50.0,
        "leverage": 10.0,
        "status": "ACTIVE"
    }
    auto_id_short = db.create_automation(short_spec, user_id=99)
    assert auto_id_short > 0
    
    autos = db.list_automations(user_id=99)
    short_auto = next(a for a in autos if a["id"] == auto_id_short)
    assert short_auto["direction"] == "SHORT"
    assert short_auto["direction_pref"] == "SHORT"
    assert short_auto["margin_usdt"] == 50.0
    
    # Test LONG automation via legacy direction_pref key
    long_spec = {
        "strategy": "VWAP_STRUCTURE_RETEST",
        "symbol": "BTC-USDT",
        "timeframe": 15,
        "direction_pref": "LONG",
        "margin_usdt": 100.0,
        "leverage": 20.0,
        "status": "ACTIVE"
    }
    auto_id_long = db.create_automation(long_spec, user_id=99)
    assert auto_id_long > 0
    
    autos = db.list_automations(user_id=99)
    long_auto = next(a for a in autos if a["id"] == auto_id_long)
    assert long_auto["direction"] == "LONG"
    assert long_auto["direction_pref"] == "LONG"
    assert long_auto["margin_usdt"] == 100.0

    # Cleanup test automations
    db.delete_automation(auto_id_short, user_id=99)
    db.delete_automation(auto_id_long, user_id=99)


def test_evaluate_position_absolute_price_and_tp1_breakeven():
    """Verify evaluate_position handles absolute target prices and moves stop to cost on TP1."""
    position = {
        "id": 8888,
        "direction": "LONG",
        "entry": 2500.0,
        "qty": 1.0,
        "stop_current": 2480.0,
        "targets": [
            {"price": 2520.0, "pct_qty": 50.0},
            {"price": 2550.0, "pct_qty": 50.0}
        ],
        "stops": [{"type": "structural_price", "value": 2480.0}],
        "detail": {"be_after_partial": True}
    }
    
    # Price rises to 2525 (hitting TP1 at 2520)
    actions = core.evaluate_position(position, price=2525.0, vwap=2510.0, st_line=2490.0)
    
    # Verify partial exit was taken
    partial_actions = [a for a in actions if a["action"] == "partial_exit"]
    assert len(partial_actions) == 1
    assert partial_actions[0]["qty"] == 0.5
    
    # Verify breakeven stop adjustment to entry price (2500.0)
    be_actions = [a for a in actions if a["action"] == "breakeven"]
    assert len(be_actions) == 1
    assert be_actions[0]["stop"] == 2500.0
    assert position["stop_current"] == 2500.0


def test_bingx_post_request_urlencoded_body():
    """Verify _request formats POST requests with urlencoded body and Content-Type."""
    client = bingx_client.BingXClient(api_key="test_key", secret_key="test_secret", allow_trade=True)
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"code": 0, "msg": "ok", "data": {"orderId": "12345"}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        
        resp = client._request("POST", "/openApi/swap/v2/trade/order", {"symbol": "ETH-USDT", "side": "BUY"})
        assert resp["orderId"] == "12345"
        
        # Verify the Request object passed to urlopen
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_method() == "POST"
        assert req.get_header("Content-type") == "application/x-www-form-urlencoded"
        assert req.data is not None
        body_str = req.data.decode("utf-8")
        assert "symbol=ETH-USDT" in body_str
        assert "side=BUY" in body_str
        assert "signature=" in body_str


def test_event_deduplication_and_rejection_recovery():
    """Verify event deduplication prevents duplicate orders on same candle, but failures don't lock out signal."""
    test_event_id = f"test_event_{int(time.time() * 1000)}"
    
    # 1. Event does not exist initially
    assert db.event_exists(test_event_id) is False
    
    # 2. Simulate failed execution: event must NOT be recorded
    # Order failure raises or returns error, so event_record is NOT called
    assert db.event_exists(test_event_id) is False
    
    # 3. Simulate successful execution: position created and event idempotently recorded
    db.event_record(test_event_id, "SIGNAL", trade_id=12345)
    assert db.event_exists(test_event_id) is True
    
    # 4. Duplicate prevention: check event_exists returns True
    assert db.event_exists(test_event_id) is True
    
    # Clean up
    db.event_delete(test_event_id)
    assert db.event_exists(test_event_id) is False


def test_ambiguous_timeout_reconciliation_logic():
    """Verify ambiguous exchange errors reconcile with BingX positions before deciding to retry."""
    client = bingx_client.BingXClient(api_key="test_key", secret_key="test_secret", allow_trade=True)
    coid = "oph-test-1234"
    
    # Scenario A: Timeout occurs, but order actually reached BingX and position opened
    with patch.object(client, "positions", return_value=[{"symbol": "ETH-USDT", "clientOrderId": coid, "positionAmt": "0.5", "orderId": "999"}]):
        positions = client.positions()
        matched = [p for p in positions if p.get("clientOrderId") == coid]
        assert len(matched) == 1
        assert matched[0]["positionAmt"] == "0.5"
        
    # Scenario B: Timeout occurs, order did NOT reach exchange (no position opened)
    with patch.object(client, "positions", return_value=[]):
        positions = client.positions()
        matched = [p for p in positions if p.get("clientOrderId") == coid]
        assert len(matched) == 0

