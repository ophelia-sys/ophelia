"""Ophelia Phase 13 Step 1 Diagnostic Replay & Bounded Historical Comparison.

Script: scripts/run_phase13_step1_diagnostic.py
Purpose:
- Deterministic synthetic replay comparing Old (buggy) vs New (corrected first-passage) classification.
- Bounded historical replay on Binance UM dataset comparing classification counts, realized PnL/R, and MAE/MFE.
- Saves results strictly to research/repair_runs/phase13_step1_first_passage/
- DOES NOT overwrite canonical data/phase13_results.json or data/phase13_stop_room.json.
- Disclaims alpha/profitability: diagnostic only.
"""
from __future__ import annotations

import json
import logging
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from control_plane import phase13_discovery_engine as p13

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase13_step1_diagnostic")


def old_buggy_classify_thesis_resumption(
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    future_1m_bars: List[Dict[str, float]]
) -> Tuple[str, bool, bool, Optional[int], Optional[int], float, str, float, float]:
    """Exact reproduction of the pre-repair buggy classification logic."""
    if not future_1m_bars:
        return "CLASS_F", False, False, None, None, entry, "NO_DATA", 0.0, 0.0

    is_long = (direction == "LONG")
    sl_hit = False
    tp1_hit = False
    time_to_sl: Optional[int] = None
    time_to_tp1: Optional[int] = None

    highs = [float(b["high"]) for b in future_1m_bars]
    lows = [float(b["low"]) for b in future_1m_bars]
    closes = [float(b["close"]) for b in future_1m_bars]

    if is_long:
        mfe = (max(highs) - entry) / entry
        mae = (entry - min(lows)) / entry
    else:
        mfe = (entry - min(lows)) / entry
        mae = (max(highs) - entry) / entry

    mae = max(0.0, mae)
    mfe = max(0.0, mfe)

    for minute_idx, b in enumerate(future_1m_bars):
        h, l = float(b["high"]), float(b["low"])
        if is_long:
            if not sl_hit and l <= sl:
                sl_hit = True
                time_to_sl = minute_idx + 1
            if not tp1_hit and h >= tp1:
                tp1_hit = True
                time_to_tp1 = minute_idx + 1
        else:
            if not sl_hit and h >= sl:
                sl_hit = True
                time_to_sl = minute_idx + 1
            if not tp1_hit and l <= tp1:
                tp1_hit = True
                time_to_tp1 = minute_idx + 1

    risk_pct = abs(entry - sl) / entry
    # BUG IDENTIFIED BY GEMINI ARGON:
    # time_to_tp1 <= time_to_sl classified as CLASS_A loss!
    if sl_hit and (not tp1_hit or (time_to_tp1 is not None and time_to_sl is not None and time_to_tp1 <= time_to_sl)):
        resumption_class = "CLASS_A"
        exit_price = sl
        exit_reason = "SL"
    elif sl_hit and tp1_hit and time_to_sl is not None and time_to_tp1 is not None and time_to_tp1 > time_to_sl:
        resumption_class = "CLASS_B"
        exit_price = sl
        exit_reason = "SL_RESUMED"
    elif not sl_hit and tp1_hit:
        resumption_class = "CLASS_C"
        exit_price = tp1
        exit_reason = "TP1"
    elif not sl_hit and not tp1_hit:
        if mae > 0.75 * risk_pct:
            resumption_class = "CLASS_E"
            exit_price = closes[-1]
            exit_reason = "STRUCTURAL_DRIFT"
        else:
            resumption_class = "CLASS_D"
            exit_price = closes[-1]
            exit_reason = "CHOP_FLAT"
    else:
        resumption_class = "CLASS_F"
        exit_price = closes[-1]
        exit_reason = "EXPIRED"

    return resumption_class, sl_hit, tp1_hit, time_to_sl, time_to_tp1, exit_price, exit_reason, mae, mfe


def run_synthetic_benchmark() -> Dict[str, Any]:
    """Runs deterministic synthetic path comparison between old buggy and new corrected logic."""
    logger.info("Running synthetic path benchmark...")
    entry = 100.0
    sl = 99.0
    tp1 = 101.5

    cases = [
        {
            "name": "Target_First_Then_Later_Stop",
            "path": [
                {"high": 100.4, "low": 99.8, "close": 100.2},
                {"high": 101.6, "low": 100.1, "close": 101.5}, # TP1 reached at min 2
                {"high": 100.0, "low": 95.0, "close": 96.0},   # SL touched at min 3 post-exit
            ],
            "expected_repaired": "CLASS_C",
            "expected_buggy": "CLASS_A",
        },
        {
            "name": "Stop_First_Then_Later_Target",
            "path": [
                {"high": 100.2, "low": 99.8, "close": 100.0},
                {"high": 99.4, "low": 98.8, "close": 99.0},   # SL touched at min 2
                {"high": 100.8, "low": 99.1, "close": 100.5},
                {"high": 101.8, "low": 100.2, "close": 101.6}, # TP1 reached at min 4
            ],
            "expected_repaired": "CLASS_B",
            "expected_buggy": "CLASS_B",
        },
        {
            "name": "Stop_Only_No_Target",
            "path": [
                {"high": 100.2, "low": 99.8, "close": 100.0},
                {"high": 99.5, "low": 98.8, "close": 99.0},
                {"high": 99.2, "low": 98.0, "close": 98.5},
            ],
            "expected_repaired": "CLASS_A",
            "expected_buggy": "CLASS_A",
        },
        {
            "name": "Target_Only_No_Stop",
            "path": [
                {"high": 100.4, "low": 99.8, "close": 100.2},
                {"high": 101.6, "low": 100.1, "close": 101.5},
                {"high": 101.4, "low": 100.5, "close": 101.0},
            ],
            "expected_repaired": "CLASS_C",
            "expected_buggy": "CLASS_C",
        },
        {
            "name": "Same_Candle_Ambiguous_Touch",
            "path": [
                {"high": 100.2, "low": 99.8, "close": 100.0},
                {"high": 101.8, "low": 98.5, "close": 100.2}, # Both touched in min 2
                {"high": 100.5, "low": 99.5, "close": 100.0},
            ],
            "expected_repaired": "CLASS_A",
            "expected_buggy": "CLASS_A",
        },
    ]

    results = []
    for c in cases:
        old_res = old_buggy_classify_thesis_resumption("LONG", entry, sl, tp1, c["path"])
        new_res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, c["path"])

        old_gross_r = (old_res[5] - entry) / (entry - sl)
        new_gross_r = (new_res.exit_price - entry) / (entry - sl)

        results.append({
            "case": c["name"],
            "old_class": old_res[0],
            "old_exit_price": old_res[5],
            "old_exit_reason": old_res[6],
            "old_gross_r": old_gross_r,
            "old_mae": old_res[7],
            "old_mfe": old_res[8],
            "new_class": new_res.resumption_class,
            "new_exit_price": new_res.exit_price,
            "new_exit_reason": new_res.exit_reason,
            "new_gross_r": new_gross_r,
            "new_realized_mae": new_res.mae,
            "new_realized_mfe": new_res.mfe,
            "new_full_window_mae": new_res.full_window_mae,
            "new_full_window_mfe": new_res.full_window_mfe,
            "same_candle_ambiguity": new_res.same_candle_ambiguity,
        })
    return {"synthetic_cases": results}


def run_bounded_historical_slice(
    parquet_path: str = "data/processed/binance_um_universe_1m_v2.parquet",
    sample_bars: int = 25000,
) -> Dict[str, Any]:
    """Runs a bounded historical slice on real Binance UM data to quantify the exact impact of the bug."""
    if not os.path.exists(parquet_path):
        logger.warning("Parquet path %s not found. Skipping bounded historical slice.", parquet_path)
        return {"status": "SKIPPED", "reason": "data_file_missing"}

    logger.info("Loading bounded historical slice (%d bars) from %s...", sample_bars, parquet_path)
    import pyarrow.parquet as pq

    # Read slice for BTCUSDT in Jan 2023 (Phase 13 TRAIN partition)
    ts_start = p13.TS_JAN_01_2023
    ts_end = ts_start + (sample_bars * 60 * 1000)  # sample_bars in minutes
    filters = [("symbol", "=", "BTCUSDT"), ("timestamp", ">=", ts_start), ("timestamp", "<=", ts_end)]
    cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume", "delta_v", "aggressive_buy_volume", "aggressive_sell_volume"]
    try:
        table = pq.read_table(parquet_path, columns=cols, filters=filters)
        df = table.to_pandas()
    except Exception as e:
        logger.error("Failed to read parquet: %s", e)
        return {"status": "ERROR", "error": str(e)}

    logger.info("Extracting events from %d historical 1m bars in Jan 2023...", len(df))

    engine = p13.Phase13DiscoveryEngine(data_path=parquet_path)
    events, outcomes, evals = engine.extract_events_for_symbol("BTCUSDT", df)

    logger.info("Extracted %d events. Running side-by-side comparison on stop evaluations...", len(events))

    # Compare old vs new on every forward path in evals
    n_total = 0
    shifted_to_class_c = 0  # Was CLASS_A in old, now CLASS_C (clean winner that hit SL later)
    total_old_classes = {"CLASS_A": 0, "CLASS_B": 0, "CLASS_C": 0, "CLASS_D": 0, "CLASS_E": 0, "CLASS_F": 0}
    total_new_classes = {"CLASS_A": 0, "CLASS_B": 0, "CLASS_C": 0, "CLASS_D": 0, "CLASS_E": 0, "CLASS_F": 0}

    old_gross_r_sum = 0.0
    new_gross_r_sum = 0.0

    # Group df by timestamp for fast forward bar lookup
    bars_records = df[["open", "high", "low", "close"]].to_dict("records")
    ts_to_idx = {int(ts): idx for idx, ts in enumerate(df["timestamp"].values)}

    # Create event lookup for forward bars
    event_dict = {e.event_id: e for e in events}

    for ev_obj in evals[:5000]:  # Evaluate 5000 actual structural stop evaluations
        ev = event_dict.get(ev_obj.event_id)
        if not ev:
            continue
        ev_idx = ts_to_idx.get(ev.timestamp_ms)
        if ev_idx is None or ev_idx + 120 >= len(bars_records):
            continue

        fwd_bars = bars_records[ev_idx + 1 : ev_idx + 121]
        close_p = ev_obj.entry_price
        sl_p = ev_obj.sl_price
        tp_p = ev_obj.tp1_price
        is_long = (ev_obj.direction == "LONG")
        sl_dist = ev_obj.sl_distance_price

        old_res = old_buggy_classify_thesis_resumption(ev_obj.direction, close_p, sl_p, tp_p, fwd_bars)

        n_total += 1
        total_old_classes[old_res[0]] = total_old_classes.get(old_res[0], 0) + 1
        total_new_classes[ev_obj.resumption_class] = total_new_classes.get(ev_obj.resumption_class, 0) + 1

        old_gr = (old_res[5] - close_p) / sl_dist if is_long else (close_p - old_res[5]) / sl_dist
        new_gr = ev_obj.gross_realized_r

        old_gross_r_sum += old_gr
        new_gross_r_sum += new_gr

        if old_res[0] == "CLASS_A" and ev_obj.resumption_class == "CLASS_C":
            shifted_to_class_c += 1

    mean_old_gross_r = old_gross_r_sum / max(1, n_total)
    mean_new_gross_r = new_gross_r_sum / max(1, n_total)

    comparison = {
        "status": "COMPLETED",
        "sample_size": n_total,
        "old_distribution_pct": {k: round(v / max(1, n_total) * 100, 2) for k, v in total_old_classes.items()},
        "new_distribution_pct": {k: round(v / max(1, n_total) * 100, 2) for k, v in total_new_classes.items()},
        "misclassified_winners_restored": shifted_to_class_c,
        "misclassified_winners_restored_pct": round(shifted_to_class_c / max(1, n_total) * 100, 2),
        "mean_gross_r_old_buggy": round(mean_old_gross_r, 4),
        "mean_gross_r_new_corrected": round(mean_new_gross_r, 4),
        "gross_r_shift": round(mean_new_gross_r - mean_old_gross_r, 4),
        "alpha_disclaimer": "DIAGNOSTIC ONLY. Other known Phase 13 defects (F-02, F-03) remain. This does not validate strategy profitability."
    }
    return comparison


def main():
    logger.info("=== STARTING OPHELIA PHASE 13 STEP 1 DIAGNOSTIC RUN ===")
    out_dir = "research/repair_runs/phase13_step1_first_passage"
    os.makedirs(out_dir, exist_ok=True)

    synthetic_results = run_synthetic_benchmark()
    historical_results = run_bounded_historical_slice()

    diagnostic_payload = {
        "timestamp": "2026-10-17T21:10:00Z",
        "step": "STEP_1_FIRST_PASSAGE_REPAIR",
        "branch": "repair/phase13-f01-first-passage",
        "commit_base": "38f3fc96a00cb14ed94108dcdce6aa3be922909d",
        "synthetic_benchmark": synthetic_results,
        "historical_benchmark": historical_results,
        "provenance": {
            "source_parquet": "data/processed/binance_um_universe_1m_v2.parquet",
            "sha256": "pre-existing research dataset",
            "diagnostic_mode": "BOUNDED_READ_ONLY",
            "canonical_data_preserved": True
        }
    }

    out_file = os.path.join(out_dir, "diagnostic_replay_results.json")
    with open(out_file, "w") as f:
        json.dump(diagnostic_payload, f, indent=2)

    logger.info("Diagnostic results successfully written to %s", out_file)
    print(json.dumps(diagnostic_payload, indent=2))


if __name__ == "__main__":
    main()
