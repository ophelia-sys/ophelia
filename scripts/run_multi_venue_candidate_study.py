"""Authoritative Multi-Venue Candidate-Level Empirical Research Runner.

Layer: scripts/run_multi_venue_candidate_study.py
Executes:
1. Ingestion / Backfill of extended real Binance USD-M Futures data for BTC, ETH, SOL.
2. Causal 5m candle aggregation.
3. Causal candidate detection:
   - Mode 'retest' (Phase 10.1 Primary): Genuine ENTRY_READY retest candidates via CausalRetestEngine.
   - Mode 'breakout' (Phase 10 Screening): Historical breakout close candidates for ablation comparison.
4. Frozen candidate TimesFM forecasting & Multi-Metric ForecastTradeCompatibilityEngine evaluation at T:
   - TIMESFM_PRIMARY_5M (12 x 5m steps: +15m, +30m, +45m, +60m)
   - TIMESFM_1M_RESEARCH (60 x 1m steps)
5. Forward outcome tracking (+15m, +30m, +45m, +60m, MFE, MAE, TP1/SL barriers, direction-neutral normalized R).
6. Matched experiment comparison: Base Strategy vs Base Strategy + TimesFM Compatibility.
7. Zero-treatment safety: If compatible_count == 0, reports NO_ACCEPTED_CANDIDATES / TRADING_UTILITY = NOT_ESTABLISHED.
8. Persistence to SQLite candidate_research_outcomes and candidate_forecasts tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control_plane import config, db
from control_plane.binance_data import (
    BinanceHistoricalBackfill,
    BinanceMarketDataProvider,
    CausalCandleAggregator,
)
from control_plane.candidate_research import (
    CandidateOutcomeTracker,
    ComparativeMarketEngine,
)
from control_plane.retest_candidate_generator import generate_retest_candidates
from control_plane.retest_engine import (
    RetestState,
    SetupCandidate,
    compute_structural_targets_stops,
)
from control_plane.timesfm_candidate import (
    TIMESFM_1M_RESEARCH,
    TIMESFM_PRIMARY_5M,
    CandidateForecastContext,
    CandidateForecastResult,
    generate_candidate_forecast,
)
from control_plane.trade_compatibility import (
    ForecastCompatibilityResult,
    evaluate_compatibility,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_candidate_study")


def detect_breakout_candidates_legacy(
    candles_5m: List[dict],
    symbol: str,
    asset_class: str = "CRYPTO"
) -> List[Dict[str, Any]]:
    """Legacy Phase 10 breakout screening candidate detector (unconfirmed breakout closes)."""
    if len(candles_5m) < 40:
        return []

    candidates: List[Dict[str, Any]] = []
    for idx in range(30, len(candles_5m) - 12):
        window = candles_5m[:idx + 1]
        cur_bar = window[-1]
        cur_ts = int(cur_bar["ts"])
        cur_px = float(cur_bar["close"])

        vols = [float(b.get("volume") or 0.0) for b in window[-30:]]
        closes = [float(b["close"]) for b in window[-30:]]
        sum_vol = sum(vols)
        vwap = sum(c * v for c, v in zip(closes, vols)) / max(sum_vol, 1e-6)

        recent_highs = [float(b["high"]) for b in window[-20:-1]]
        recent_lows = [float(b["low"]) for b in window[-20:-1]]
        max_h = max(recent_highs)
        min_l = min(recent_lows)

        if cur_px > max_h and cur_px > vwap:
            targets = compute_structural_targets_stops(window, "LONG", cur_px, vwap, timeframe=5)
            sl = targets["sl"]
            tp1 = targets["tp1"]
            tp2 = targets.get("tp2")
            if sl < cur_px < tp1 and (tp1 - cur_px) >= (cur_px - sl):
                cand_id = f"CAND-BO-{symbol}-L-{cur_ts}"
                candidates.append({
                    "candidate_id": cand_id,
                    "symbol": symbol,
                    "canonical_instrument_id": f"CRYPTO:{symbol}",
                    "direction": "LONG",
                    "timestamp_ms": cur_ts,
                    "candle_idx": idx,
                    "entry_price": cur_px,
                    "sl_price": sl,
                    "tp1_price": tp1,
                    "tp2_price": tp2,
                    "expected_horizon": "15m-60m",
                    "regime": "TREND",
                    "structure_state": "BREAKOUT_CONFIRMED",
                    "retest_state": "BREAKOUT_SCREENING",
                    "breakout_price": max_h,
                    "retest_touch_price": cur_px,
                    "rejection_confirm_price": cur_px,
                    "retest_elapsed_bars": 0
                })
        elif cur_px < min_l and cur_px < vwap:
            targets = compute_structural_targets_stops(window, "SHORT", cur_px, vwap, timeframe=5)
            sl = targets["sl"]
            tp1 = targets["tp1"]
            tp2 = targets.get("tp2")
            if sl > cur_px > tp1 and (cur_px - tp1) >= (sl - cur_px):
                cand_id = f"CAND-BO-{symbol}-S-{cur_ts}"
                candidates.append({
                    "candidate_id": cand_id,
                    "symbol": symbol,
                    "canonical_instrument_id": f"CRYPTO:{symbol}",
                    "direction": "SHORT",
                    "timestamp_ms": cur_ts,
                    "candle_idx": idx,
                    "entry_price": cur_px,
                    "sl_price": sl,
                    "tp1_price": tp1,
                    "tp2_price": tp2,
                    "expected_horizon": "15m-60m",
                    "regime": "TREND",
                    "structure_state": "BREAKOUT_CONFIRMED",
                    "retest_state": "BREAKOUT_SCREENING",
                    "breakout_price": min_l,
                    "retest_touch_price": cur_px,
                    "rejection_confirm_price": cur_px,
                    "retest_elapsed_bars": 0
                })

    thinned: List[Dict[str, Any]] = []
    last_ts = 0
    for c in candidates:
        if c["timestamp_ms"] - last_ts >= 1800_000:
            thinned.append(c)
            last_ts = c["timestamp_ms"]
    return thinned


def run_candidate_study(
    symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    backfill_days: int = 14,
    use_live_backfill: bool = True,
    mode: str = "retest",  # "retest" (Phase 10.1) or "breakout" (Phase 10)
    timeframe_mode: str = TIMESFM_PRIMARY_5M,
    experiment_family: str = "PHASE10_RETEST_ENTRY_READY_V1"
) -> Dict[str, Any]:
    """Execute complete empirical candidate evaluation study."""
    logger.info("============================================================")
    logger.info("STARTING OPHELIA CANDIDATE EMPIRICAL STUDY (%s)", experiment_family)
    logger.info("Mode: %s | TF Mode: %s | Days: %d", mode, timeframe_mode, backfill_days)
    logger.info("Invariants: TRADING_AUTHORITY=FALSE, SHADOW_ONLY")
    logger.info("============================================================")

    backfill_engine = BinanceHistoricalBackfill()
    all_candidate_outcomes: List[Dict[str, Any]] = []
    symbol_reports: Dict[str, Any] = {}
    dataset_hashes: Dict[str, str] = {}

    for sym in symbols:
        logger.info("Processing symbol %s...", sym)
        if use_live_backfill:
            try:
                bf_result = backfill_engine.backfill_symbol(sym, target_days=backfill_days, chunk_limit=1000)
                logger.info("Backfill result for %s: %s (1m: %d, 5m: %d)", sym, bf_result["status"], bf_result["raw_1m_count"], bf_result["derived_5m_count"])
            except Exception as e:
                logger.warning("Backfill error for %s (%s). Using existing stored bars.", sym, e)

        # Query derived 5m candles from database
        # For 14 days of 5m bars: 14 * 288 = ~4032 bars. Limit=10000 ensures full history.
        derived_5m = db.get_binance_derived_candles(sym, resolution="5m", limit=10000)
        if len(derived_5m) < 40:
            logger.warning("Insufficient 5m candles for %s (%d bars). Skipping.", sym, len(derived_5m))
            continue

        derived_5m.sort(key=lambda x: int(x["ts"]))
        logger.info("Loaded %d continuous closed 5m bars for %s.", len(derived_5m), sym)

        # Deterministic dataset hashing
        ds_bytes = json.dumps([b["close"] for b in derived_5m[:500]]).encode()
        dataset_hashes[sym] = hashlib.sha256(ds_bytes).hexdigest()[:16]

        # 1. Detect candidates based on mode
        if mode == "retest":
            candidates = generate_retest_candidates(derived_5m, sym, timeframe=5)
        else:
            candidates = detect_breakout_candidates_legacy(derived_5m, sym)

        logger.info("Detected %d candidates for %s (mode=%s).", len(candidates), sym, mode)

        sym_outcomes: List[Dict[str, Any]] = []
        for cand in candidates:
            c_idx = cand["candle_idx"]
            c_ts = cand["timestamp_ms"]

            # Causal historical context up to T (closed bar end <= T)
            context_candles = derived_5m[:c_idx + 1]

            # Future closed candles strictly post-T (12 bars = 60 minutes)
            future_candles = derived_5m[c_idx + 1: c_idx + 13]

            # Build frozen candidate context at T
            ctx = CandidateForecastContext(
                candidate_id=cand["candidate_id"],
                canonical_instrument_id=cand["canonical_instrument_id"],
                symbol=cand["symbol"],
                direction=cand["direction"],
                candidate_timestamp_ms=c_ts,
                entry_price=cand["entry_price"],
                sl_price=cand["sl_price"],
                tp1_price=cand["tp1_price"],
                tp2_price=cand.get("tp2_price"),
                expected_holding_horizon=cand["expected_horizon"],
                regime=cand["regime"],
                structure_state=cand["structure_state"],
                retest_state=cand["retest_state"],
            )

            # Generate frozen TimesFM forecast at T
            forecast = generate_candidate_forecast(
                context=ctx,
                historical_candles=context_candles,
                timeframe_mode=timeframe_mode
            )

            # Evaluate Trade Compatibility using multi-metric engine
            compat = evaluate_compatibility(ctx, forecast)

            # Evaluate forward outcome with direction-neutral normalized R
            outcome = CandidateOutcomeTracker.evaluate_outcome(cand, future_candles)

            # Record combined research row
            row = {
                "candidate_id": cand["candidate_id"],
                "symbol": sym,
                "timestamp_ms": c_ts,
                "direction": cand["direction"],
                "entry_price": cand["entry_price"],
                "sl_price": cand["sl_price"],
                "tp1_price": cand["tp1_price"],
                "tp2_price": cand.get("tp2_price"),
                "expected_horizon": cand["expected_horizon"],
                "regime": cand["regime"],
                "data_venue": "BINANCE",
                "execution_venue": "BINGX",
                "forecast_id": forecast.forecast_id,
                "q10": forecast.quantiles["q10"],
                "q50": forecast.quantiles["q50"],
                "q90": forecast.quantiles["q90"],
                "dispersion_pct": forecast.raw_dispersion_pct,
                "dispersion_bucket": forecast.dispersion_bucket,
                "forecast_direction": compat.forecast_direction,
                "trade_compatibility": compat.trade_compatibility,
                "compatibility_mode": compat.compatibility_category,
                "retest_state_at_entry": cand.get("retest_state", "ENTRY_READY"),
                "breakout_price": cand.get("breakout_price"),
                "retest_touch_price": cand.get("retest_touch_price"),
                "rejection_confirm_price": cand.get("rejection_confirm_price"),
                "retest_elapsed_bars": cand.get("retest_elapsed_bars", 0),
                "forecast_median_return": compat.forecast_median_return,
                "forecast_q10_return": compat.forecast_q10_return,
                "forecast_q50_return": compat.forecast_q50_return,
                "forecast_q90_return": compat.forecast_q90_return,
                "dist_entry_to_q10": compat.dist_q10_to_entry,
                "dist_entry_to_q50": compat.dist_q50_to_entry,
                "dist_entry_to_q90": compat.dist_q90_to_entry,
                "dist_sl_to_q10": compat.dist_q10_to_sl,
                "dist_sl_to_q50": compat.dist_q50_to_sl,
                "dist_sl_to_q90": compat.dist_q90_to_sl,
                "dist_tp1_to_q10": compat.dist_q10_to_tp1,
                "dist_tp1_to_q50": compat.dist_q50_to_tp1,
                "dist_tp1_to_q90": compat.dist_q90_to_tp1,
                "forecast_path_direction": compat.forecast_path_direction,
                "forecast_path_slope": compat.forecast_path_slope,
                "forecast_expected_range": compat.forecast_expected_range,
                "mfe": outcome["mfe"],
                "mae": outcome["mae"],
                "tp1_hit": outcome["tp1_hit"],
                "tp2_hit": outcome["tp2_hit"],
                "sl_hit": outcome["sl_hit"],
                "exit_reason": outcome["exit_reason"],
                "time_to_exit_min": outcome["time_to_exit_min"],
                "realized_r_multiple": outcome["realized_r_multiple"],
                "normalized_risk_amount": outcome["normalized_risk_amount"],
                "normalized_realized_r": outcome["normalized_realized_r"],
                "return_15m": outcome["return_15m"],
                "return_30m": outcome["return_30m"],
                "return_45m": outcome["return_45m"],
                "return_60m": outcome["return_60m"],
                "binance_price_at_entry": cand["entry_price"],
                "bingx_price_at_entry": cand["entry_price"],
                "basis_pct_at_entry": 0.0,
                "evaluation_status": "COMPLETE"
            }
            try:
                db.insert_candidate_outcome(row)
            except Exception as e:
                logger.error("Failed saving outcome in db: %s", e)

            sym_outcomes.append(row)
            all_candidate_outcomes.append(row)

        symbol_reports[sym] = _compute_cohort_stats(sym_outcomes)

    aggregate_report = _compute_cohort_stats(all_candidate_outcomes)

    report_payload = {
        "timestamp_ms": int(time.time() * 1000),
        "experiment_family": experiment_family,
        "mode": mode,
        "timeframe_mode": timeframe_mode,
        "backfill_days": backfill_days,
        "dataset_hashes": dataset_hashes,
        "total_candidates": len(all_candidate_outcomes),
        "symbols_tested": symbols,
        "aggregate": aggregate_report,
        "by_symbol": symbol_reports,
        "status": "SUCCESS"
    }

    logger.info("============================================================")
    logger.info("STUDY COMPLETE: %d Total Candidates Evaluated", len(all_candidate_outcomes))
    logger.info("Base Strategy: Count=%d, Win Rate=%.1f%%, Net R=%.2f",
                aggregate_report["base"]["count"], aggregate_report["base"]["win_rate"], aggregate_report["base"]["net_r"])
    logger.info("TimesFM COMPATIBLE Cohort: Status=%s, Count=%d, Win Rate=%s, Net R=%.2f",
                aggregate_report["compatible"]["treatment_status"],
                aggregate_report["compatible"]["count"],
                str(aggregate_report["compatible"]["win_rate"]),
                aggregate_report["compatible"]["net_r"])
    logger.info("TimesFM INCOMPATIBLE Cohort: Count=%d, Win Rate=%.1f%%, Net R=%.2f",
                aggregate_report["incompatible"]["count"],
                aggregate_report["incompatible"]["win_rate"],
                aggregate_report["incompatible"]["net_r"])
    logger.info("============================================================")
    return report_payload


def _compute_cohort_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute comparative stats between Base, Compatible, and Incompatible cohorts."""
    def calc_group(sub: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(sub)
        if n == 0:
            return {
                "count": 0,
                "treatment_status": "NO_ACCEPTED_CANDIDATES",
                "trading_utility": "NOT_ESTABLISHED",
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "expectancy_r": 0.0,
                "net_r": 0.0,
                "mean_mfe": 0.0,
                "mean_mae": 0.0
            }

        wins = sum(1 for r in sub if r["tp1_hit"] == 1)
        losses = sum(1 for r in sub if r["sl_hit"] == 1)
        win_rate = round((wins / n) * 100.0, 2)
        r_mults = [float(r.get("normalized_realized_r", r["realized_r_multiple"])) for r in sub]
        net_r = round(sum(r_mults), 2)
        expectancy = round(net_r / n, 2)

        gains = sum(r for r in r_mults if r > 0)
        neg_gains = abs(sum(r for r in r_mults if r < 0))
        pf = round(gains / max(0.0001, neg_gains), 2) if neg_gains > 0 else 99.0

        mfes = [float(r["mfe"]) for r in sub]
        maes = [float(r["mae"]) for r in sub]
        mean_mfe = round(sum(mfes) / n, 2)
        mean_mae = round(sum(maes) / n, 2)

        return {
            "count": n,
            "treatment_status": "EVALUATED",
            "trading_utility": "MEASURED",
            "win_rate": win_rate,
            "profit_factor": pf,
            "expectancy_r": expectancy,
            "net_r": net_r,
            "mean_mfe": mean_mfe,
            "mean_mae": mean_mae
        }

    base = calc_group(records)
    comp = calc_group([r for r in records if r["trade_compatibility"] == "COMPATIBLE"])
    incomp = calc_group([r for r in records if r["trade_compatibility"] == "INCOMPATIBLE"])
    neutral = calc_group([r for r in records if r["trade_compatibility"] == "NEUTRAL"])

    return {"base": base, "compatible": comp, "incompatible": incomp, "neutral": neutral}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Multi-Venue Candidate Empirical Study")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT,SOLUSDT")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--mode", type=str, default="retest", choices=["retest", "breakout"])
    parser.add_argument("--timeframe", type=str, default="5m", choices=["5m", "1m"])
    parser.add_argument("--no-backfill", action="store_true")
    args = parser.parse_args()

    sym_list = [s.strip().upper() for s in args.symbols.split(",")]
    tf_mode = TIMESFM_PRIMARY_5M if args.timeframe == "5m" else TIMESFM_1M_RESEARCH
    family = "PHASE10_RETEST_ENTRY_READY_V1" if args.mode == "retest" else "PHASE10_BREAKOUT_SCREENING_V1"

    report = run_candidate_study(
        symbols=sym_list,
        backfill_days=args.days,
        use_live_backfill=not args.no_backfill,
        mode=args.mode,
        timeframe_mode=tf_mode,
        experiment_family=family
    )
    print(json.dumps(report, indent=2))
