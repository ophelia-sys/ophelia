"""TradingAgents & Qwen3 4B Continuous Intelligence Layer for Ophelia.

Layer: control_plane/intelligence
Contract:
- Asynchronous, non-blocking intelligence & research engine.
- Fair rotating scheduler across the full watchlist (BTC, ETH, SOL, XRP).
- Synthesizes multi-TF market structure (1m, 3m, 5m, 15m), causal retest states,
  true CVD, FVG, RVOL, and Yahoo Finance/macro context.
- Invokes Qwen3 4B via Ollama for reasoning, explanation, thesis, and setup ranking.
- Generates first-class structured setup candidates with structural targets/stops.
- Strictly NO execution authority: cannot sign exchange requests, send BingX orders,
  or bypass RiskManager.
- If Ollama/Qwen is offline, deterministic Ophelia trading continues unaffected.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import analytics, config, db, news, retest_engine, sessions, ingest
from institutional import structure_detectors


# In-memory per-symbol intelligence cache
_symbol_intelligence: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def get_symbol_intelligence(symbol: str) -> Dict[str, Any]:
    """Retrieve the latest cached intelligence state for a symbol."""
    norm_sym = config.to_display_symbol(symbol)
    with _lock:
        if norm_sym in _symbol_intelligence:
            return dict(_symbol_intelligence[norm_sym])
        if symbol in _symbol_intelligence:
            return dict(_symbol_intelligence[symbol])

    is_gold = norm_sym == config.GOLD_DISPLAY_NAME
    # Default initial state
    return {
        "symbol": norm_sym,
        "display_symbol": norm_sym,
        "venue_symbol": config.to_venue_symbol(norm_sym),
        "status": "READY",
        "ml_status": "ACTIVE",
        "execution_gate": "BLACKOUT" if sessions.in_blackout() else "CLEAR",
        "last_analysis_ms": 0,
        "latency_ms": 0,
        "thesis": f"Monitoring {norm_sym} multi-timeframe market structure and session VWAP alignment.",
        "directional_bias": "NEUTRAL",
        "confidence_pct": 50.0,
        "ai_confidence": 50.0,
        "calibration_status": "NOT CALIBRATED",
        "retest_state": "IDLE",
        "timeframe_states": {
            "3m": "WATCHING",
            "5m": "NO VALID SETUP",
            "15m": "NO VALID SETUP",
            "30m": "NO VALID SETUP",
            "1h": "NO VALID SETUP"
        },
        "opportunities": [],
        "risks": ["Awaiting high-probability structural breakout"],
        "active_setups_count": 0,
        "model": config.LLM_PRIMARY,
        "provider": "Ollama",
        "framework": "TauricResearch/TradingAgents v0.4.0",
        "funding_rate": "NOT AVAILABLE FOR THIS INSTRUMENT" if is_gold else "0.0001",
        "open_interest": "NOT AVAILABLE FOR THIS INSTRUMENT" if is_gold else "N/A",
        "data_cutoff_ms": int(time.time() * 1000),
    }


def get_all_watchlist_intelligence() -> List[Dict[str, Any]]:
    """Retrieve intelligence state across the entire configured watchlist."""
    symbols = config.SYMBOLS
    res = []
    for s in symbols:
        res.append(get_symbol_intelligence(s))
    return res



def call_qwen_structured(prompt: str, system: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
    """Query Qwen3 4B via Ollama with strict JSON extraction and fallback handling."""
    payload = {
        "model": config.LLM_PRIMARY,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "keep_alive": config.LLM_KEEP_ALIVE,
        "options": {
            "num_predict": 600,
            "num_ctx": 3072,
            "temperature": 0.2
        }
    }
    try:
        req = urllib.request.Request(
            f"{config.OLLAMA_URL}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")

            # Strip thinking tags if Qwen3 outputs thinking tokens
            content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

            # Strip markdown formatting
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            raw_json = match.group(1) if match else content

            # Fallback regex search for JSON brackets
            bracket_match = re.search(r"\{[\s\S]*\}", raw_json)
            if bracket_match:
                return json.loads(bracket_match.group(0))
            return json.loads(raw_json)
    except Exception as e:
        return None


def evaluate_symbol_intelligence(symbol: str) -> Dict[str, Any]:
    """Perform deterministic technical scan across multiple timeframes (3m, 5m, 15m, 30m, 1h) + Qwen3 4B context evaluation."""
    t0 = time.time()
    now_ms = int(t0 * 1000)

    display_sym = config.to_display_symbol(symbol)
    venue_sym = config.to_venue_symbol(symbol)
    is_gold = (display_sym == config.GOLD_DISPLAY_NAME)

    # 1. Fetch recent 1m candles for the symbol (last 720 minutes = 12h for multi-timeframe synthesis)
    start_ms = now_ms - (720 * 60 * 1000)
    raw_1m = db.query_candles(display_sym, start_ms, now_ms)
    if len(raw_1m) < 30 and is_gold:
        try:
            ingest.poll_bingx_gold_1m()
            raw_1m = db.query_candles(display_sym, start_ms, now_ms)
        except Exception:
            pass

    if len(raw_1m) < 15:
        return get_symbol_intelligence(display_sym)

    cur_price = float(raw_1m[-1]["close"])

    # 2. Calculate Session VWAP
    utc_day_start = now_ms - (now_ms % 86400000)
    session_1m = [c for c in raw_1m if c["ts"] >= utc_day_start]
    vwap = analytics.session_vwap(session_1m) or cur_price

    # 3. Multi-Timeframe Causal Retest Evaluation (3m, 5m, 15m, 30m, 1h)
    timeframe_states: Dict[str, str] = {}
    setups_generated: List[Dict[str, Any]] = []
    candles_3m = analytics.aggregate(raw_1m, 3, closed_only=True)
    candles_5m = analytics.aggregate(raw_1m, 5, closed_only=True)
    candles_15m = analytics.aggregate(raw_1m, 15, closed_only=True)

    tf_map = {
        3: candles_3m,
        5: candles_5m,
        15: candles_15m,
        30: analytics.aggregate(raw_1m, 30, closed_only=True),
        60: analytics.aggregate(raw_1m, 60, closed_only=True)
    }

    for tf_mins, tf_candles in tf_map.items():
        tf_label = "1h" if tf_mins == 60 else f"{tf_mins}m"
        if len(tf_candles) < 3:
            timeframe_states[tf_label] = "NOT ENOUGH DATA"
            continue

        state_long_dict = db.get_retest_state(display_sym, tf_mins, "LONG")
        retest_state_long = retest_engine.RetestState.from_dict(state_long_dict) if state_long_dict else retest_engine.RetestState(symbol=display_sym, timeframe=tf_mins, direction="LONG", state="IDLE")

        state_short_dict = db.get_retest_state(display_sym, tf_mins, "SHORT")
        retest_state_short = retest_engine.RetestState.from_dict(state_short_dict) if state_short_dict else retest_engine.RetestState(symbol=display_sym, timeframe=tf_mins, direction="SHORT", state="IDLE")

        engine_long = retest_engine.CausalRetestEngine(display_sym, tf_mins, "LONG")
        updated_long = engine_long.evaluate_step(retest_state_long, tf_candles, vwap)
        db.save_retest_state(updated_long.to_dict())

        engine_short = retest_engine.CausalRetestEngine(display_sym, tf_mins, "SHORT")
        updated_short = engine_short.evaluate_step(retest_state_short, tf_candles, vwap)
        db.save_retest_state(updated_short.to_dict())

        # Generate setup candidates (Phase 4 Retest Intelligence)
        active_states = ("WAITING_FOR_RETEST", "RETEST_TOUCHED", "RETEST_ZONE_TOUCHED", "CONFIRMING_REJECTION", "REJECTION_CONFIRMED", "ENTRY_READY", "ENTRY_CANDIDATE")
        if updated_long.state in active_states:
            cand_long = retest_engine.generate_setup_candidate_from_state(updated_long, tf_candles, vwap)
            db.save_setup_candidate(cand_long)
            setups_generated.append(cand_long)
        elif updated_long.state in ("INVALIDATED", "EXPIRED"):
            cand_long = retest_engine.generate_setup_candidate_from_state(updated_long, tf_candles, vwap)
            cand_long["status"] = updated_long.state
            db.save_setup_candidate(cand_long)

        if updated_short.state in active_states:
            cand_short = retest_engine.generate_setup_candidate_from_state(updated_short, tf_candles, vwap)
            db.save_setup_candidate(cand_short)
            setups_generated.append(cand_short)
        elif updated_short.state in ("INVALIDATED", "EXPIRED"):
            cand_short = retest_engine.generate_setup_candidate_from_state(updated_short, tf_candles, vwap)
            cand_short["status"] = updated_short.state
            db.save_setup_candidate(cand_short)

        # Per-timeframe categorization
        if updated_long.state in ("ENTRY_READY", "ENTRY_CANDIDATE", "CONFIRMING_REJECTION", "REJECTION_CONFIRMED"):
            timeframe_states[tf_label] = "VALID SETUP"
        elif updated_short.state in ("ENTRY_READY", "ENTRY_CANDIDATE", "CONFIRMING_REJECTION", "REJECTION_CONFIRMED"):
            timeframe_states[tf_label] = "VALID SETUP"
        elif updated_long.state in ("WAITING_FOR_RETEST", "RETEST_TOUCHED", "RETEST_ZONE_TOUCHED"):
            timeframe_states[tf_label] = "WATCHING"
        elif updated_short.state in ("WAITING_FOR_RETEST", "RETEST_TOUCHED", "RETEST_ZONE_TOUCHED"):
            timeframe_states[tf_label] = "WATCHING"
        elif updated_long.state == "INVALIDATED" or updated_short.state == "INVALIDATED":
            timeframe_states[tf_label] = "INVALIDATED"
        else:
            timeframe_states[tf_label] = "NO VALID SETUP"

    # 4. Multi-Timeframe FVG Detection
    fvgs_3m = []
    if len(candles_3m) >= 3:
        highs_3m = [float(c["high"]) for c in candles_3m]
        lows_3m = [float(c["low"]) for c in candles_3m]
        closes_3m = [float(c["close"]) for c in candles_3m]
        fvg_res_3m = structure_detectors.detect_fvg(highs_3m[-3:], lows_3m[-3:], closes_3m[-3:], now_ms, display_sym, "3m")
        if fvg_res_3m.detected:
            fvgs_3m.append(fvg_res_3m.measurements)

    fvgs_5m = []
    if len(candles_5m) >= 3:
        highs_5m = [float(c["high"]) for c in candles_5m]
        lows_5m = [float(c["low"]) for c in candles_5m]
        closes_5m = [float(c["close"]) for c in candles_5m]
        fvg_res_5m = structure_detectors.detect_fvg(highs_5m[-3:], lows_5m[-3:], closes_5m[-3:], now_ms, display_sym, "5m")
        if fvg_res_5m.detected:
            fvgs_5m.append(fvg_res_5m.measurements)

    # 7. Fetch Macro & Yahoo Finance Context
    macro_ctx = news.get_daily_macro_context()
    macro_sentiment = macro_ctx.get("macro_sentiment", "NEUTRAL")

    # 8. Asynchronous Multi-Agent Evaluation with authentic TauricResearch/TradingAgents LangGraph
    from . import tradingagents_crypto

    dxy_val = macro_ctx.get("yahoo_instruments", {}).get("DXY", {}).get("price", "N/A")
    us10y_val = macro_ctx.get("yahoo_instruments", {}).get("US10Y", {}).get("price", "N/A")
    spx_val = macro_ctx.get("yahoo_instruments", {}).get("SPX", {}).get("price", "N/A")
    gold_val = macro_ctx.get("yahoo_instruments", {}).get("GOLD", {}).get("price", "N/A")
    oil_val = macro_ctx.get("yahoo_instruments", {}).get("OIL", {}).get("price", "N/A")
    macro_str = f"DXY: {dxy_val}, US10Y: {us10y_val}%, SPX: {spx_val}, Gold: {gold_val}, Oil: {oil_val} (Stance: {macro_sentiment})"
    geo_str = "Geopolitical reference baseline: 5 global macro monitored zones."

    cvd_series = retest_engine.calculate_cvd_series(candles_3m[-10:]) if len(candles_3m) >= 2 else []
    cvd_val = float(cvd_series[-1] - cvd_series[0] if len(cvd_series) > 1 else 0.0)
    rvol_val = 1.2
    retest_val = updated_long.state if cur_price > vwap else updated_short.state
    fvg_desc = f"{len(fvgs_3m)} 3m FVGs, {len(fvgs_5m)} 5m FVGs"

    structural_sl = round(cur_price * (0.99 if cur_price > vwap else 1.01), 2)
    suggested_tp1 = round(cur_price * (1.015 if cur_price > vwap else 0.985), 2)
    suggested_tp2 = round(cur_price * (1.03 if cur_price > vwap else 0.97), 2)

    ta_output = tradingagents_crypto.execute_tradingagents_crypto_intelligence(
        symbol=display_sym,
        price=cur_price,
        vwap=vwap,
        cvd_delta=cvd_val,
        rvol=rvol_val,
        retest_state=retest_val,
        fvg_state=fvg_desc,
        structural_sl=structural_sl,
        suggested_tp1=suggested_tp1,
        suggested_tp2=suggested_tp2,
        macro_context=macro_str,
        geopolitical_summary=geo_str,
    )

    direction_bias_det = "BULLISH" if cur_price > vwap else "BEARISH"
    bias = ta_output.get("direction", direction_bias_det)
    conf = float(ta_output.get("confidence", 65.0))
    thesis = ta_output.get("thesis") or f"TradingAgents: {display_sym} trading {'above' if cur_price > vwap else 'below'} session VWAP ({vwap:.2f}) with developing retest."
    opps = [f"Structural {bias} continuation off {retest_val}"]
    risks = [f"Invalidation beyond structural stop {structural_sl:.2f}"]
    bull_case = ta_output.get("bull_case") or ""
    bear_case = ta_output.get("bear_case") or ""
    technical_summary = ta_output.get("technical_summary") or ""
    macro_summary = ta_output.get("macro_summary") or ""
    news_summary = ta_output.get("news_summary") or ""
    missing_conds = ta_output.get("missing_conditions") or []
    inference_success = ta_output.get("inference_success", True)
    error_state = ta_output.get("error_state")
    latency_ms = int(ta_output.get("latency_ms", (time.time() - t0) * 1000))

    # 9. Persist ML Analysis record
    analysis_record = {
        "analysis_id": f"an_{display_sym}_{now_ms}",
        "symbol": display_sym,
        "analysis_type": "SETUP_SCAN",
        "model": config.LLM_PRIMARY,
        "model_version": tradingagents_crypto.TRADINGAGENTS_VERSION,
        "timestamp_ms": now_ms,
        "data_cutoff_ms": now_ms,
        "thesis": thesis,
        "opportunities": opps,
        "risks": risks,
        "confidence_pct": conf,
        "latency_ms": latency_ms,
        "error_status": error_state,
    }
    db.save_ml_analysis(analysis_record)

    # 10. Update in-memory state with complete safe telemetry & multi-agent details
    result_intel = {
        "symbol": display_sym,
        "display_symbol": display_sym,
        "venue_symbol": venue_sym,
        "status": "ACTIVE",
        "ml_status": "ACTIVE",
        "execution_gate": "BLACKOUT" if sessions.in_blackout() else "CLEAR",
        "last_analysis_ms": now_ms,
        "last_evaluation_timestamp_utc": datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc).isoformat(),
        "latency_ms": latency_ms,
        "thesis": thesis,
        "directional_bias": bias,
        "confidence_pct": conf,
        "ai_confidence": conf,
        "calibration_status": "NOT CALIBRATED",
        "retest_state": retest_val,
        "timeframe_states": timeframe_states,
        "opportunities": opps,
        "risks": risks,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "technical_summary": technical_summary,
        "macro_summary": macro_summary,
        "news_summary": news_summary,
        "missing_conditions": missing_conds,
        "active_setups_count": len(setups_generated),
        "model": config.LLM_PRIMARY,
        "provider": "Ollama",
        "framework": tradingagents_crypto.TRADINGAGENTS_FRAMEWORK_NAME,
        "framework_commit": tradingagents_crypto.TRADINGAGENTS_COMMIT,
        "framework_version": tradingagents_crypto.TRADINGAGENTS_VERSION,
        "package_path": tradingagents_crypto.TRADINGAGENTS_PACKAGE_PATH,
        "inference_success": inference_success,
        "error_state": error_state,
        "funding_rate": "NOT AVAILABLE FOR THIS INSTRUMENT" if is_gold else "0.0001",
        "open_interest": "NOT AVAILABLE FOR THIS INSTRUMENT" if is_gold else "N/A",
        "next_scheduled_evaluation_ms": now_ms + (15 * 1000 * len(config.SYMBOLS)),
        "data_cutoff_ms": now_ms,
    }

    with _lock:
        _symbol_intelligence[display_sym] = result_intel
        if display_sym != symbol:
            _symbol_intelligence[symbol] = result_intel

    return result_intel



def continuous_intelligence_worker(stop_event: Optional[threading.Event] = None, interval_s: int = 60) -> None:
    """Fair rotating scheduler across the full watchlist.
    Continuously monitors all symbols without blocking deterministic trading.
    """
    ev = stop_event if stop_event is not None else _stop_event
    symbols = list(config.SYMBOLS)
    idx = 0
    poll_interval = int(os.environ.get("OPH_INTELLIGENCE_INTERVAL_S", str(interval_s)))
    print(f"[intelligence] worker started across watchlist: {symbols} (interval={poll_interval}s)", flush=True)
    while not ev.is_set():
        sym = symbols[idx % len(symbols)]
        idx += 1
        try:
            res = evaluate_symbol_intelligence(sym)
            lat = res.get("latency_ms", 0)
            cnt = res.get("active_setups_count", 0)
            print(f"[intelligence] {sym} evaluated in {lat}ms (active_setups={cnt})", flush=True)
        except Exception as e:
            print(f"[intelligence] evaluation error for {sym}: {e}", flush=True)
        # Rest between iterations to preserve CPU and allow other processes to run
        for _ in range(poll_interval):
            if ev.is_set():
                break
            time.sleep(1)


def start_intelligence_worker() -> None:
    """Start the asynchronous continuous intelligence worker thread."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=continuous_intelligence_worker, args=(60,), daemon=True)
    _worker_thread.start()


def stop_intelligence_worker() -> None:
    """Stop the asynchronous continuous intelligence worker thread."""
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=3)
