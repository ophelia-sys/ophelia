import pandas as pd
import numpy as np
import json
import os

def run_exp_030():
    print("========================================")
    print("EXP 030: OOS RECONCILIATION")
    print("========================================")
    
    in_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\processed\phase5_5"
    out_dir = r"c:\Users\dopa.mine\Desktop\ophelia\research\results\phase5_5"
    
    oos_path = os.path.join(in_dir, "BTCUSDT_context_oos.parquet")
    preds_path = os.path.join(out_dir, "oos_predictions.parquet")
    config_path = os.path.join(out_dir, "phase5_5_dev_frozen_config.json")
    
    oos_df = pd.read_parquet(oos_path)
    preds_df = pd.read_parquet(preds_path)
    
    with open(config_path, "r") as f:
        config = json.load(f)
        
    cost_bps = config['cost_bps']
    thresholds = config['thresholds']
    
    merged = pd.merge(oos_df, preds_df, on='timestamp', how='inner')
    
    regime_map = pd.read_csv(os.path.join(out_dir, "regime_analysis_dev_val.csv"))
    robust_regimes = regime_map[regime_map['classification'] == 'ROBUST_ECONOMIC_CANDIDATE']
    
    print(f"Independent Reconciliation of OOS Performance.")
    print(f"Cost Assumption: {cost_bps} bps")
    print(f"Total Eligible Regimes to Trade: {len(robust_regimes)}")
    
    if len(robust_regimes) == 0:
        print("Reconciliation confirms NO eligible regimes were selected.")
        print("Expected Trade Count: 0")
        print("Expected Net EV: 0")
        return
        
    # If we had robust regimes, we'd verify them here.
    
if __name__ == '__main__':
    run_exp_030()
