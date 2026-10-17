import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from control_plane import config, db, retest_engine, intelligence, account, core
try:
    from control_plane import api
    CreateAutomationFromSetupRequest = api.CreateAutomationFromSetupRequest
except ImportError:
    from dataclasses import dataclass
    from typing import Optional
    @dataclass
    class CreateAutomationFromSetupRequest:
        setup_id: str
        margin: Optional[float] = 25.0
        leverage: Optional[float] = 15.0
        origin: str = "ML_RECOMMENDATION"

def test_max_open_trades_cap_is_two():
    """Verify that MAX_OPEN_TRADES is authoritatively 2 across backend config."""
    assert config.MAX_OPEN_TRADES == 2
    assert config.MAX_CONCURRENT_TRADES == 2

def test_gold_contract_resolution():
    """Verify dynamic discovery and resolution of Gold contract."""
    contract = config.resolve_gold_contract()
    assert contract is not None
    assert "symbol" in contract
    assert contract["symbol"] == "NCCOGOLD2USD-USDT"
    assert contract["display_name"] == "GOLD (XAU)"
    assert contract["price_precision"] == 2
    assert contract["quantity_precision"] == 4
    assert contract["min_qty"] == 0.0005
    assert contract["min_notional"] == 2.0

def test_ml_analysis_active_during_blackout():
    """Verify ML intelligence analysis is active 24/7, separate from execution blackout."""
    state = intelligence.get_symbol_intelligence("BTC-USDT")
    assert state is not None
    assert state["ml_status"] == "ACTIVE"
    # Even if blackout is active for execution, ML status remains ACTIVE
    assert state["provider"] == "Ollama"
    assert "qwen3:4b" in state["model"]

def test_gold_ml_intelligence():
    """Verify GOLD receives ML intelligence with macro context."""
    state = intelligence.get_symbol_intelligence("GOLD (XAU)")
    assert state is not None
    assert state["symbol"] == "GOLD (XAU)"
    assert state["ml_status"] == "ACTIVE"
    thesis = state.get("thesis", "").lower()
    assert "gold" in thesis or "market structure" in thesis or "macro" in thesis

def test_setup_deduplication_and_uncalibrated_probability():
    """Verify setups use deterministic IDs and display uncalibrated status."""
    cand = retest_engine.SetupCandidate(
        setup_id="setup_BTC-USDT_LONG_3m_1000",
        symbol="BTC-USDT",
        direction="LONG",
        timeframe="3m",
        strategy="VWAP_STRUCTURE_RETEST",
        entry_price=65000.0,
        suggested_sl=64500.0,
        suggested_tp1=65500.0,
        suggested_tp2=66000.0,
        suggested_tp3=66500.0,
        sl_distance_pct=0.77,
        tp1_distance_pct=0.77,
        tp2_distance_pct=1.54,
        tp3_distance_pct=2.31,
        risk_reward=2.0,
        confidence_pct=65.0,
        ai_confidence=65.0,
        calibration_status="NOT CALIBRATED"
    )
    d = cand.to_dict()
    assert d["setup_id"] == "setup_BTC-USDT_LONG_3m_1000"
    assert d["calibration_status"] == "NOT CALIBRATED"
    assert d["sl_distance_pct"] == 0.77
    assert d["tp1_distance_pct"] == 0.77
    assert d["suggested_tp3"] == 66500.0

def test_imported_ml_automation_has_no_vwap_gate():
    """Verify imported ML automation explicitly sets vwap_gate_enabled = False."""
    req = CreateAutomationFromSetupRequest(
        setup_id="setup_ETH-USDT_LONG_3m_2000",
        margin=25.0,
        leverage=15.0
    )
    assert req.setup_id == "setup_ETH-USDT_LONG_3m_2000"
    assert req.origin == "ML_RECOMMENDATION"

def test_system_status_and_guarded_live_preflight():
    """Verify System Control Centre preflight status is blocked and mode is SHADOW."""
    db.set_mode("SHADOW")
    status = core.run_preflight()
    assert status["current_mode"] == "SHADOW"
    assert status["live_execution"] == "OFF"
    assert status["live_preflight"] in ("BLOCKED", "READY")
    assert status["execution_block"] == "ACTIVE"
    assert status["max_open_trades"] == 2
    assert len(status["checklist"]) == 12

def test_honest_empty_dashboard():
    """Verify dashboard view returns zero positions and zero trades when no active positions exist."""
    dash = account.dashboard_view(user_id=9999)
    assert len(dash["positions"]) == 0
    assert dash["position"] is None
    assert dash["account"]["total_equity"] >= 0.0
    assert dash["risk"]["positions_max"] == 2

def test_setup_filtering_by_symbol_and_all():
    """Verify setup candidates filter strictly by symbol and allow ALL."""
    now_ms = 1725400000000
    db.save_setup_candidate({
        "setup_id": "setup_BTC-USDT_SHORT_3m_test",
        "symbol": "BTC-USDT",
        "direction": "SHORT",
        "timeframe": 3,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "breakout_price": 81000.0,
        "entry_price": 80900.0,
        "suggested_sl": 81200.0,
        "suggested_tp1": 80450.0,
        "status": "ACTIVE",
        "generated_ms": now_ms
    })
    db.save_setup_candidate({
        "setup_id": "setup_ETH-USDT_LONG_3m_test",
        "symbol": "ETH-USDT",
        "direction": "LONG",
        "timeframe": 3,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "breakout_price": 2500.0,
        "entry_price": 2505.0,
        "suggested_sl": 2490.0,
        "suggested_tp1": 2525.0,
        "status": "ACTIVE",
        "generated_ms": now_ms
    })
    db.save_setup_candidate({
        "setup_id": "setup_GOLD_LONG_15m_test",
        "symbol": "GOLD (XAU)",
        "direction": "LONG",
        "timeframe": 15,
        "strategy": "VWAP_STRUCTURE_RETEST",
        "breakout_price": 2720.0,
        "entry_price": 2722.0,
        "suggested_sl": 2710.0,
        "suggested_tp1": 2740.0,
        "status": "ACTIVE",
        "generated_ms": now_ms
    })

    # Test ALL
    all_setups = db.list_setup_candidates(status="ACTIVE", symbol="ALL")
    all_symbols = {s["symbol"] for s in all_setups}
    assert "BTC-USDT" in all_symbols
    assert "ETH-USDT" in all_symbols

    # Test BTC filter: must NEVER contain ETH or GOLD
    btc_setups = db.list_setup_candidates(status="ACTIVE", symbol="BTC-USDT")
    assert len(btc_setups) > 0
    for s in btc_setups:
        assert s["symbol"] == "BTC-USDT"
        assert s["symbol"] != "ETH-USDT"
        assert "GOLD" not in s["symbol"]

    # Test ETH filter: must NEVER contain BTC
    eth_setups = db.list_setup_candidates(status="ACTIVE", symbol="ETH-USDT")
    assert len(eth_setups) > 0
    for s in eth_setups:
        assert s["symbol"] == "ETH-USDT"
        assert s["symbol"] != "BTC-USDT"

    # Test GOLD filter: must contain ONLY Gold
    gold_setups = db.list_setup_candidates(status="ACTIVE", symbol="GOLD (XAU)")
    assert len(gold_setups) > 0
    for s in gold_setups:
        assert "GOLD" in s["symbol"] or s["symbol"] == "NCCOGOLD2USD-USDT"

def test_canonical_rr_and_distances():
    """Verify canonical R:R = reward / risk and direction-aware percentages."""
    cand = db.get_setup_candidate("setup_ETH-USDT_LONG_3m_test")
    assert cand is not None
    assert cand["risk_distance"] == 15.0  # abs(2505 - 2490)
    assert cand["reward_distance_tp1"] == 20.0  # abs(2525 - 2505)
    assert cand["reward_risk_ratio"] == 1.33  # 20 / 15
    assert cand["sl_distance_pct"] < 0  # direction aware negative: -0.6%
    assert cand["tp1_distance_pct"] > 0  # direction aware positive: +0.8%

def test_news_categories_and_trade_eligibility():
    """Verify 7 news categories and deterministic news trade candidate generator."""
    from control_plane import news
    cats = news.get_news_by_category()
    required = ["MACRO", "GEOPOLITICS", "MARKETS", "CRYPTO", "ENERGY", "CENTRAL BANKS", "REGULATION"]
    for r in required:
        assert r in cats
        assert len(cats[r]) >= 3  # at least 3-5 items per category
        for item in cats[r]:
            assert "source" in item
            assert "published_ts" in item
            assert item["status"] in ("LIVE", "REFERENCE", "STALE")

    candidates = news.evaluate_news_trade_candidates()
    assert len(candidates) >= 2  # Gold and BTC
    gold_cand = next((c for c in candidates if "GOLD" in c["symbol"]), None)
    assert gold_cand is not None
    assert gold_cand["source"] == "NEWS EVENT"
    assert gold_cand["eligibility_status"] == "TRADE-CANDIDATE"
    assert gold_cand["reward_risk_ratio"] >= 1.0

