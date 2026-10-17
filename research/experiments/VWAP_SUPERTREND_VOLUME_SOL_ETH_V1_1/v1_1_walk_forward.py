import os
import json
import pandas as pd
from datetime import datetime
import sys

# Adjust PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.VWAP_SUPERTREND_VOLUME_SOL_ETH_V1_1.vwap_st_v1_1_backtest import (
    prepare_features, run_simulation, SYMBOLS
)

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Data splits (2022-01-01 to 2023-12-31 is available)
TRAIN_END = "2023-06-30"
VAL_END = "2023-10-31"

def split_data(df: pd.DataFrame):
    train_df = df[df['timestamp'] <= TRAIN_END].copy()
    val_df = df[(df['timestamp'] > TRAIN_END) & (df['timestamp'] <= VAL_END)].copy()
    holdout_df = df[df['timestamp'] > VAL_END].copy()
    return train_df, val_df, holdout_df

def compute_stats(df_ev: pd.DataFrame):
    if len(df_ev) == 0:
        return {"total_trades": 0}
        
    stats = {
        "total_trades": len(df_ev),
        "longs": len(df_ev[df_ev['direction'] == 'LONG']),
        "shorts": len(df_ev[df_ev['direction'] == 'SHORT']),
        "gross_win_rate": float((df_ev['gross_return_pct'] > 0).mean()),
        "net_win_rate": float((df_ev['net_return_pct'] > 0).mean()),
        "milestone_hit_rate": float(df_ev['partial_achieved'].mean()),
        "mean_gross_return_bps": float(df_ev['gross_return_pct'].mean() * 100),
        "mean_net_return_bps": float(df_ev['net_return_pct'].mean() * 100),
        "mean_holding_bars": float(df_ev['holding_bars'].mean()),
        "mean_mfe_bps": float(df_ev['mfe_pct'].mean() * 100),
        "mean_mae_bps": float(df_ev['mae_pct'].mean() * 100)
    }
    return stats

from concurrent.futures import ProcessPoolExecutor, as_completed
from research.experiments.vwap_supertrend.indicators import calc_session_vwap, calc_supertrend

def process_config(sym, config, train_df):
    key = f"{sym}_S{config['stop_bps']}_V{config['vol_mult']}-{config['vol_window']}_C{config.get('anti_chop_variant', 'N')}_{config['ab_name']}"
    events = run_simulation(train_df, sym, config)
    df_ev = pd.DataFrame(events)
    stats = compute_stats(df_ev)
    return key, config, stats

def run_walk_forward():
    loader = ResearchDataLoader()
    
    stop_buffers = [0, 5, 10, 20]
    vol_configs = [
        {"mult": 1.25, "win": 5},
        {"mult": 1.5, "win": 5}
    ]
    chop_variants = ['A', 'B']
    
    # Ablation matrix
    ablations = [
        {"name": "BASE", "use_vol": False, "use_chop": False},
        {"name": "BASE+VOL", "use_vol": True, "use_chop": False},
        {"name": "BASE+CHOP", "use_vol": False, "use_chop": True},
        {"name": "BASE+VOL+CHOP", "use_vol": True, "use_chop": True}
    ]
    
    base_cost = 12.0
    base_milestone = 80.0
    
    all_results = {}
    
    for sym in SYMBOLS:
        print(f"Loading {sym}...")
        df = loader.load_symbol(sym)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        df_5m = df.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'delta_v': 'sum'
        }).dropna().reset_index()
        
        # Pre-calculate expensive constant features to save time across processes
        df_5m['VWAP'] = calc_session_vwap(df_5m)
        df_5m = calc_supertrend(df_5m, length=10, factor=3.0)
        
        train_df, val_df, holdout_df = split_data(df_5m)
        print(f"{sym} Splits -> Train: {len(train_df)}, Val: {len(val_df)}, Holdout: {len(holdout_df)}")
        
        sym_results = {}
        best_net_bps = -9999
        best_config = None
        
        configs_to_run = []
        for stop_bps in stop_buffers:
            for vol in vol_configs:
                for ab in ablations:
                    for cv in chop_variants:
                        if not ab['use_chop'] and cv == 'B':
                            continue
                        if not ab['use_vol'] and vol != vol_configs[0]:
                            continue
                        
                        configs_to_run.append({
                            'stop_bps': stop_bps,
                            'net_milestone_bps': base_milestone,
                            'round_trip_cost_bps': base_cost,
                            'use_vol': ab['use_vol'],
                            'vol_mult': vol['mult'],
                            'vol_window': vol['win'],
                            'use_chop': ab['use_chop'],
                            'anti_chop_variant': cv,
                            'ab_name': ab['name']
                        })
                        
        print(f"Running {len(configs_to_run)} configurations for {sym} using ProcessPool...")
        with ProcessPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(process_config, sym, cfg, train_df): cfg for cfg in configs_to_run}
            for future in as_completed(futures):
                key, cfg, stats = future.result()
                sym_results[key] = stats
                
                if stats.get('total_trades', 0) > 10:
                    if stats.get('mean_net_return_bps', -9999) > best_net_bps:
                        best_net_bps = stats['mean_net_return_bps']
                        best_config = cfg
                        
        print(f"Best Train Config for {sym}: {best_config} with {best_net_bps} bps")
        
        # Run Validate on Best Config
        if best_config:
            val_events = run_simulation(val_df, sym, best_config)
            val_stats = compute_stats(pd.DataFrame(val_events))
            print(f"{sym} Validate Results: {val_stats}")
            
            # Run Holdout on Best Config
            ho_events = run_simulation(holdout_df, sym, best_config)
            ho_stats = compute_stats(pd.DataFrame(ho_events))
            print(f"{sym} Holdout Results: {ho_stats}")
            
            # Save holdout events
            with open(os.path.join(RESULTS_DIR, f"{sym}_holdout_events.jsonl"), "w") as f:
                for e in ho_events:
                    f.write(json.dumps(e) + "\n")
        else:
            val_stats = {}
            ho_stats = {}
            
        all_results[sym] = {
            "best_train_config": best_config,
            "train_sweeps": sym_results,
            "validate_results": val_stats,
            "holdout_results": ho_stats
        }
        
    with open(os.path.join(RESULTS_DIR, "v1_1_walk_forward_results.json"), "w") as f:
        json.dump(all_results, f, indent=4)
        
    print("Walk-Forward complete.")

if __name__ == "__main__":
    run_walk_forward()
