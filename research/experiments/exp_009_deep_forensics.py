import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.VWAP_SUPERTREND_VOLUME_SOL_ETH_V1_1.vwap_st_v1_1_backtest import (
    prepare_features, generate_signals
)
from exp_009_component_forensics import build_forward_returns

def main():
    loader = ResearchDataLoader()
    results = {}
    
    for sym in ["SOLUSDT", "ETHUSDT"]:
        print(f"Deep Forensics on {sym}...")
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
        
        # Supertrend Raw Base
        prev_st_dir = df['ST_Direction'].shift(1)
        curr_st_dir = df['ST_Direction']
        st_long = (prev_st_dir == -1) & (curr_st_dir == 1)
        st_short = (prev_st_dir == 1) & (curr_st_dir == -1)
        
        # --- VWAP Variants ---
        vwap_res = {}
        for dist_bps in [0, 5, 10, 20]:
            dist = dist_bps / 10000.0
            vl = (df['close'] > df['VWAP'] * (1 + dist))
            vs = (df['close'] < df['VWAP'] * (1 - dist))
            for side, sig_mask, vwap_mask in [("L", st_long, vl), ("S", st_short, vs)]:
                final_mask = sig_mask & vwap_mask
                if final_mask.sum() > 0:
                    r60 = (df[final_mask]['fwd_60m_ret'] * (1 if side=="L" else -1)).dropna()
                    vwap_res[f"{sym}_{side}_{dist_bps}bps"] = {
                        "trades": len(r60),
                        "mean_60m_bps": float(r60.mean() * 10000)
                    }
        results['vwap'] = vwap_res
        
        # --- Volume Variants ---
        vol_res = {}
        exp = df['vol_expansion']
        d_long = df['delta_long']
        d_short = df['delta_short']
        
        variants = {
            "no_vol": (pd.Series(True, index=df.index), pd.Series(True, index=df.index)),
            "expansion": (exp, exp),
            "delta": (d_long, d_short),
            "both": (exp & d_long, exp & d_short)
        }
        for name, (v_l, v_s) in variants.items():
            for side, sig_mask, v_mask in [("L", st_long & (df['close']>df['VWAP']), v_l), ("S", st_short & (df['close']<df['VWAP']), v_s)]:
                final_mask = sig_mask & v_mask
                if final_mask.sum() > 0:
                    r60 = (df[final_mask]['fwd_60m_ret'] * (1 if side=="L" else -1)).dropna()
                    vol_res[f"{sym}_{side}_{name}"] = {
                        "trades": len(r60),
                        "mean_60m_bps": float(r60.mean() * 10000)
                    }
        results['volume'] = vol_res
        
        # --- Anti-Chop Deep Dive ---
        chop_res = {}
        c_long = df['not_choppy_long']
        c_short = df['not_choppy_short']
        
        for side, sig_mask, chop_mask in [("L", st_long, c_long), ("S", st_short, c_short)]:
            base_trades = df[sig_mask]
            base_r60 = (base_trades['fwd_60m_ret'] * (1 if side=="L" else -1)).dropna()
            
            filtered_trades = df[sig_mask & chop_mask]
            filt_r60 = (filtered_trades['fwd_60m_ret'] * (1 if side=="L" else -1)).dropna()
            
            removed_trades = df[sig_mask & ~chop_mask]
            rem_r60 = (removed_trades['fwd_60m_ret'] * (1 if side=="L" else -1)).dropna()
            
            fav_removed = (rem_r60 > 0).sum()
            unfav_removed = (rem_r60 <= 0).sum()
            
            chop_res[f"{sym}_{side}"] = {
                "raw_signals": len(base_r60),
                "removed_signals": len(rem_r60),
                "favorable_removed": int(fav_removed),
                "unfavorable_removed": int(unfav_removed),
                "pre_filter_mean_bps": float(base_r60.mean() * 10000) if len(base_r60) else 0.0,
                "post_filter_mean_bps": float(filt_r60.mean() * 10000) if len(filt_r60) else 0.0
            }
        results['chop'] = chop_res
        
        # --- Supertrend Transition Forensics ---
        st_res = []
        for side, sig_mask in [("L", st_long), ("S", st_short)]:
            sigs = df[sig_mask].copy()
            sigs['fwd_ret'] = sigs['fwd_60m_ret'] * (1 if side=="L" else -1)
            sigs['winner'] = sigs['fwd_ret'] > 0
            
            for _, row in sigs.dropna(subset=['fwd_ret']).iterrows():
                st_res.append({
                    "symbol": sym,
                    "side": side,
                    "close": row['close'],
                    "st_val": row['Supertrend'],
                    "dist_vwap_bps": float((row['close'] / row['VWAP'] - 1) * 10000),
                    "dist_st_bps": float((row['close'] / row['Supertrend'] - 1) * 10000),
                    "body_bps": float(abs(row['close'] - row['open']) / row['open'] * 10000),
                    "range_bps": float((row['high'] - row['low']) / row['low'] * 10000),
                    "winner": bool(row['winner'])
                })
        results['st_transitions'] = st_res

    with open(os.path.join(os.path.dirname(__file__), "component_forensics_deep.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("Saved deep forensics results.")

if __name__ == "__main__":
    main()
