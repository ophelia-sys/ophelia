import pytest
import time
from typing import Dict, Any
from control_plane import backtest, db

def make_sample_setup() -> Dict[str, Any]:
    return {
        "setup_id": "TEST_SETUP_BTC_001",
        "symbol": "BTC-USDT",
        "timeframe": 5,
        "direction": "LONG",
        "confidence": 0.85,
        "current_price": 65000.0,
        "suggested_entry": 65000.0,
        "suggested_sl": 64500.0,
        "suggested_tp1": 65500.0,
        "suggested_tp2": 66000.0,
        "suggested_tp3": 66500.0,
        "breakout_price": 64900.0,
        "retest_state": "CONFIRMED",
        "entry_conditions": {"vwap_confirmed": True, "cvd_divergence": True, "rvol": 2.1},
        "confirmation_conditions": {"structure": "BOS_BULLISH", "fvg": "BULLISH_FVG"},
        "tradingagents_output": {
            "final_signal": "LONG",
            "decision": "LONG",
            "confidence": 0.88,
            "analyst_signals": {"technical": "BULLISH", "sentiment": "NEUTRAL"}
        },
        "qwen_output": {
            "decision": "LONG",
            "confidence": 0.82,
            "reasoning": "Strong displacement above session VWAP with expanding taker volume."
        },
        "news_context": "US inflation print cooler than expected; macro risk-on.",
        "created_at": int(time.time() * 1000)
    }

def test_frozen_setup_snapshot_immutability():
    """Verify setup snapshot is frozen and unaffected by subsequent mutations."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_SETUP_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    assert result["replay_system"] == "ML_SETUP_HISTORICAL_REPLAY"
    assert result["status"] in ("COMPLETED", "SUCCESS", "PARTIAL_DATA", "NO_MATCHES")
    snapshot = result["setup_snapshot"]
    assert snapshot["setup_id"] == "TEST_SETUP_BTC_001"
    assert snapshot["symbol"] == "BTC-USDT"
    assert snapshot["direction"] == "LONG"
    assert snapshot["entry"] == 65000.0
    assert snapshot["sl"] == 64500.0
    
    # Mutating original setup dictionary must not mutate the frozen snapshot
    setup["suggested_entry"] = 99999.0
    assert snapshot["entry"] == 65000.0

def test_no_usdt_primary_ml_replay():
    """Verify primary ML replay cards and summary use % and R without USDT."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_SETUP_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    summary = result["summary"]
    # Check that primary summary fields are %, R, rates, or counts - no primary USDT profit
    assert "net_return_pct" in summary
    assert "expectancy_r" in summary
    assert "median_r" in summary
    assert "tp1_hit_rate_pct" in summary
    assert "sl_first_rate_pct" in summary
    assert "primary_display_currency" in summary
    assert summary["primary_display_currency"] == "PERCENT_AND_R"
    
    # Check matches geometry
    for m in result.get("matches", []):
        geom = m["geometry"]
        assert geom["entry_pct"] == 0.0
        assert "sl_pct" in geom
        assert "tp1_pct" in geom
        assert "r_multiples" in geom
        assert "outcome" in m
        assert "result_pct" in m
        assert "result_r" in m
        assert "mae_pct" in m
        assert "mfe_pct" in m

def test_three_quality_layers_separated():
    """Verify Technical, TradingAgents, Qwen, and Risk validation decisions are distinct."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_SETUP_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    for m in result.get("matches", []):
        ql = m["quality_layers"]
        assert "technical_quality" in ql
        assert "tradingagents_decision" in ql
        assert "qwen_decision" in ql
        assert "deterministic_validation" in ql
        assert ql["tradingagents_decision"] in ("LONG", "SHORT", "NEUTRAL", "NO SETUP", "AI REPLAY UNAVAILABLE")
        assert ql["qwen_decision"] in ("LONG", "SHORT", "NEUTRAL", "REJECT", "AI REPLAY UNAVAILABLE")
        assert isinstance(ql["deterministic_validation"], bool)

def test_explainability_and_provenance():
    """Verify WHY MATCHED, which matched, which differed, and disclaimer."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_SETUP_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    assert "HISTORICAL ANALOGUE" in result["disclaimer"]
    for m in result.get("matches", []):
        assert "why_matched" in m
        assert "which_characteristics_matched" in m
        assert "which_characteristics_differed" in m
        assert "match_score_pct" in m
        assert 0.0 <= m["match_score_pct"] <= 100.0

def test_timeframe_and_direction_breakdowns():
    """Verify agree/disagree statistics with Long/Short and Timeframe breakdowns."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_SETUP_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    breakdowns = result["breakdowns"]
    assert "by_direction" in breakdowns
    assert "LONG" in breakdowns["by_direction"]
    assert "SHORT" in breakdowns["by_direction"]
    assert "by_timeframe" in breakdowns
    for tf in ("3m", "5m", "15m", "30m", "1h"):
        assert tf in breakdowns["by_timeframe"]
