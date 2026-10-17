import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.VWAP_SUPERTREND_VOLUME_SOL_ETH_V1_1.vwap_st_v1_1_backtest import (
    prepare_features, run_simulation, calculate_net_returns
)

def build_forward_returns(df):
    """
    Given a dataframe with 5m candles, compute forward returns relative to the OPEN of the NEXT candle (t+1).
    Signal is at t. Entry is open[t+1].
    5m return = close[t+2] / open[t+1] - 1
    15m return = close[t+4] / open[t+1] - 1
    30m return = close[t+7] / open[t+1] - 1
    60m return = close[t+13] / open[t+1] - 1
    
    We shift backwards so that at row `t` (the signal candle), these values represent the future returns of the entry at `t+1`.
    """
    df = df.copy()
    entry_price = df['open'].shift(-1)
    
    df['fwd_5m_ret'] = df['close'].shift(-2) / entry_price - 1.0
    df['fwd_15m_ret'] = df['close'].shift(-4) / entry_price - 1.0
    df['fwd_30m_ret'] = df['close'].shift(-7) / entry_price - 1.0
    df['fwd_60m_ret'] = df['close'].shift(-13) / entry_price - 1.0
    
    # 60m MFE/MAE (next 12 bars starting from t+1)
    df['fwd_60m_high'] = df['high'].shift(-1).rolling(window=12).max().shift(-11)
    df['fwd_60m_low'] = df['low'].shift(-1).rolling(window=12).min().shift(-11)
    
    df['mfe_long'] = df['fwd_60m_high'] / entry_price - 1.0
    df['mae_long'] = df['fwd_60m_low'] / entry_price - 1.0
    
    df['mfe_short'] = 1.0 - df['fwd_60m_low'] / entry_price
    df['mae_short'] = 1.0 - df['fwd_60m_high'] / entry_price
    
    return df

def apply_configs(df):
    prev_st_dir = df['ST_Direction'].shift(1)
    curr_st_dir = df['ST_Direction']
    
    st_flip_long = (prev_st_dir == -1) & (curr_st_dir == 1)
    st_flip_short = (prev_st_dir == 1) & (curr_st_dir == -1)
    
    vwap_long = df['close'] > df['VWAP']
    vwap_short = df['close'] < df['VWAP']
    
    vol_long = df['vol_expansion'] & df['delta_long']
    vol_short = df['vol_expansion'] & df['delta_short']
    
    chop_long = df['not_choppy_long']
    chop_short = df['not_choppy_short']
    
    configs = {
        "A": {"L": st_flip_long, "S": st_flip_short},
        "B": {"L": st_flip_long & vwap_long, "S": st_flip_short & vwap_short},
        "C": {"L": st_flip_long & vol_long, "S": st_flip_short & vol_short},
        "D": {"L": st_flip_long & chop_long, "S": st_flip_short & chop_short},
        "E": {"L": st_flip_long & vwap_long & vol_long, "S": st_flip_short & vwap_short & vol_short},
        "F": {"L": st_flip_long & vwap_long & chop_long, "S": st_flip_short & vwap_short & chop_short},
        "G": {"L": st_flip_long & vol_long & chop_long, "S": st_flip_short & vol_short & chop_short},
        "H": {"L": st_flip_long & vwap_long & vol_long & chop_long, "S": st_flip_short & vwap_short & vol_short & chop_short},
    }
    return configs

def evaluate_entry_quality(df, signal_mask, direction="L"):
    signals = df[signal_mask]
    n = len(signals)
    if n == 0:
        return {}
    
    side = 1 if direction == "L" else -1
    
    r5 = (signals['fwd_5m_ret'] * side).dropna()
    r15 = (signals['fwd_15m_ret'] * side).dropna()
    r30 = (signals['fwd_30m_ret'] * side).dropna()
    r60 = (signals['fwd_60m_ret'] * side).dropna()
    
    mfe = signals['mfe_long'].dropna() if direction == "L" else signals['mfe_short'].dropna()
    mae = signals['mae_long'].dropna() if direction == "L" else signals['mae_short'].dropna()
    
    return {
        "trades": n,
        "mean_5m_bps": float(r5.mean() * 10000) if len(r5) else 0.0,
        "mean_15m_bps": float(r15.mean() * 10000) if len(r15) else 0.0,
        "mean_30m_bps": float(r30.mean() * 10000) if len(r30) else 0.0,
        "mean_60m_bps": float(r60.mean() * 10000) if len(r60) else 0.0,
        "mean_mfe_bps": float(mfe.mean() * 10000) if len(mfe) else 0.0,
        "mean_mae_bps": float(mae.mean() * 10000) if len(mae) else 0.0,
        "pct_gt_0": float((r60 > 0).mean()) if len(r60) else 0.0,
        "pct_gt_20bps": float((r60 > 0.002).mean()) if len(r60) else 0.0,
        "pct_gt_80bps": float((r60 > 0.008).mean()) if len(r60) else 0.0,
    }

def main():
    loader = ResearchDataLoader()
    results = {}
    
    for sym in ["SOLUSDT", "ETHUSDT"]:
        print(f"Loading {sym}...")
        df_raw = loader.load_symbol(sym)
        df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], unit='ms')
        df_raw = df_raw[df_raw['timestamp'] <= "2023-10-31"]
        
        df_5m = df_raw.resample('5min', on='timestamp').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 
            'volume': 'sum', 'delta_v': 'sum'
        }).dropna().reset_index()
        
        vol_mult = 1.5 if sym == "SOLUSDT" else 1.25
        df = prepare_features(df_5m, vol_mult=vol_mult, vol_window=5, anti_chop_variant='A')
        df = build_forward_returns(df)
        
        configs = apply_configs(df)
        
        for c_name, c_masks in configs.items():
            for side in ["L", "S"]:
                stats = evaluate_entry_quality(df, c_masks[side], direction=side)
                results[f"{sym}_{c_name}_{side}"] = stats
                
    with open(os.path.join(os.path.dirname(__file__), "component_forensics_entry.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("Saved entry results.")

if __name__ == "__main__":
    main()
