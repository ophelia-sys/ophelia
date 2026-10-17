"""Phase 12 Critical Friction Accounting Engine & Audit Runner.

Calculates the 16 exact trade-level friction fields across all research trades
and recomputes Phase 12 results under:
1. 0 friction
2. Actual BingX fee only (Maker/Taker 7 bps and Taker/Taker 10 bps)
3. Actual fee + Empirically justified slippage (9.1 bps and 12.1 bps)
4. Conservative fee + Slippage sensitivity (14.1 bps)

Outputs:
- data/phase12_friction_audit.json
- Trade-level CSV/table and aggregated USD / R statistics
"""
import copy
import dataclasses
import datetime
import json
import logging
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ophelia.friction_audit")

sys.path.insert(0, os.path.abspath("."))

# Import Phase 12 validation engine
from control_plane.phase12_timesfm_engine import (
    Phase12TimesFMValidationEngine,
    Phase12Candidate,
    D4H_SPEC_HASH,
    D4H_SPECIFICATION
)

# Standard institutional risk allocation per trade for USD calculations
R_USD_UNIT = 100.00  # $100 risk per trade

# Verified BingX Fee Rates from actual exchange fills:
BINGX_MAKER_FEE_RATE = 0.00020  # 2.0 bps (VIP0)
BINGX_TAKER_FEE_RATE = 0.00050  # 5.0 bps (VIP0)

# Typical 8-hour perpetual funding rate (0.01% = 0.0001 per 8h, or 0.0001 / 480 per minute)
FUNDING_RATE_PER_MINUTE = 0.0001 / 480.0


def calculate_trade_friction_record(
    cand: Phase12Candidate,
    entry_fee_rate: float,
    exit_fee_rate: float,
    entry_slip_rate: float,
    exit_slip_rate: float,
    apply_funding: bool = True,
    use_reforecast_exit: bool = False
) -> Dict[str, Any]:
    """Calculates all 16 required friction fields for a single trade."""
    entry_px = cand.entry_price
    sl_px = cand.sl_price
    direction = cand.direction.upper()

    # Determine exit price and duration. An early-exit cohort must use the actual
    # reforecast mark and then recompute gross/net PnL from that price. Never treat
    # an already-net R field as gross return or substitute the original trade exit.
    if use_reforecast_exit and cand.reforecast_policy == "EARLY_EXIT":
        exit_px = cand.reforecast_exit_price
        if exit_px is None or not np.isfinite(float(exit_px)) or float(exit_px) <= 0:
            raise ValueError(
                f"Candidate {cand.candidate_id} is marked EARLY_EXIT but has no valid reforecast_exit_price"
            )
        exit_px = float(exit_px)
        exit_reason = "REFORECAST_EARLY_EXIT"
        exit_time_min = 15
        gross_r = (
            (exit_px - entry_px) / cand.risk_amount
            if direction == "LONG"
            else (entry_px - exit_px) / cand.risk_amount
        )
    else:
        exit_px = cand.exit_price
        exit_reason = cand.exit_reason
        exit_time_min = cand.time_to_exit_min
        gross_r = cand.gross_realized_r

    # Structural SL distance
    sl_distance = abs(entry_px - sl_px)
    stop_distance_pct = sl_distance / max(1e-6, entry_px)

    # Actual quantity sized for $100 risk
    qty = R_USD_UNIT / max(1e-6, sl_distance)

    # 1. Entry notional
    entry_notional = qty * entry_px

    # 2. Exit notional
    exit_notional = qty * exit_px

    # 6. Gross price PnL
    if direction == "LONG":
        gross_price_pnl = qty * (exit_px - entry_px)
    else:
        gross_price_pnl = qty * (entry_px - exit_px)

    # 7, 8, 9. Exchange fees
    entry_fee = entry_notional * entry_fee_rate
    exit_fee = exit_notional * exit_fee_rate
    exchange_fee = entry_fee + exit_fee

    # 10. Funding
    if apply_funding:
        avg_notional = (entry_notional + exit_notional) / 2.0
        funding_cost = avg_notional * FUNDING_RATE_PER_MINUTE * exit_time_min
    else:
        funding_cost = 0.0

    # 11. Slippage cost
    entry_slippage_cost = entry_notional * entry_slip_rate
    exit_slippage_cost = exit_notional * exit_slip_rate
    slippage_cost = entry_slippage_cost + exit_slippage_cost

    # 12. Gross PnL
    gross_pnl = gross_price_pnl

    # 13. Net PnL
    net_pnl = gross_pnl - exchange_fee - slippage_cost - funding_cost

    # 15. R denominator
    r_denominator = R_USD_UNIT

    # 16. Net PnL expressed in R
    gross_r_calc = gross_pnl / r_denominator
    fee_r = exchange_fee / r_denominator
    slippage_r = slippage_cost / r_denominator
    funding_r = funding_cost / r_denominator
    net_r_calc = net_pnl / r_denominator

    # Friction percentages of executed notional
    total_friction_cost = exchange_fee + slippage_cost + funding_cost
    total_executed_notional = entry_notional + exit_notional
    friction_pct_of_notional = (total_friction_cost / max(1e-6, total_executed_notional)) * 100.0

    # Friction as R per trade
    friction_r_per_trade = fee_r + slippage_r + funding_r

    # Derived Fee / Gross PnL ratio (when gross_pnl != 0)
    fee_to_gross_pnl_pct = (exchange_fee / abs(gross_pnl) * 100.0) if abs(gross_pnl) > 1e-4 else 0.0

    return {
        "candidate_id": cand.candidate_id,
        "symbol": cand.symbol,
        "direction": cand.direction,
        "split": cand.split,
        "entry_notional": round(entry_notional, 2),
        "exit_notional": round(exit_notional, 2),
        "actual_quantity": round(qty, 6),
        "entry_price": round(entry_px, 4),
        "exit_price": round(exit_px, 4),
        "gross_price_pnl": round(gross_price_pnl, 2),
        "exchange_fee": round(exchange_fee, 4),
        "entry_fee": round(entry_fee, 4),
        "exit_fee": round(exit_fee, 4),
        "funding": round(funding_cost, 4),
        "slippage_cost": round(slippage_cost, 4),
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "structural_sl_distance": round(sl_distance, 4),
        "stop_distance_pct": round(stop_distance_pct * 100.0, 4),
        "r_denominator": round(r_denominator, 2),
        "gross_r": round(gross_r_calc, 4),
        "fee_r": round(fee_r, 4),
        "slippage_r": round(slippage_r, 4),
        "funding_r": round(funding_r, 4),
        "net_r": round(net_r_calc, 4),
        "friction_pct_of_notional": round(friction_pct_of_notional, 4),
        "friction_r_per_trade": round(friction_r_per_trade, 4),
        "fee_to_gross_pnl_pct": round(fee_to_gross_pnl_pct, 2),
        "exit_reason": exit_reason,
        "time_to_exit_min": exit_time_min,
        # Membership flags
        "pass_variant_d": cand.pass_variant_d,
        "pass_d4h": cand.pass_d4h,
        "tfm_reachable": cand.tfm_reachable_binary_60m,
        "pass_downside_gate": cand.pass_downside_gate,
        "reforecast_policy": cand.reforecast_policy
    }


def compute_cohort_friction_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregates trade-level friction metrics for a cohort."""
    if not trades:
        return {
            "count": 0, "win_rate": 0.0, "tp1_hit_rate": 0.0,
            "gross_positive_rate": 0.0, "net_positive_rate": 0.0,
            "total_gross_pnl": 0.0, "total_fee": 0.0, "total_slippage": 0.0,
            "total_funding": 0.0, "total_net_pnl": 0.0,
            "gross_r": 0.0, "fee_r": 0.0, "slippage_r": 0.0, "funding_r": 0.0, "net_r": 0.0,
            "mean_gross_r": 0.0, "mean_fee_r": 0.0, "mean_slippage_r": 0.0, "mean_funding_r": 0.0, "mean_net_r": 0.0,
            "profit_factor": 0.0,
            "mean_friction_pct_notional": 0.0, "mean_friction_r_per_trade": 0.0,
            "median_fee_to_gross_pnl_pct": 0.0
        }

    n = len(trades)
    # Keep distinct outcome definitions. A positive gross mark-to-market return is
    # not the same as hitting TP1, and neither guarantees positive PnL after costs.
    tp1_wins = [t for t in trades if t["exit_reason"] in ("TP1", "TP2")]
    gross_positive = [t for t in trades if t["gross_r"] > 0]
    net_positive = [t for t in trades if t["net_r"] > 0]
    tp1_hit_rate = (len(tp1_wins) / n) * 100.0
    gross_positive_rate = (len(gross_positive) / n) * 100.0
    net_positive_rate = (len(net_positive) / n) * 100.0

    total_gross_pnl = sum(t["gross_pnl"] for t in trades)
    total_fee = sum(t["exchange_fee"] for t in trades)
    total_slippage = sum(t["slippage_cost"] for t in trades)
    total_funding = sum(t["funding"] for t in trades)
    total_net_pnl = sum(t["net_pnl"] for t in trades)

    gross_r = sum(t["gross_r"] for t in trades)
    fee_r = sum(t["fee_r"] for t in trades)
    slippage_r = sum(t["slippage_r"] for t in trades)
    funding_r = sum(t["funding_r"] for t in trades)
    net_r = sum(t["net_r"] for t in trades)

    pos_r = sum(t["net_r"] for t in trades if t["net_r"] > 0)
    neg_r = abs(sum(t["net_r"] for t in trades if t["net_r"] < 0))
    pf = (pos_r / max(1e-6, neg_r)) if neg_r > 0 else (999.0 if pos_r > 0 else 0.0)

    mean_f_notional = np.mean([t["friction_pct_of_notional"] for t in trades])
    mean_f_r = np.mean([t["friction_r_per_trade"] for t in trades])

    # Fee to gross PnL percentage on winning trades
    win_fee_ratios = [t["fee_to_gross_pnl_pct"] for t in gross_positive if t["fee_to_gross_pnl_pct"] > 0]
    median_fee_pnl = float(np.median(win_fee_ratios)) if win_fee_ratios else 0.0

    return {
        "count": n,
        # Compatibility alias: win_rate means TP1/TP2 hit rate, matching Phase 12.
        "win_rate": round(tp1_hit_rate, 2),
        "tp1_hit_rate": round(tp1_hit_rate, 2),
        "gross_positive_rate": round(gross_positive_rate, 2),
        "net_positive_rate": round(net_positive_rate, 2),
        "total_gross_pnl": round(total_gross_pnl, 2),
        "total_fee": round(total_fee, 2),
        "total_slippage": round(total_slippage, 2),
        "total_funding": round(total_funding, 2),
        "total_net_pnl": round(total_net_pnl, 2),
        "gross_r": round(gross_r, 2),
        "fee_r": round(fee_r, 2),
        "slippage_r": round(slippage_r, 2),
        "funding_r": round(funding_r, 2),
        "net_r": round(net_r, 2),
        "mean_gross_r": round(gross_r / n, 4),
        "mean_fee_r": round(fee_r / n, 4),
        "mean_slippage_r": round(slippage_r / n, 4),
        "mean_funding_r": round(funding_r / n, 4),
        "mean_net_r": round(net_r / n, 4),
        "profit_factor": round(pf, 2),
        "mean_friction_pct_notional": round(float(mean_f_notional), 4),
        "mean_friction_r_per_trade": round(float(mean_f_r), 4),
        "median_fee_to_gross_pnl_pct": round(median_fee_pnl, 2)
    }


def main():
    parquet_path = "data/processed/phase12_fresh_universe_1m.parquet"
    if not os.path.exists(parquet_path):
        print(f"Error: Parquet file not found at {parquet_path}")
        sys.exit(1)

    # 1. Initialize validation engine and evaluate candidates
    logger.info("Initializing Phase 12 validation engine...")
    engine = Phase12TimesFMValidationEngine(parquet_path=parquet_path)
    engine.load_and_resample_universe()

    # Generate or load candidates
    cands_cache = "data/phase12_evaluated_candidates_cache.json"
    evaluated_candidates: List[Phase12Candidate] = []

    if os.path.exists(cands_cache):
        logger.info("Loading evaluated candidates from cache %s ...", cands_cache)
        with open(cands_cache, "r") as f:
            raw_c_list = json.load(f)
        for rc in raw_c_list:
            evaluated_candidates.append(Phase12Candidate(**rc))
        engine.all_candidates = evaluated_candidates
        logger.info("Loaded %d candidates from cache", len(evaluated_candidates))
    else:
        logger.info("Evaluating candidates across universe with TimesFM...")
        engine.run_validation()
        evaluated_candidates = engine.all_candidates
        # Save cache
        c_dicts = [dataclasses.asdict(c) for c in evaluated_candidates]
        with open(cands_cache, "w") as f:
            json.dump(c_dicts, f)
        logger.info("Saved %d candidates to cache %s", len(evaluated_candidates), cands_cache)

    # Filter candidates by split
    test_candidates = [c for c in evaluated_candidates if c.split == "TEST"]
    logger.info("Total TEST candidates: %d", len(test_candidates))

    # Cohort candidate subsets for TEST split
    cohort_cands = {
        "A_BASELINE": test_candidates,
        "B_VARIANT_D": [c for c in test_candidates if c.pass_variant_d],
        "C_D4H": [c for c in test_candidates if c.pass_d4h],
        "D_D4H_TFM_REACHABLE": [c for c in test_candidates if c.pass_d4h and c.tfm_reachable_binary_60m],
        "E_D4H_TFM_DOWNSIDE": [c for c in test_candidates if c.pass_d4h and c.tfm_reachable_binary_60m and c.pass_downside_gate],
        "F_D4H_TFM_MANAGED": [c for c in test_candidates if c.pass_d4h and c.tfm_reachable_binary_60m and c.pass_downside_gate]
    }

    # Define the 4 Core Friction Scenarios:
    scenarios = {
        "scenario_1_zero_friction": {
            "name": "Zero Friction (Gross Benchmark)",
            "entry_fee_rate": 0.0000,
            "exit_fee_rate": 0.0000,
            "entry_slip_rate": 0.0000,
            "exit_slip_rate": 0.0000,
            "apply_funding": False,
            "nominal_bps": 0.0,
            "description": "0 bps: Zero exchange fee, zero slippage, zero funding."
        },
        "scenario_2a_verified_maker_taker_fee_only": {
            "name": "Verified BingX Fee Only (Maker Entry + Taker Exit)",
            "entry_fee_rate": BINGX_MAKER_FEE_RATE,   # 2.0 bps
            "exit_fee_rate": BINGX_TAKER_FEE_RATE,    # 5.0 bps
            "entry_slip_rate": 0.0000,
            "exit_slip_rate": 0.0000,
            "apply_funding": False,
            "nominal_bps": 7.0,
            "description": "7.0 bps: 2 bps maker limit entry + 5 bps taker exit, 0 slippage, 0 funding."
        },
        "scenario_2b_verified_taker_taker_fee_only": {
            "name": "Verified BingX Fee Only (Taker Entry + Taker Exit)",
            "entry_fee_rate": BINGX_TAKER_FEE_RATE,   # 5.0 bps
            "exit_fee_rate": BINGX_TAKER_FEE_RATE,    # 5.0 bps
            "entry_slip_rate": 0.0000,
            "exit_slip_rate": 0.0000,
            "apply_funding": False,
            "nominal_bps": 10.0,
            "description": "10.0 bps: 5 bps taker market entry + 5 bps taker exit, 0 slippage, 0 funding."
        },
        "scenario_3a_actual_fee_empirical_slippage_maker": {
            "name": "Actual Fee + Empirical Slippage (Maker Entry + Taker Exit)",
            "entry_fee_rate": BINGX_MAKER_FEE_RATE,   # 2.0 bps
            "exit_fee_rate": BINGX_TAKER_FEE_RATE,    # 5.0 bps
            "entry_slip_rate": 0.0001,                # 1.0 bps
            "exit_slip_rate": 0.0001,                 # 1.0 bps
            "apply_funding": True,                    # ~0.08 bps avg
            "nominal_bps": 9.1,
            "description": "9.1 bps: 7.0 bps fee (2 maker/5 taker) + 2.0 bps slippage (1 entry/1 exit) + pro-rated funding."
        },
        "scenario_3b_actual_fee_empirical_slippage_taker": {
            "name": "Actual Fee + Empirical Slippage (Taker Entry + Taker Exit)",
            "entry_fee_rate": BINGX_TAKER_FEE_RATE,   # 5.0 bps
            "exit_fee_rate": BINGX_TAKER_FEE_RATE,    # 5.0 bps
            "entry_slip_rate": 0.0001,                # 1.0 bps
            "exit_slip_rate": 0.0001,                 # 1.0 bps
            "apply_funding": True,                    # ~0.08 bps avg
            "nominal_bps": 12.1,
            "description": "12.1 bps: 10.0 bps fee (5 taker/5 taker) + 2.0 bps slippage (1 entry/1 exit) + pro-rated funding."
        },
        "scenario_4_conservative_sensitivity": {
            "name": "Conservative Fee + Slippage Sensitivity",
            "entry_fee_rate": BINGX_TAKER_FEE_RATE,   # 5.0 bps
            "exit_fee_rate": BINGX_TAKER_FEE_RATE,    # 5.0 bps
            "entry_slip_rate": 0.0002,                # 2.0 bps
            "exit_slip_rate": 0.0002,                 # 2.0 bps
            "apply_funding": True,
            "nominal_bps": 14.1,
            "description": "14.1 bps: 10.0 bps taker fees + 4.0 bps slippage (2 entry/2 exit) + pro-rated funding."
        }
    }

    # Compute audit results across all scenarios and cohorts
    audit_results: Dict[str, Any] = {
        "spec_hash": D4H_SPEC_HASH,
        "dataset_period": "2023-12-01 to 2024-03-31 (122 calendar days)",
        "fixed_risk_usd_per_trade": R_USD_UNIT,
        "verified_bingx_fees": {
            "maker_fee_rate": BINGX_MAKER_FEE_RATE,
            "taker_fee_rate": BINGX_TAKER_FEE_RATE,
            "empirical_basis": "Verified from actual VPS BingX fill records (Position 316, 384)"
        },
        "stop_distance_distribution_d4h_test": {},
        "scenarios": {},
        "trade_level_samples": []
    }

    # Stop distance statistics on D4H TEST cohort (N=132)
    d4h_cands = cohort_cands["C_D4H"]
    stop_pcts = [abs(c.entry_price - c.sl_price) / c.entry_price * 100.0 for c in d4h_cands]
    audit_results["stop_distance_distribution_d4h_test"] = {
        "count": len(d4h_cands),
        "mean_pct": round(float(np.mean(stop_pcts)), 4),
        "median_pct": round(float(np.median(stop_pcts)), 4),
        "min_pct": round(float(np.min(stop_pcts)), 4),
        "max_pct": round(float(np.max(stop_pcts)), 4),
        "std_pct": round(float(np.std(stop_pcts)), 4),
        "implied_r_cost_at_7bps": round(0.07 / float(np.mean(stop_pcts)), 4),
        "implied_r_cost_at_9bps": round(0.09 / float(np.mean(stop_pcts)), 4),
        "implied_r_cost_at_12bps": round(0.12 / float(np.mean(stop_pcts)), 4),
        "implied_r_cost_at_14bps": round(0.14 / float(np.mean(stop_pcts)), 4),
    }

    # Evaluate each scenario
    for sc_key, sc_cfg in scenarios.items():
        logger.info("Computing metrics for %s (%s)...", sc_key, sc_cfg["name"])
        sc_out: Dict[str, Any] = {
            "config": sc_cfg,
            "cohorts": {}
        }

        for c_name, c_list in cohort_cands.items():
            use_reforecast = (c_name == "F_D4H_TFM_MANAGED")
            trade_records = [
                calculate_trade_friction_record(
                    cand=c,
                    entry_fee_rate=sc_cfg["entry_fee_rate"],
                    exit_fee_rate=sc_cfg["exit_fee_rate"],
                    entry_slip_rate=sc_cfg["entry_slip_rate"],
                    exit_slip_rate=sc_cfg["exit_slip_rate"],
                    apply_funding=sc_cfg["apply_funding"],
                    use_reforecast_exit=use_reforecast
                )
                for c in c_list
            ]

            cohort_metrics = compute_cohort_friction_metrics(trade_records)
            sc_out["cohorts"][c_name] = cohort_metrics

            # If Scenario 3A and D4H_TFM_REACHABLE, store sample trade records
            if sc_key == "scenario_3a_actual_fee_empirical_slippage_maker" and c_name == "D_D4H_TFM_REACHABLE" and not audit_results["trade_level_samples"]:
                audit_results["trade_level_samples"] = trade_records[:10]

        audit_results["scenarios"][sc_key] = sc_out

    # Save to data/phase12_friction_audit.json
    out_path = "data/phase12_friction_audit.json"
    with open(out_path, "w") as f:
        json.dump(audit_results, f, indent=2)
    logger.info("Friction audit successfully saved to %s", out_path)

    # Print summary tables to console
    print("\n" + "=" * 115)
    print("OPHELIA PHASE 12: CRITICAL FRICTION ACCOUNTING AUDIT SUMMARY")
    print("=" * 115)
    print(f"Spec Hash:              {D4H_SPEC_HASH}")
    print(f"Dataset Window:         {audit_results['dataset_period']}")
    sd = audit_results["stop_distance_distribution_d4h_test"]
    print(f"D4H Stop Distance:      Mean={sd['mean_pct']:.3f}% | Median={sd['median_pct']:.3f}% | Min={sd['min_pct']:.3f}% | Max={sd['max_pct']:.3f}%")
    print(f"Implied Friction in R:  7 bps={sd['implied_r_cost_at_7bps']:.3f}R | 9 bps={sd['implied_r_cost_at_9bps']:.3f}R | 12 bps={sd['implied_r_cost_at_12bps']:.3f}R | 14 bps={sd['implied_r_cost_at_14bps']:.3f}R")
    print("-" * 115)

    for sc_key, sc_data in audit_results["scenarios"].items():
        cfg = sc_data["config"]
        print(f"\n>>> {cfg['name'].upper()} ({cfg['nominal_bps']:.1f} bps nominal):")
        print(f"{'COHORT':25s} {'N':>5s} {'WIN %':>7s} {'GROSS R':>9s} {'FEE R':>8s} {'SLIP R':>8s} {'FUND R':>8s} {'NET R':>9s} {'MEAN R':>8s} {'PF':>6s} {'FRIC %NOT':>10s}")
        print("-" * 115)
        for c_key in ["A_BASELINE", "B_VARIANT_D", "C_D4H", "D_D4H_TFM_REACHABLE", "E_D4H_TFM_DOWNSIDE", "F_D4H_TFM_MANAGED"]:
            m = sc_data["cohorts"][c_key]
            print(f"{c_key:25s} {m['count']:5d} {m['win_rate']:6.2f}% {m['gross_r']:+8.2f}R {m['fee_r']:7.2f}R {m['slippage_r']:7.2f}R {m['funding_r']:7.2f}R {m['net_r']:+8.2f}R {m['mean_net_r']:+7.3f}R {m['profit_factor']:6.2f} {m['mean_friction_pct_notional']:9.4f}%")

    print("\n" + "=" * 115)


if __name__ == "__main__":
    main()

