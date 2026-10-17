import os
import sys
import pandas as pd
import numpy as np
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research.phase6.pipeline import ResearchPipeline
from institutional.volatility import calculate_atr
from research.phase6.statistics import fdr_bh

DATA_PATH = Path("data/processed/binance_um_universe_1m_v2.parquet")
OUTPUT_MD = Path("PHASE6_MULTI_ASSET_VALIDATION_RESULTS.md")

def main():
    logger.info(f"Loading {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    
    symbols = df['symbol'].unique()
    logger.info(f"Found {len(symbols)} symbols: {symbols}")
    
    # Store results per symbol
    all_results = {}
    
    # Collect all p_values for cross-universe FDR
    cross_universe_p_values = []
    cross_universe_meta = []
    
    for symbol in symbols:
        logger.info(f"Processing {symbol}...")
        sym_df = df[df['symbol'] == symbol].copy()
        sym_df = sym_df.sort_values('timestamp').reset_index(drop=True)
        
        # We must align ATR
        atr_series = calculate_atr(sym_df)
        
        pipeline = ResearchPipeline(n_folds=5)
        # run_pipeline will internally re-sort by timestamp, but we already sorted
        res = pipeline.run_pipeline(sym_df, atr_series)
        all_results[symbol] = res
        
        # Extract p_values for global FDR
        for stat in res['statistical_results']:
            if not np.isnan(stat.get('raw_p', np.nan)):
                cross_universe_p_values.append(stat['raw_p'])
                cross_universe_meta.append({
                    "symbol": symbol,
                    "feature": stat["feature"],
                    "horizon": stat["horizon"]
                })

    logger.info("Computing Cross-Universe FDR...")
    cross_fdr_p = fdr_bh(np.array(cross_universe_p_values))
    
    # Map back to results
    for i, meta in enumerate(cross_universe_meta):
        symbol = meta["symbol"]
        feature = meta["feature"]
        horizon = meta["horizon"]
        
        for stat in all_results[symbol]['statistical_results']:
            if stat["feature"] == feature and stat["horizon"] == horizon:
                stat["cross_universe_fdr_p"] = float(cross_fdr_p[i])
                
                # Re-classify based on cross-universe FDR
                if stat["cross_universe_fdr_p"] < 0.05 and stat["excess_return"] > 0:
                    stat["cross_classification"] = "EMPIRICAL EVIDENCE SUPPORTS FEATURE"
                else:
                    stat["cross_classification"] = "EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE"
    
    # Generate final report
    with open(OUTPUT_MD, "w") as f:
        f.write("# Phase 6 Multi-Asset Empirical Validation Results\n\n")
        f.write("## 1. Dataset Identity\n")
        f.write(f"- **Dataset ID:** `binance_um_universe_1m_v2`\n")
        f.write(f"- **Symbols:** {', '.join(symbols)}\n")
        f.write(f"- **Date Range:** {pd.to_datetime(df['timestamp'].min(), unit='ms')} to {pd.to_datetime(df['timestamp'].max(), unit='ms')}\n")
        f.write(f"- **Total Observation Count:** {len(df)}\n\n")
        
        f.write("## 2. Cross-Universe Results Summary\n")
        f.write("| Symbol | Feature | Horizon | N | Raw P | Within-Symbol FDR | Cross-Universe FDR | Cross-Classification |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        
        for symbol in symbols:
            for stat in all_results[symbol]['statistical_results']:
                if np.isnan(stat.get('raw_p', np.nan)): continue
                
                class_str = stat.get('cross_classification', 'INCONCLUSIVE')
                if class_str == "EMPIRICAL EVIDENCE SUPPORTS FEATURE":
                    class_str = "✅ SUPPORTS"
                else:
                    class_str = "❌ FAILS"
                    
                f.write(f"| {symbol} | {stat['feature']} | {stat['horizon']} | {stat['N']} | {stat['raw_p']:.4f} | {stat['fdr_p']:.4f} | {stat['cross_universe_fdr_p']:.4f} | {class_str} |\n")
                
        f.write("\n## 3. Power Analysis & Realistic Costs (Aggregate)\n")
        for symbol in symbols:
            pwr = all_results[symbol]['power']
            cost = all_results[symbol]['cost_results'].get("REALISTIC", {})
            f.write(f"### {symbol}\n")
            f.write(f"- **Effective N:** {pwr.get('effective_n', 'N/A')}\n")
            f.write(f"- **Target Power (1-β):** 0.80\n")
            f.write(f"- **Minimum Detectable Effect (MDE):** {pwr.get('minimum_detectable_effect_return', 'N/A')}\n")
            f.write(f"- **Realistic Net PnL (bps):** {cost.get('net_pnl_bps', 'N/A')}\n\n")

    logger.info(f"Results written to {OUTPUT_MD}")

if __name__ == "__main__":
    main()
