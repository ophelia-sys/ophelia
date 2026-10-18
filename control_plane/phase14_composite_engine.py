"""Ophelia Phase 14: Controlled Multi-Factor Alpha Discovery Engine.

Conditioning candidate microstructure signals (HTF Aligned Displacement & Liquidity Sweep SFP)
on contextual market regime filters (4H trend, RVOL, Volatility Regime, CVD absorption,
mutual confluence, and 1H HTF levels) across the 2023 universe and the Q1 2024 out-of-time universe.

Enforces:
1. Zero lookahead causal event generation and forward trajectories.
2. Synchronized cross-symbol time-block bootstrap (2h, 6h primary, 24h).
3. Pre-registered hypothesis family (m = 10) with Benjamini-Hochberg FDR control.
4. Complete friction accounting at 5.0 bps, 9.1 bps (baseline), and 15.0 bps.
5. Strict split isolation: TRAIN, VALIDATION, TEST, and OUT_OF_TIME_Q1_2024.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

from control_plane.phase13_discovery_engine import (
    FORWARD_HORIZONS,
    STOP_REGIMES,
    ForwardOutcome,
    Phase13DiscoveryEngine,
    Phase13Event,
    StopRoomEvaluation,
    assign_phase13_split,
    bootstrap_mean_ci,
    classify_stop_regime,
    synchronized_time_block_bootstrap,
)

STOP_MODELS = ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]

logger = logging.getLogger("phase14_engine")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Q1 2024 Timestamp Bounds (UTC ms)
TS_JAN_01_2024 = 1704067200000  # 2024-01-01 00:00:00 UTC
TS_MAR_31_2024 = 1711929540000  # 2024-03-31 23:59:00 UTC

# Friction tiers (round-trip decimal)
FRICTION_FEE_ONLY = 0.0005       # 5.0 bps
FRICTION_BASELINE = 0.00091      # 9.1 bps (Ophelia baseline)
FRICTION_CONSERVATIVE = 0.0015   # 15.0 bps

# 10 Pre-Registered Phase 14 Hypotheses
PHASE14_HYPOTHESES = [
    "BENCH_HTF_ALIGNED_DISPLACEMENT",
    "BENCH_LIQUIDITY_SWEEP_SFP",
    "COMP_SFP_HTF_TREND",
    "COMP_SFP_RVOL_CONFIRM",
    "COMP_SFP_VOL_EXPANSION",
    "COMP_DISPLACEMENT_RVOL",
    "COMP_DISPLACEMENT_VOL_EXPANSION",
    "COMP_SFP_CVD_ABSORPTION",
    "COMP_DUAL_CONFLUENCE",
    "COMP_HTF_1H_SWING_SFP",
]


def assign_phase14_split(ts_ms: int) -> str:
    """Assigns timestamp to chronological split including Q1 2024 out-of-time."""
    if ts_ms >= TS_JAN_01_2024 and ts_ms <= TS_MAR_31_2024:
        return "OUT_OF_TIME_Q1_2024"
    return assign_phase13_split(ts_ms)


class Phase14CompositeEngine:
    """Execution engine for Phase 14 composite alpha discovery."""

    def __init__(self, data_path: str = "data/processed/binance_um_universe_1m_v2.parquet"):
        self.data_path = data_path
        self._engine = Phase13DiscoveryEngine(data_path=data_path, event_family_mode="phase14_composite")

    @property
    def stop_diagnostics(self) -> Dict[str, Any]:
        return self._engine.stop_diagnostics

    @property
    def per_symbol_stop_diagnostics(self) -> Dict[str, Any]:
        return self._engine.per_symbol_stop_diagnostics

    def extract_composite_events_for_symbol(
        self,
        symbol: str,
        df_1m: pd.DataFrame,
        is_oot_2024: bool = False,
    ) -> Tuple[List[Phase13Event], List[ForwardOutcome], List[StopRoomEvaluation]]:
        """Extracts candidate events across all 10 pre-registered hypotheses for a single symbol."""
        return self._engine.extract_events_for_symbol(symbol, df_1m)


def run_phase14_experiment(
    universe_2023_path: str = "data/processed/binance_um_universe_1m_v2.parquet",
    universe_2024_path: str = "data/processed/phase12_fresh_universe_1m.parquet",
    symbols: Optional[List[str]] = None,
    output_dir: str = "data",
) -> Dict[str, Any]:
    """Runs the complete Phase 14 Controlled Multi-Factor Alpha Discovery experiment."""
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    if pq is None:
        raise ImportError("pyarrow is required to read parquet datasets for run_phase14_experiment")

    engine = Phase14CompositeEngine()
    all_events: List[Phase13Event] = []
    all_outcomes: List[ForwardOutcome] = []
    all_evals: List[StopRoomEvaluation] = []

    # 1. Process 2023 Universe (TRAIN, VALIDATION, TEST)
    ts_start_2023 = 1672531200000  # 2023-01-01
    ts_end_2023 = 1704067199000    # 2023-12-31
    cols_2023 = [
        "timestamp", "symbol", "open", "high", "low", "close", "volume",
        "quote_volume", "delta_v", "aggressive_buy_volume", "aggressive_sell_volume", "taker_buy_volume"
    ]

    for sym in symbols:
        logger.info("Loading 2023 1m data for %s from %s...", sym, universe_2023_path)
        filters = [("symbol", "=", sym), ("timestamp", ">=", ts_start_2023), ("timestamp", "<=", ts_end_2023)]
        try:
            table = pq.read_table(universe_2023_path, columns=cols_2023, filters=filters)
            df_sym_2023 = table.to_pandas()
            evs, outs, evals = engine.extract_composite_events_for_symbol(sym, df_sym_2023, is_oot_2024=False)
            all_events.extend(evs)
            all_outcomes.extend(outs)
            all_evals.extend(evals)
        except Exception as e:
            logger.error("Error processing 2023 data for %s: %s", sym, e)

    # 2. Process Q1 2024 Universe (OUT_OF_TIME_Q1_2024)
    # Warm up from Dec 01 2023 (1701388800000) so that 4H EMA, 1H ATR, and rolling features are fully initialized by Jan 01 2024.
    cols_2024 = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    for sym in symbols:
        logger.info("Loading Q1 2024 1m data (with Dec 2023 warm-up) for %s from %s...", sym, universe_2024_path)
        filters = [("symbol", "=", sym), ("timestamp", ">=", 1701388800000), ("timestamp", "<=", TS_MAR_31_2024)]
        try:
            table = pq.read_table(universe_2024_path, columns=cols_2024, filters=filters)
            df_sym_2024 = table.to_pandas()
            evs, outs, evals = engine.extract_composite_events_for_symbol(sym, df_sym_2024, is_oot_2024=True)
            # Retain strictly OUT_OF_TIME_Q1_2024 records
            evs_oot = [e for e in evs if e.split == "OUT_OF_TIME_Q1_2024"]
            oot_event_ids = {e.event_id for e in evs_oot}
            outs_oot = [o for o in outs if o.event_id in oot_event_ids]
            evals_oot = [ev for ev in evals if ev.split == "OUT_OF_TIME_Q1_2024"]
            all_events.extend(evs_oot)
            all_outcomes.extend(outs_oot)
            all_evals.extend(evals_oot)
        except Exception as e:
            logger.error("Error processing Q1 2024 data for %s: %s", sym, e)

    logger.info("Total Phase 14 extraction: %d events, %d outcomes, %d stop evaluations.",
                len(all_events), len(all_outcomes), len(all_evals))

    # Convert to DataFrames for analysis
    df_evs = pd.DataFrame([e.to_dict() for e in all_events])
    df_outs = pd.DataFrame([o.to_dict() for o in all_outcomes])
    df_evals = pd.DataFrame([ev.to_dict() for ev in all_evals])

    # Save parquets
    os.makedirs(output_dir, exist_ok=True)
    df_evs.to_parquet(os.path.join(output_dir, "phase14_events.parquet"), index=False)
    df_outs.to_parquet(os.path.join(output_dir, "phase14_forward_outcomes.parquet"), index=False)
    df_evals.to_parquet(os.path.join(output_dir, "phase14_stop_room.parquet"), index=False)

    # Primary analysis: 60m horizon
    df_60m = df_outs[df_outs["horizon_min"] == 60].merge(df_evs, on="event_id")

    candidate_results: List[Dict[str, Any]] = []

    for hyp_name in PHASE14_HYPOTHESES:
        sub = df_60m[df_60m["event_class"] == hyp_name]
        n_total = len(sub)

        sub_train = sub[sub["split"] == "TRAIN"]
        sub_val = sub[sub["split"] == "VALIDATION"]
        sub_test = sub[sub["split"] == "TEST"]
        sub_oot = sub[sub["split"] == "OUT_OF_TIME_Q1_2024"]

        def _eval_split(df_sub: pd.DataFrame, split_label: str) -> Dict[str, Any]:
            n = len(df_sub)
            if n == 0:
                return {"sample_size": 0, "status": "NO_EVENTS"}
            rets = df_sub["directional_return_pct"].dropna().values
            n_pos = int(np.sum(rets > 0))
            wr = (n_pos / len(rets) * 100) if len(rets) > 0 else 0.0
            mean_ret = float(np.mean(rets)) * 100 if len(rets) > 0 else 0.0

            # Profit factor on 60m return: sum(gains) / abs(sum(losses))
            gains = rets[rets > 0]
            losses = rets[rets < 0]
            sum_gains = float(np.sum(gains)) if len(gains) > 0 else 0.0
            sum_losses = float(np.abs(np.sum(losses))) if len(losses) > 0 else 1e-6
            pf = round(sum_gains / sum_losses, 3)

            # Net expectancies
            net_5bps = mean_ret - (FRICTION_FEE_ONLY * 100)
            net_9bps = mean_ret - (FRICTION_BASELINE * 100)
            net_15bps = mean_ret - (FRICTION_CONSERVATIVE * 100)

            # Loss tail
            worst_loss = float(np.min(rets)) * 100 if len(rets) > 0 else 0.0
            p90_loss = float(np.percentile(rets, 10)) * 100 if len(rets) > 0 else 0.0

            # Symbol breakdown
            sym_counts = df_sub["symbol"].value_counts().to_dict()

            # Bootstrap if sample size >= 30
            boot_6h = synchronized_time_block_bootstrap(
                df_sub, value_col="directional_return_pct", timestamp_col="timestamp_ms", block_duration_hours=6.0
            ) if n >= 30 else {"ci_low": 0.0, "ci_high": 0.0, "p_value": 1.0, "se": 0.0, "n_active_blocks": 0}

            boot_2h = synchronized_time_block_bootstrap(
                df_sub, value_col="directional_return_pct", timestamp_col="timestamp_ms", block_duration_hours=2.0
            ) if n >= 30 else {"ci_low": 0.0, "ci_high": 0.0, "p_value": 1.0, "se": 0.0, "n_active_blocks": 0}

            boot_24h = synchronized_time_block_bootstrap(
                df_sub, value_col="directional_return_pct", timestamp_col="timestamp_ms", block_duration_hours=24.0
            ) if n >= 30 else {"ci_low": 0.0, "ci_high": 0.0, "p_value": 1.0, "se": 0.0, "n_active_blocks": 0}

            return {
                "split": split_label,
                "sample_size": n,
                "win_count": n_pos,
                "win_rate_pct": round(wr, 2),
                "gross_mean_return_pct": round(mean_ret, 4),
                "gross_mean_return_bps": round(mean_ret * 100, 2),
                "net_mean_return_5bps": round(net_5bps * 100, 2),
                "net_mean_return_9_1bps": round(net_9bps * 100, 2),
                "net_mean_return_15bps": round(net_15bps * 100, 2),
                "profit_factor": pf,
                "worst_loss_pct": round(worst_loss, 3),
                "p90_loss_pct": round(p90_loss, 3),
                "symbol_breakdown": sym_counts,
                "bootstrap_6h": {
                    "ci_95_low_bps": round(boot_6h["ci_low"] * 10000, 2),
                    "ci_95_high_bps": round(boot_6h["ci_high"] * 10000, 2),
                    "cluster_se_bps": round(boot_6h["se"] * 10000, 2),
                    "raw_p": round(boot_6h["p_value"], 5),
                    "active_clusters": boot_6h["n_active_blocks"],
                },
                "sensitivity_durations": {
                    "block_2h": {"p_val": round(boot_2h["p_value"], 5), "clusters": boot_2h["n_active_blocks"]},
                    "block_6h": {"p_val": round(boot_6h["p_value"], 5), "clusters": boot_6h["n_active_blocks"]},
                    "block_24h": {"p_val": round(boot_24h["p_value"], 5), "clusters": boot_24h["n_active_blocks"]},
                },
            }

        train_res = _eval_split(sub_train, "TRAIN")
        val_res = _eval_split(sub_val, "VALIDATION")
        test_res = _eval_split(sub_test, "TEST")
        oot_res = _eval_split(sub_oot, "OUT_OF_TIME_Q1_2024")

        candidate_results.append({
            "hypothesis": hyp_name,
            "total_sample_size": n_total,
            "train": train_res,
            "validation": val_res,
            "test": test_res,
            "out_of_time_q1_2024": oot_res,
        })

    # Multiple Testing FDR across TEST partition
    test_p_vals = [c["test"].get("bootstrap_6h", {}).get("raw_p", 1.0) for c in candidate_results]
    sorted_indices = np.argsort(test_p_vals)
    m = len(PHASE14_HYPOTHESES)
    fdr_q_values = [1.0] * m
    cum_min = 1.0
    for rank in range(m, 0, -1):
        idx = sorted_indices[rank - 1]
        p_val = test_p_vals[idx]
        q_val = min(1.0, (m / rank) * p_val)
        cum_min = min(cum_min, q_val)
        fdr_q_values[idx] = round(cum_min, 5)

    for i, c in enumerate(candidate_results):
        c["test"]["fdr_q"] = fdr_q_values[i]
        c["test"]["fdr_significant"] = bool(fdr_q_values[i] < 0.05)

        # Decision classification
        net_ret_test_bps = c["test"].get("net_mean_return_9_1bps", -999.0)
        net_ret_oot_bps = c["out_of_time_q1_2024"].get("net_mean_return_9_1bps", -999.0)
        n_test = c["test"].get("sample_size", 0)

        if n_test < 30:
            c["verdict"] = "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
        elif c["test"]["fdr_significant"] and net_ret_test_bps > 0 and net_ret_oot_bps > 0:
            c["verdict"] = "STATISTICALLY_SUPPORTED_CANDIDATE_UNDER_MODELED_COSTS"
        elif c["train"].get("net_mean_return_9_1bps", -999.0) > 0 or c["validation"].get("net_mean_return_9_1bps", -999.0) > 0:
            c["verdict"] = "EXPLORATORY_CANDIDATE_NOT_CONFIRMED"
        else:
            c["verdict"] = "NO_EDGE_FOUND"

    # Stop Room Confirmatory Summary on TEST & Q1 2024
    def _stop_summary(df_sub: pd.DataFrame, scope_label: str) -> List[Dict[str, Any]]:
        summary = []
        for model_name in STOP_MODELS:
            sub_m = df_sub[df_sub["stop_model"] == model_name]
            n_m = len(sub_m)
            if n_m == 0:
                continue
            class_counts = sub_m["resumption_class"].value_counts().to_dict()
            summary.append({
                "stop_model": model_name,
                "scope": scope_label,
                "sample_size": n_m,
                "mean_gross_r": round(float(np.mean(sub_m["gross_realized_r"].values)), 4),
                "mean_net_r_fee_slip": round(float(np.mean(sub_m["net_r_fee_slip"].values)), 4),
                "class_a_pct": round((class_counts.get("CLASS_A", 0) / n_m) * 100, 2),
                "class_b_resumed_pct": round((class_counts.get("CLASS_B", 0) / n_m) * 100, 2),
                "class_c_winner_pct": round((class_counts.get("CLASS_C", 0) / n_m) * 100, 2),
            })
        return summary

    df_evals_test = df_evals[df_evals["split"] == "TEST"]
    df_evals_oot = df_evals[df_evals["split"] == "OUT_OF_TIME_Q1_2024"]

    stop_summary_test = _stop_summary(df_evals_test, "TEST_CONFIRMATORY_2023")
    stop_summary_oot = _stop_summary(df_evals_oot, "OUT_OF_TIME_Q1_2024")

    final_results = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_events": len(df_evs),
        "total_forward_outcomes": len(df_outs),
        "total_stop_evaluations": len(df_evals),
        "symbols": symbols,
        "datasets": {
            "universe_2023": universe_2023_path,
            "universe_2024_oot": universe_2024_path,
        },
        "hypothesis_results": candidate_results,
        "stop_models_summary_test": stop_summary_test,
        "stop_models_summary_oot": stop_summary_oot,
        "stop_diagnostics": engine.stop_diagnostics,
    }

    results_path = os.path.join(output_dir, "phase14_composite_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(final_results, f, indent=2)

    logger.info("Phase 14 results saved to %s", results_path)
    return final_results


if __name__ == "__main__":
    run_phase14_experiment()
