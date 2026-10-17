import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.PHASE2_EDGE_DISCOVERY_V1.features import build_base_features

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT"]
DEV_END_DATE = pd.to_datetime("2023-06-30 23:59:59")

HORIZONS_MINUTES = [15, 30, 45, 60, 90, 120, 180, 240, 300]
THRESHOLDS_BPS = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100]

def run_feasibility_screen():
    loader = ResearchDataLoader()
    results = []

    for sym in SYMBOLS:
        print(f"Processing feasibility for {sym}...")
        df_1m = loader.load_symbol(sym)
        df_5m = build_base_features(df_1m)
        
        # Slicing purely the dev set for target analysis
        df_dev = df_5m[df_5m.index <= DEV_END_DATE].copy()
        
        for h_min in HORIZONS_MINUTES:
            h_bars = h_min // 5
            
            # Point-to-point return
            df_dev[f'R_{h_min}'] = np.log(df_dev['close'].shift(-h_bars) / df_dev['close'])
            
            # Median Forward Return (Absolute)
            med_move = df_dev[f'R_{h_min}'].abs().median() * 10000
            
            for t_bps in THRESHOLDS_BPS:
                t_dec = t_bps / 10000.0
                
                # Targets
                long_mask = df_dev[f'R_{h_min}'] > t_dec
                short_mask = df_dev[f'R_{h_min}'] < -t_dec
                
                n_total = len(df_dev) - h_bars
                if n_total <= 0:
                    continue
                    
                n_long = long_mask.sum()
                n_short = short_mask.sum()
                
                rate_long = n_long / n_total
                rate_short = n_short / n_total
                rate_neutral = 1.0 - (rate_long + rate_short)
                
                diff_rates = abs(rate_long - rate_short)
                
                # Minimum movement requirement for 12bps round-trip cost
                # A target of X bps gives at most X bps (plus over-excursion).
                is_economically_constrained = t_bps <= 12
                
                results.append({
                    'symbol': sym,
                    'horizon_m': h_min,
                    'horizon_bars': h_bars,
                    'threshold_bps': t_bps,
                    'n_total': n_total,
                    'rate_long': rate_long,
                    'rate_short': rate_short,
                    'rate_neutral': rate_neutral,
                    'class_diff': diff_rates,
                    'median_abs_move_bps': med_move,
                    'is_econ_constrained': is_economically_constrained
                })

    df_res = pd.DataFrame(results)
    output_path = os.path.join(os.path.dirname(__file__), "feasibility_report.csv")
    df_res.to_csv(output_path, index=False)
    
    print("\n--- FEASIBILITY SUMMARY ---")
    print(f"Saved to {output_path}")
    
    # Global summary over all symbols
    summary = df_res.groupby(['horizon_m', 'threshold_bps']).agg({
        'rate_long': 'mean',
        'rate_short': 'mean',
        'rate_neutral': 'mean',
        'median_abs_move_bps': 'mean',
        'is_econ_constrained': 'first'
    }).reset_index()
    
    summary['viable_signal_freq'] = (summary['rate_long'] > 0.01) & (summary['rate_short'] > 0.01)
    
    viable_candidates = summary[~summary['is_econ_constrained'] & summary['viable_signal_freq']]
    
    print("\nPromising Target Regions (>12 bps threshold, >1% base rate):")
    print(viable_candidates.to_string())
    
    # Create a markdown summary for review
    md_path = os.path.join(os.path.dirname(__file__), "FEASIBILITY_SUMMARY.md")
    with open(md_path, 'w') as f:
        f.write("# PHASE 3 - FEASIBILITY SCREEN SUMMARY\n\n")
        f.write("## 1. Parameters\n")
        f.write("- **Dev Period**: 2022-01-01 to 2023-06-30\n")
        f.write("- **Holdout Period**: 2023-07-01 to 2023-12-31 (EXCLUDED)\n")
        f.write("- **Friction Hurdle**: 12 bps\n\n")
        f.write("## 2. Promising Candidates (Global Means)\n")
        f.write(viable_candidates.to_string(index=False))
        
if __name__ == "__main__":
    run_feasibility_screen()
