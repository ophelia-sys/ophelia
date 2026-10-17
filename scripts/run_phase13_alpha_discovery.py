"""Phase 13: Alpha Discovery Reset & Structural Stop-Room Research Runner.

Usage:
    python scripts/run_phase13_alpha_discovery.py [--symbols BTCUSDT,ETHUSDT,SOLUSDT] [--data-path data/processed/binance_um_universe_1m_v2.parquet]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control_plane.phase13_discovery_engine import run_alpha_discovery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("run_phase13_discovery")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Ophelia Phase 13 Alpha Discovery Reset.")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT,SOLUSDT", help="Comma-separated symbols")
    parser.add_argument("--data-path", type=str, default="data/processed/binance_um_universe_1m_v2.parquet", help="Path to 1m parquet")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    logger.info("Starting Phase 13 Alpha Discovery Reset for symbols: %s", symbols)
    logger.info("Dataset: %s", args.data_path)

    t0 = time.time()
    results = run_alpha_discovery(
        parquet_path=args.data_path,
        symbols=symbols,
        output_dir=args.output_dir,
    )
    elapsed = time.time() - t0

    logger.info("==================================================================")
    logger.info("PHASE 13 DISCOVERY COMPLETE in %.2f seconds", elapsed)
    logger.info("Total Events: %d", results["total_events"])
    logger.info("Total Forward Outcomes (8 horizons): %d", results["total_forward_outcomes"])
    logger.info("Total Stop Evaluations (4 models): %d", results["total_stop_evaluations"])
    logger.info("==================================================================")

    print("\n--- HYPOTHESIS TESTING SUMMARY (60m Horizon) ---")
    for h in results["hypothesis_results"]:
        sig_str = "REJECT NULL (SIGNIFICANT)" if h["fdr_significant"] else "FAIL TO REJECT (NOT SIG)"
        print(f"Event: {h['event_class']:<28} | N={h['n_total']:<5} | WR={h['win_rate_all_pct']}% | "
              f"DirRet={h['mean_directional_return_pct']:+.3f}% | t={h['t_stat']:+.2f} | "
              f"raw_p={h['raw_p']:.5f} | q={h['fdr_q']:.5f} | {sig_str}")

    print("\n--- MULTI-TIMEFRAME STOP MODEL EVALUATION ---")
    for sm in results["stop_models_summary"]:
        print(f"Model: {sm['stop_model']:<18} | MedSL={sm['median_sl_pct']:.2f}% | "
              f"Class B (Resumed)={sm['class_b_resumed_pct']}% | Winner={sm['class_c_winner_pct']}% | "
              f"Gross R={sm['mean_gross_r']:+.3f} | Net R (Fee+Slip)={sm['mean_net_r_fee_slip']:+.3f}")

    print("\n--- STOP-DISTANCE REGIME EVALUATION ---")
    for r in results["regimes_summary"]:
        print(f"Regime: {r['stop_regime']:<16} ({r['range_pct']:<15}) | N={r['sample_size']:<5} | "
              f"Resumed={r['class_b_resumed_pct']}% | Gross R={r['mean_gross_r']:+.3f} | "
              f"Friction R={r['mean_friction_r_slip']:.3f} | Net R={r['mean_net_r_fee_slip']:+.3f} | "
              f"95% CI=[{r['ci_95_low']:+.3f}, {r['ci_95_high']:+.3f}]")

    print("\n--- MAE DISTRIBUTION: WINNERS VS LOSERS ---")
    m = results["mae_stats"]
    print(f"Winners Median MAE: {m['winners_median_mae_pct']:.3f}% | Mean: {m['winners_mean_mae_pct']:.3f}% | "
          f"p75: {m['winners_p75_mae_pct']:.3f}% | p90: {m['winners_p90_mae_pct']:.3f}%")
    print(f"Losers Median MAE:  {m['losers_median_mae_pct']:.3f}% | Mean: {m['losers_mean_mae_pct']:.3f}%")


if __name__ == "__main__":
    main()
