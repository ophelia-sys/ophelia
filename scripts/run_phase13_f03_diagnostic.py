"""Ophelia Phase 13 Step 3 (F-03) Diagnostic Replay & Bounded Historical Benchmark.

Script: scripts/run_phase13_f03_diagnostic.py
Purpose:
- Deterministic synthetic hand-check validating volume-weighted session VWAP and variance.
- Adversarial synthetic benchmark proving missing flow, insufficient history, and zero-variance
  are distinguished and never substituted with neutral zero.
- Proves CVD_ACCELERATION and ORDER_FLOW_VWAP_CONFLUENCE are strictly gated on AVAILABLE flow status.
- Bounded historical replay on Binance UM dataset slice (BTCUSDT Jan 1–4, 2023: 1672531200000 to 1672876740000 UTC).
- Quantifies data coverage, missing flow rate, valid flow counts, and CVD status breakdown.
- Saves diagnostic results to research/repair_runs/phase13_f03_orderflow_vwap/diagnostic_orderflow_vwap_results.json
- DOES NOT overwrite canonical data/phase13_results.json or data/phase13_stop_room.json.
- Disclaims alpha/profitability: diagnostic and data-integrity verification only.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from control_plane import phase13_discovery_engine as p13

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase13_f03_diagnostic")

OUTPUT_DIR = os.path.join(REPO_ROOT, "research", "repair_runs", "phase13_f03_orderflow_vwap")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "diagnostic_orderflow_vwap_results.json")


def run_hand_calculated_vwap_benchmark() -> Dict[str, Any]:
    """Validates volume-weighted session VWAP and variance against independent hand calculations."""
    logger.info("Running hand-calculated VWAP benchmark...")
    idx = pd.date_range("2023-01-01 00:00:00", periods=3, freq="5min")
    df = pd.DataFrame({
        "close": [100.0, 110.0, 90.0],
        "volume": [10.0, 10.0, 20.0]
    }, index=idx)

    vwap, std = p13.compute_vwap(df)

    # Independent hand-calculated references:
    # Bar 1: P=100, V=10 -> cum_pv=1000, cum_v=10 -> VWAP=100.0, var=0.0 -> std=NaN (undefined dispersion)
    # Bar 2: P=110, V=10 -> cum_pv=2100, cum_v=20 -> VWAP=105.0, cum_p2v=221000 -> var=25.0 -> std=5.0
    # Bar 3: P=90, V=20  -> cum_pv=3900, cum_v=40 -> VWAP=97.5, cum_p2v=383000 -> var=68.75 -> std=sqrt(68.75)
    expected_vwap = [100.0, 105.0, 97.5]
    expected_std = [float("nan"), 5.0, float(np.sqrt(68.75))]

    passed_vwap = np.allclose(vwap.values, expected_vwap, equal_nan=True)
    passed_std = np.allclose(std.values, expected_std, equal_nan=True)

    # Compare with old buggy unweighted dispersion:
    # In old engine: cum_dev = cumsum((close - vwap)^2) / cum_v
    # For Bar 2: ((100 - 105)^2 + (110 - 105)^2) / 20 = (25 + 25) / 20 = 2.5 -> sqrt(2.5) ~ 1.5811 (incorrect!)
    old_unweighted_var_bar2 = ((100.0 - 105.0)**2 + (110.0 - 105.0)**2) / 20.0
    correct_volume_weighted_var_bar2 = (10.0 * (100.0 - 105.0)**2 + 10.0 * (110.0 - 105.0)**2) / 20.0

    return {
        "status": "PASS" if (passed_vwap and passed_std) else "FAIL",
        "sample_points": 3,
        "calculated_vwap": [round(float(v), 4) for v in vwap.values],
        "expected_vwap": expected_vwap,
        "calculated_std": [round(float(s), 4) if np.isfinite(s) else "NaN" for s in std.values],
        "expected_std": [round(float(s), 4) if np.isfinite(s) else "NaN" for s in expected_std],
        "single_bar_dispersion_undefined_as_nan": bool(np.isnan(std.iloc[0])),
        "old_unweighted_variance_bar2": round(float(old_unweighted_var_bar2), 4),
        "correct_volume_weighted_variance_bar2": round(float(correct_volume_weighted_var_bar2), 4),
        "formula": "Weighted Welford incremental between-bar dispersion on representative transaction price (turnover / volume)",
    }


def run_synthetic_flow_adversarial_benchmark() -> Dict[str, Any]:
    """Validates CVD statuses, missing-data handling, and signal gating under adversarial conditions."""
    logger.info("Running synthetic flow adversarial benchmark...")
    idx = pd.date_range("2023-01-01 00:00:00", periods=60, freq="5min")

    # 1. Genuine constant zero delta (10 buy - 10 sell = 0.0)
    df_zero = pd.DataFrame({"delta_v": [0.0] * 60}, index=idx)
    z_zero, st_zero = p13.compute_cvd(df_zero)

    # 2. All missing delta
    df_nan = pd.DataFrame({"delta_v": [np.nan] * 60}, index=idx)
    z_nan, st_nan = p13.compute_cvd(df_nan)

    # 3. Valid fluctuating delta with 1 missing bar at index 35
    np.random.seed(42)
    deltas = np.random.randn(60) * 10.0
    deltas[35] = np.nan
    df_gap = pd.DataFrame({"delta_v": deltas}, index=idx)
    z_gap, st_gap = p13.compute_cvd(df_gap)

    # Check status transitions
    # In df_zero: bars 0..33 are INSUFFICIENT_HISTORY (34 bars), bars 34..59 are ZERO_VARIANCE (26 bars)
    zero_var_count = int((st_zero == "ZERO_VARIANCE").sum())
    zero_insufficient_count = int((st_zero == "INSUFFICIENT_HISTORY").sum())
    zero_nan_zscore = bool(z_zero.loc[st_zero == "ZERO_VARIANCE"].isna().all())

    # In df_nan: ALL 60 bars must be MISSING_FLOW; 0 bars may report INSUFFICIENT_HISTORY
    nan_missing_count = int((st_nan == "MISSING_FLOW").sum())
    nan_insufficient_count = int((st_nan == "INSUFFICIENT_HISTORY").sum())
    nan_nan_zscore = bool(z_nan.isna().all())

    # In df_gap: bar 35 and bars 35..46 (within 1h window of bar 35) must be MISSING_FLOW
    gap_impacted_bars = [i for i in range(35, 47) if st_gap.iloc[i] == "MISSING_FLOW"]
    gap_properly_propagated = (len(gap_impacted_bars) == 12)

    passed = (
        zero_var_count == 26
        and zero_insufficient_count == 34
        and zero_nan_zscore
        and nan_missing_count == 60
        and nan_insufficient_count == 0
        and nan_nan_zscore
        and gap_properly_propagated
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "genuine_zero_delta": {
            "status_at_bar_10": str(st_zero.iloc[10]),
            "status_at_bar_40": str(st_zero.iloc[40]),
            "zero_variance_bars_count": zero_var_count,
            "insufficient_history_bars_count": zero_insufficient_count,
            "zero_variance_zscore_is_nan": zero_nan_zscore,
            "never_substituted_neutral_zero": zero_nan_zscore,
        },
        "all_missing_flow": {
            "missing_flow_bars_count": nan_missing_count,
            "insufficient_history_bars_count": nan_insufficient_count,
            "all_zscores_are_nan": nan_nan_zscore,
            "never_substituted_neutral_zero": nan_nan_zscore,
            "all_60_bars_missing_flow": bool(nan_missing_count == 60 and nan_insufficient_count == 0),
        },
        "single_missing_bar_gap": {
            "gap_index": 35,
            "affected_rolling_1h_bars": len(gap_impacted_bars),
            "expected_affected_bars": 12,
            "properly_marked_missing_flow": gap_properly_propagated,
        },
    }


def run_historical_slice_benchmark(
    parquet_path: str = "data/processed/binance_um_universe_1m_v2.parquet",
    start_utc: str = "2023-01-01 00:00:00",
    end_utc: str = "2023-01-04 23:59:00",
    symbol: str = "BTCUSDT",
) -> Dict[str, Any]:
    """Runs bounded historical order-flow and VWAP audit on explicit UTC dataset slice."""
    logger.info("Loading bounded historical slice for %s (%s to %s UTC)...", symbol, start_utc, end_utc)
    full_path = os.path.join(REPO_ROOT, parquet_path)
    if not os.path.exists(full_path):
        return {
            "status": "SKIPPED",
            "reason": f"Parquet dataset not found at {parquet_path}",
        }

    dt_start = pd.Timestamp(start_utc, tz="UTC")
    dt_end = pd.Timestamp(end_utc, tz="UTC")
    ts_start = int(dt_start.timestamp() * 1000)
    ts_end = int(dt_end.timestamp() * 1000)

    try:
        import pyarrow.parquet as pq
        filters = [
            ("symbol", "=", symbol),
            ("timestamp", ">=", ts_start),
            ("timestamp", "<=", ts_end),
        ]
        table = pq.read_table(full_path, filters=filters)
        df_1m = table.to_pandas()
    except Exception as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": f"Failed to load dataset: {exc}",
        }

    if len(df_1m) == 0:
        return {
            "status": "INCONCLUSIVE",
            "reason": f"Zero rows found for {symbol} between {start_utc} and {end_utc}",
        }

    # 1. Source-grid validation
    df_1m = df_1m.sort_values("timestamp").reset_index(drop=True)
    df_1m["dt"] = pd.to_datetime(df_1m["timestamp"], unit="ms", utc=True)
    df_1m = df_1m.set_index("dt")

    total_1m_rows = len(df_1m)
    expected_1m_rows = 5760  # 4 days * 24 * 60
    expected_grid = pd.date_range(start=dt_start, end=dt_end, freq="1min")
    expected_first_ts = int(dt_start.timestamp() * 1000)
    expected_last_ts = int(dt_end.timestamp() * 1000)
    actual_first_ts = int(df_1m["timestamp"].min()) if len(df_1m) > 0 else None
    actual_last_ts = int(df_1m["timestamp"].max()) if len(df_1m) > 0 else None

    duplicate_ts_count = int(df_1m["timestamp"].duplicated().sum())
    is_monotonic = bool(df_1m["timestamp"].is_monotonic_increasing)
    off_grid_count = int((df_1m["timestamp"] % 60_000 != 0).sum())
    missing_timestamps = [ts.isoformat() for ts in expected_grid.difference(df_1m.index)]
    extra_timestamps = [ts.isoformat() for ts in df_1m.index.difference(expected_grid)]

    exact_grid_match = bool(
        total_1m_rows == expected_1m_rows
        and duplicate_ts_count == 0
        and off_grid_count == 0
        and is_monotonic
        and len(missing_timestamps) == 0
        and len(extra_timestamps) == 0
        and actual_first_ts == expected_first_ts
        and actual_last_ts == expected_last_ts
    )
    grid_validation_status = "PASS" if exact_grid_match else "FAIL"

    # 2. Order flow columns & identity validation
    flow_cols = ["delta_v", "aggressive_buy_volume", "aggressive_sell_volume", "taker_buy_volume", "volume", "quote_volume"]
    flow_presence = {col: bool(col in df_1m.columns) for col in flow_cols}

    # 1m Identities
    # Identity 1: delta_v = aggressive_buy_volume - aggressive_sell_volume
    # Identity 2: delta_v = 2 * taker_buy_volume - volume
    id1_valid_1m = df_1m["delta_v"].notna() & df_1m["aggressive_buy_volume"].notna() & df_1m["aggressive_sell_volume"].notna() if ("aggressive_buy_volume" in df_1m and "aggressive_sell_volume" in df_1m and "delta_v" in df_1m) else pd.Series(False, index=df_1m.index)
    diff1_1m = np.abs(df_1m.loc[id1_valid_1m, "delta_v"] - (df_1m.loc[id1_valid_1m, "aggressive_buy_volume"] - df_1m.loc[id1_valid_1m, "aggressive_sell_volume"]))
    max_err_id1_1m = float(diff1_1m.max()) if len(diff1_1m) > 0 else None
    id1_pass_1m = (max_err_id1_1m is not None and max_err_id1_1m < 1e-4)

    id2_valid_1m = df_1m["delta_v"].notna() & df_1m["taker_buy_volume"].notna() & df_1m["volume"].notna() if ("taker_buy_volume" in df_1m and "volume" in df_1m and "delta_v" in df_1m) else pd.Series(False, index=df_1m.index)
    diff2_1m = np.abs(df_1m.loc[id2_valid_1m, "delta_v"] - (2.0 * df_1m.loc[id2_valid_1m, "taker_buy_volume"] - df_1m.loc[id2_valid_1m, "volume"]))
    max_err_id2_1m = float(diff2_1m.max()) if len(diff2_1m) > 0 else None
    id2_pass_1m = (max_err_id2_1m is not None and max_err_id2_1m < 1e-4)

    tbv_range_violations_1m = int(((df_1m["taker_buy_volume"] < -1e-5) | (df_1m["taker_buy_volume"] > df_1m["volume"] + 1e-5)).sum()) if ("taker_buy_volume" in df_1m and "volume" in df_1m) else 0

    delta_v_1m_valid = int(df_1m["delta_v"].notna().sum()) if "delta_v" in df_1m.columns else 0
    delta_v_1m_missing_rate = round(float(1.0 - (delta_v_1m_valid / total_1m_rows)), 4) if total_1m_rows > 0 else 1.0
    delta_v_1m_zeros = int((df_1m["delta_v"] == 0.0).sum()) if "delta_v" in df_1m.columns else 0

    # 3. Strict Resampling
    df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m)
    total_5m_bars = len(df_5m)

    # 5m Identities
    id1_valid_5m = df_5m["delta_v"].notna() & df_5m["aggressive_buy_volume"].notna() & df_5m["aggressive_sell_volume"].notna() if ("aggressive_buy_volume" in df_5m and "aggressive_sell_volume" in df_5m and "delta_v" in df_5m) else pd.Series(False, index=df_5m.index)
    diff1_5m = np.abs(df_5m.loc[id1_valid_5m, "delta_v"] - (df_5m.loc[id1_valid_5m, "aggressive_buy_volume"] - df_5m.loc[id1_valid_5m, "aggressive_sell_volume"]))
    max_err_id1_5m = float(diff1_5m.max()) if len(diff1_5m) > 0 else None
    id1_pass_5m = (max_err_id1_5m is not None and max_err_id1_5m < 1e-4)

    id2_valid_5m = df_5m["delta_v"].notna() & df_5m["taker_buy_volume"].notna() & df_5m["volume"].notna() if ("taker_buy_volume" in df_5m and "volume" in df_5m and "delta_v" in df_5m) else pd.Series(False, index=df_5m.index)
    diff2_5m = np.abs(df_5m.loc[id2_valid_5m, "delta_v"] - (2.0 * df_5m.loc[id2_valid_5m, "taker_buy_volume"] - df_5m.loc[id2_valid_5m, "volume"]))
    max_err_id2_5m = float(diff2_5m.max()) if len(diff2_5m) > 0 else None
    id2_pass_5m = (max_err_id2_5m is not None and max_err_id2_5m < 1e-4)

    delta_v_5m_valid = int(df_5m["delta_v"].notna().sum()) if "delta_v" in df_5m.columns else 0
    delta_v_5m_missing_rate = round(float(1.0 - (delta_v_5m_valid / total_5m_bars)), 4) if total_5m_bars > 0 else 1.0

    # 4. Compute VWAP and CVD
    df_5m["vwap"], df_5m["std_vwap"] = p13.compute_vwap(df_5m)
    df_5m["vwap_zscore"] = (df_5m["close"] - df_5m["vwap"]) / df_5m["std_vwap"]
    df_5m["cvd_zscore"], df_5m["cvd_status"] = p13.compute_cvd(df_5m)

    status_counts = df_5m["cvd_status"].value_counts().to_dict()
    cnt_available = int(status_counts.get("AVAILABLE", 0))
    cnt_missing_flow = int(status_counts.get("MISSING_FLOW", 0))
    cnt_insufficient_history = int(status_counts.get("INSUFFICIENT_HISTORY", 0))
    cnt_zero_variance = int(status_counts.get("ZERO_VARIANCE", 0))

    non_avail_mask = df_5m["cvd_status"] != "AVAILABLE"
    neutral_zero_violations = int((df_5m.loc[non_avail_mask, "cvd_zscore"] == 0.0).sum())
    vwap_undefined_count = int(df_5m["std_vwap"].isna().sum())

    # 5. Event extraction audit & Dynamic Event Gating
    engine = p13.Phase13DiscoveryEngine()
    events, outcomes, evals = engine.extract_events_for_symbol(symbol, df_1m)

    events_by_class: Dict[str, int] = {}
    for ev in events:
        events_by_class[ev.event_class] = events_by_class.get(ev.event_class, 0) + 1

    cvd_events_count = events_by_class.get("CVD_ACCELERATION", 0)
    orderflow_vwap_confluence_count = events_by_class.get("ORDER_FLOW_VWAP_CONFLUENCE", 0)
    vwap_deviation_count = events_by_class.get("VWAP_DEVIATION", 0)
    vwap_reclaim_count = events_by_class.get("VWAP_RECLAIM", 0)

    event_status_counts: Dict[str, int] = {}
    event_zero_sub_violations = 0
    gating_violations: List[Dict[str, Any]] = []

    for ev in events:
        event_status_counts[ev.cvd_data_status] = event_status_counts.get(ev.cvd_data_status, 0) + 1
        if ev.cvd_data_status != "AVAILABLE" and not np.isnan(ev.cvd_zscore) and ev.cvd_zscore == 0.0:
            event_zero_sub_violations += 1

        if ev.event_class == "CVD_ACCELERATION":
            if ev.cvd_data_status != "AVAILABLE" or not np.isfinite(ev.cvd_zscore):
                gating_violations.append({
                    "event_id": ev.event_id,
                    "event_class": ev.event_class,
                    "reason": "CVD_ACCELERATION emitted with non-AVAILABLE status or non-finite zscore",
                    "status": ev.cvd_data_status,
                    "cvd_zscore": ev.cvd_zscore,
                })
        elif ev.event_class == "ORDER_FLOW_VWAP_CONFLUENCE":
            if ev.cvd_data_status != "AVAILABLE" or not np.isfinite(ev.cvd_zscore) or not np.isfinite(ev.entry_price):
                gating_violations.append({
                    "event_id": ev.event_id,
                    "event_class": ev.event_class,
                    "reason": "ORDER_FLOW_VWAP_CONFLUENCE emitted with invalid CVD or entry price",
                    "status": ev.cvd_data_status,
                    "cvd_zscore": ev.cvd_zscore,
                })
        elif ev.event_class == "VWAP_DEVIATION":
            if not np.isfinite(ev.vwap_deviation_sigma) or abs(ev.vwap_deviation_sigma) < 1.5:
                gating_violations.append({
                    "event_id": ev.event_id,
                    "event_class": ev.event_class,
                    "reason": "VWAP_DEVIATION emitted with invalid deviation sigma",
                    "vwap_deviation_sigma": ev.vwap_deviation_sigma,
                })
        elif ev.event_class == "VWAP_RECLAIM":
            if not np.isfinite(ev.entry_price):
                gating_violations.append({
                    "event_id": ev.event_id,
                    "event_class": ev.event_class,
                    "reason": "VWAP_RECLAIM emitted with invalid entry price",
                    "entry_price": ev.entry_price,
                })

    computed_gating_status = "PASS" if len(gating_violations) == 0 and len(events) > 0 else ("INCONCLUSIVE" if len(events) == 0 else "FAIL")

    overall_benchmark_status = "COMPLETED" if (
        grid_validation_status == "PASS"
        and id1_pass_1m
        and id2_pass_1m
        and id1_pass_5m
        and id2_pass_5m
        and tbv_range_violations_1m == 0
        and neutral_zero_violations == 0
        and event_zero_sub_violations == 0
        and len(gating_violations) == 0
    ) else "FAIL"

    return {
        "status": overall_benchmark_status,
        "source_grid_validation": {
            "status": grid_validation_status,
            "expected_first_ts": expected_first_ts,
            "actual_first_ts": actual_first_ts,
            "expected_last_ts": expected_last_ts,
            "actual_last_ts": actual_last_ts,
            "expected_rows": expected_1m_rows,
            "actual_rows": total_1m_rows,
            "duplicate_timestamps": duplicate_ts_count,
            "is_strictly_monotonic": is_monotonic,
            "off_grid_timestamps": off_grid_count,
            "missing_timestamps_count": len(missing_timestamps),
            "extra_timestamps_count": len(extra_timestamps),
            "exact_grid_match": exact_grid_match,
        },
        "sample_scope": {
            "symbol": symbol,
            "period_utc": f"{start_utc} to {end_utc}",
            "start_timestamp_ms": ts_start,
            "end_timestamp_ms": ts_end,
            "total_1m_bars": total_1m_rows,
            "expected_1m_bars": expected_1m_rows,
            "has_exact_expected_minutes": exact_grid_match,
            "total_5m_bars": total_5m_bars,
        },
        "order_flow_audit": {
            "flow_columns_present": flow_presence,
            "identities": {
                "identity_1_aggressive_delta_max_abs_err_1m": max_err_id1_1m,
                "identity_1_pass_1m": id1_pass_1m,
                "identity_1_aggressive_delta_max_abs_err_5m": max_err_id1_5m,
                "identity_1_pass_5m": id1_pass_5m,
                "identity_2_taker_delta_max_abs_err_1m": max_err_id2_1m,
                "identity_2_pass_1m": id2_pass_1m,
                "identity_2_taker_delta_max_abs_err_5m": max_err_id2_5m,
                "identity_2_pass_5m": id2_pass_5m,
                "taker_buy_volume_range_violations_1m": tbv_range_violations_1m,
            },
            "delta_v_1m_valid_count": delta_v_1m_valid,
            "delta_v_1m_missing_rate": delta_v_1m_missing_rate,
            "delta_v_1m_genuine_zeros": delta_v_1m_zeros,
            "delta_v_5m_valid_count": delta_v_5m_valid,
            "delta_v_5m_missing_rate": delta_v_5m_missing_rate,
            "cvd_5m_status_breakdown": {
                "AVAILABLE": cnt_available,
                "MISSING_FLOW": cnt_missing_flow,
                "INSUFFICIENT_HISTORY": cnt_insufficient_history,
                "ZERO_VARIANCE": cnt_zero_variance,
            },
            "neutral_zero_substitutions_on_5m_bars": neutral_zero_violations,
        },
        "vwap_audit": {
            "total_5m_vwap_calculated": int(df_5m["vwap"].notna().sum()),
            "vwap_undefined_dispersion_count": vwap_undefined_count,
            "vwap_min": round(float(df_5m["vwap"].min()), 2),
            "vwap_max": round(float(df_5m["vwap"].max()), 2),
        },
        "event_gating_audit": {
            "total_events_extracted": len(events),
            "events_by_class": events_by_class,
            "cvd_acceleration_events": cvd_events_count,
            "orderflow_vwap_confluence_events": orderflow_vwap_confluence_count,
            "vwap_deviation_events": vwap_deviation_count,
            "vwap_reclaim_events": vwap_reclaim_count,
            "event_cvd_status_breakdown": event_status_counts,
            "event_neutral_zero_substitutions": event_zero_sub_violations,
            "gating_rule_verification": computed_gating_status,
            "gating_violations_count": len(gating_violations),
            "gating_violations": gating_violations[:10],
        },
        "stop_model_audit": {
            "stop_evaluations_total": len(evals),
            "stop_diagnostics": engine.stop_diagnostics,
        },
    }


def main() -> None:
    """Executes the complete F-03 Order Flow & VWAP diagnostic suite and writes artifact."""
    logger.info("Starting Phase 13 Step 3 (F-03) Diagnostic Run...")
    hand_check_res = run_hand_calculated_vwap_benchmark()
    synthetic_flow_res = run_synthetic_flow_adversarial_benchmark()
    historical_res = run_historical_slice_benchmark(
        parquet_path="data/processed/binance_um_universe_1m_v2.parquet",
        start_utc="2023-01-01 00:00:00",
        end_utc="2023-01-04 23:59:00",
        symbol="BTCUSDT",
    )

    combined_artifact = {
        "diagnostic_run_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_step": "F-03-F-06: Forensic Audit Remediation (Order Flow, Invariants, Stop Eligibility, Split-Isolated Inference)",
        "branch": "repair/phase13-audit-remediation",
        "safety_invariants": {
            "TRADING_AUTHORITY": False,
            "EXECUTION_MODE": "SHADOW",
            "LIVE_ORDERS_FORBIDDEN": True,
            "ALPHA_CLAIM": "NONE (Data integrity & causal market structure repair only)",
        },
        "benchmarks": {
            "hand_calculated_vwap_benchmark": hand_check_res,
            "synthetic_flow_adversarial_benchmark": synthetic_flow_res,
            "historical_slice_benchmark": historical_res,
        },
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(combined_artifact, f, indent=2)

    logger.info("Saved F-03 diagnostic artifact to %s", OUTPUT_PATH)
    print("\n" + "="*80)
    print("PHASE 13 STEP 3 (F-03-F-06) DIAGNOSTIC SUMMARY")
    print("="*80)
    print(f"Hand-Calculated VWAP Benchmark: {hand_check_res['status']}")
    print(f"Synthetic Flow Adversarial Benchmark: {synthetic_flow_res['status']}")
    print(f"Historical Slice Benchmark: {historical_res['status']}")
    if historical_res["status"] == "COMPLETED":
        grid = historical_res["source_grid_validation"]
        of = historical_res["order_flow_audit"]
        eg = historical_res["event_gating_audit"]
        sm = historical_res.get("stop_model_audit", {})
        print(f"Source Grid Validation: {grid['status']} (Exact Grid Match: {grid['exact_grid_match']})")
        print(f"Identity 1 (Aggressive Delta) 1m/5m Pass: {of['identities']['identity_1_pass_1m']} / {of['identities']['identity_1_pass_5m']}")
        print(f"Identity 2 (Taker Delta) 1m/5m Pass: {of['identities']['identity_2_pass_1m']} / {of['identities']['identity_2_pass_5m']}")
        print(f"BTCUSDT 1m Bars: {historical_res['sample_scope']['total_1m_bars']}")
        print(f"5m CVD Status Breakdown: {of['cvd_5m_status_breakdown']}")
        print(f"Neutral Zero Substitutions: {of['neutral_zero_substitutions_on_5m_bars']}")
        print(f"Events Extracted: {eg['total_events_extracted']}")
        print(f"Event Gating Status: {eg['gating_rule_verification']} (Violations: {eg['gating_violations_count']})")
        print(f"Stop Model Evaluations: {sm.get('stop_evaluations_total', 0)}")
        print(f"Stop Diagnostics: {sm.get('stop_diagnostics', {})}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
