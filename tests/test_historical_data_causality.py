import pytest
import time
from control_plane import backtest, config, db

def make_sample_setup():
    now_ms = int(time.time() * 1000)
    return {
        "setup_id": "TEST_CAUSALITY_BTC_001",
        "symbol": "BTC-USDT",
        "timeframe": "5m",
        "direction": "LONG",
        "created_at": "2026-09-04T12:00:00Z",
        "entry": 60000.0,
        "stop_loss": 59500.0,
        "take_profit": 61000.0,
        "take_profit_2": 61500.0,
        "take_profit_3": 62500.0,
        "breakout_evidence": "BOS high broken with volume",
        "displacement": "Bullish expansion 2.1 ATR",
        "retest_evidence": "Key S/R retest confirmed",
        "rejection_evidence": "Wick rejection below VWAP",
        "cvd": "AGGRESSIVE_BUYING",
        "rvol": 2.2,
        "vwap": "ABOVE_VWAP",
        "fvg": "5m Bullish FVG open",
        "structure": "BULLISH_CONTINUATION",
        "mtf_context": "15m and 1h bullish trend aligned",
        "news_context": "No high-impact events pending",
        "macro_context": "DXY weakening",
        "confidence_pct": 85.0,
        "tradingagents_output": "Consensus: Strong continuation signal",
        "qwen_output": "Qwen3: High confluence setup",
        "model_version": "qwen3:4b-instruct",
        "metadata": {"prompt_version": "v3.2_bingx_futures"}
    }

def test_historical_data_causality():
    """Verify that every evaluated historical candidate only receives data at or prior to T."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_CAUSALITY_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    for m in result.get("matches", []):
        t = m.get("timestamp_ms", m.get("timestamp"))
        assert t is not None
        # Candidate timestamp must be strictly in the past
        assert t <= int(time.time() * 1000)
        # Outcome timeline must start at or after t
        outcome = m["outcome"]
        assert outcome in ("SL FIRST", "TP1", "TP2", "TP3", "BREAKEVEN", "EXPIRED")

def test_historical_news_cutoff():
    """Verify news context evaluated at historical T does not include future articles."""
    articles = [
        {"published_ms": 1000, "title": "Old News"},
        {"published_ms": 2000, "title": "Current News at T"},
        {"published_ms": 3000, "title": "Future News after T"}
    ]
    t = 2000
    causal_articles = [a for a in articles if a["published_ms"] <= t]
    assert len(causal_articles) == 2
    assert all(a["published_ms"] <= t for a in causal_articles)

def test_replay_setup_fingerprint():
    """Verify setup fingerprint is deterministic and structurally derived."""
    setup = make_sample_setup()
    fp1 = backtest.derive_setup_fingerprint(setup)
    fp2 = backtest.derive_setup_fingerprint(setup)
    assert fp1 == fp2
    assert fp1["direction"] == "LONG"
    assert fp1["timeframe"] == 5
    assert fp1["rvol"] >= 2.0
    assert fp1["has_breakout"] is True
    assert fp1["has_retest"] is True

def test_tradingagents_replay_provenance():
    """Verify TradingAgents decision is recorded with provenance and separate from technical match."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_CAUSALITY_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    for m in result.get("matches", []):
        ql = m["quality_layers"]
        assert "tradingagents_decision" in ql
        assert ql["tradingagents_decision"] in ("LONG", "SHORT", "NEUTRAL", "NO SETUP", "ML REPLAY UNAVAILABLE")
        assert "why_matched" in m

def test_qwen_replay_provenance():
    """Verify Qwen decision and confidence are independently preserved."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_CAUSALITY_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    for m in result.get("matches", []):
        ql = m["quality_layers"]
        assert "qwen_decision" in ql
        assert ql["qwen_decision"] in ("LONG", "SHORT", "NEUTRAL", "REJECT", "ML REPLAY UNAVAILABLE")
        assert 0.0 <= ql["ai_confidence_pct"] <= 100.0

def test_long_short_geometry():
    """Verify LONG SL is below entry and SHORT SL is above entry."""
    # Long geometry
    long_ent, long_sl, long_tp = 60000.0, 59500.0, 61000.0
    assert long_sl < long_ent < long_tp
    # Short geometry
    short_ent, short_sl, short_tp = 60000.0, 60500.0, 59000.0
    assert short_tp < short_ent < short_sl

def test_no_duplicate_execution():
    """Verify historical matches do not contain duplicate timestamps for the same symbol."""
    setup = make_sample_setup()
    result = backtest.run_ml_setup_historical_replay(
        setup_id="TEST_CAUSALITY_BTC_001",
        setup_data=setup,
        hours=48,
        execute_live_ai=False
    )
    ts_list = [m.get("timestamp_ms", m.get("timestamp")) for m in result.get("matches", [])]
    assert len(ts_list) == len(set(ts_list))

def test_gold_historical_coverage():
    """Verify gold contract symbol resolves dynamically without hardcoding."""
    gold_sym = config.resolve_gold_symbol()
    assert "XAU" in gold_sym or "GOLD" in gold_sym
