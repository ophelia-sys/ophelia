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

def build_forward_returns(df):
    df = df.copy()
    entry_price = df['open'].shift(-1)
    
    df['fwd_5m_ret'] = df['close'].shift(-2) / entry_price - 1.0
    df['fwd_15m_ret'] = df['close'].shift(-4) / entry_price - 1.0
    df['fwd_30m_ret'] = df['close'].shift(-7) / entry_price - 1.0
    df['fwd_60m_ret'] = df['close'].shift(-13) / entry_price - 1.0
    df['fwd_120m_ret'] = df['close'].shift(-25) / entry_price - 1.0
    
    df['fwd_60m_high'] = df['high'].shift(-1).rolling(window=12).max().shift(-11)
    df['fwd_60m_low'] = df['low'].shift(-1).rolling(window=12).min().shift(-11)
    df['mfe_60m'] = df['fwd_60m_high'] / entry_price - 1.0
    df['mae_60m'] = df['fwd_60m_low'] / entry_price - 1.0
    
    df['fwd_120m_high'] = df['high'].shift(-1).rolling(window=24).max().shift(-23)
    df['fwd_120m_low'] = df['low'].shift(-1).rolling(window=24).min().shift(-23)
    df['mfe_120m'] = df['fwd_120m_high'] / entry_price - 1.0
    df['mae_120m'] = df['fwd_120m_low'] / entry_price - 1.0
    
    return df

def simulate_exits(df, signal_mask, config, exit_type="A"):
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    vwaps = df['VWAP'].values
    st_dir = df['ST_Direction'].values
    
    signals = np.where(signal_mask)[0]
    events = []
    
    rt_cost_pct = config['round_trip_cost_bps'] / 10000.0
    net_milestone_pct = config['net_milestone_bps'] / 10000.0
    gross_milestone_pct = net_milestone_pct + rt_cost_pct
    
    for i in signals:
        if i >= len(df) - 1:
            continue
            
        entry_idx = i + 1
        entry_price = opens[entry_idx]
        
        mfe_val = entry_price
        mae_val = entry_price
        
        if exit_type in ["B", "C", "D"]:
            bars = 3 if exit_type == "B" else (6 if exit_type == "C" else 12)
            exit_idx = min(entry_idx + bars - 1, len(df) - 1)
            if exit_idx >= entry_idx:
                mfe_val = np.max(highs[entry_idx:exit_idx+1])
                mae_val = np.min(lows[entry_idx:exit_idx+1])
                exit_price = closes[exit_idx]
                ret_pct = exit_price / entry_price - 1.0
                events.append({
                    "signal_idx": i,
                    "entry_idx": entry_idx,
                    "exit_idx": exit_idx,
                    "gross_return_pct": ret_pct,
                    "net_return_pct": ret_pct - rt_cost_pct,
                    "mfe_pct": mfe_val / entry_price - 1.0,
                    "mae_pct": mae_val / entry_price - 1.0,
                    "holding_bars": exit_idx - entry_idx
                })
            continue
            
        active_stop = vwaps[i]
        milestone_price = entry_price * (1.0 + gross_milestone_pct)
        state = "ACTIVE"
        
        for j in range(entry_idx, len(df)):
            bar_high = highs[j]
            bar_low = lows[j]
            bar_open = opens[j]
            bar_close = closes[j]
            current_vwap = vwaps[j]
            
            mfe_val = max(mfe_val, bar_high)
            mae_val = min(mae_val, bar_low)
            
            exit_triggered = False
            exit_price = 0.0
            
            if exit_type == "A":
                hit_stop = bar_low <= active_stop
                hit_milestone = bar_high >= milestone_price
                
                if hit_stop and hit_milestone:
                    hit_milestone = False
                    
                if hit_stop:
                    exit_price = active_stop if bar_open >= active_stop else bar_open
                    exit_triggered = True
                elif hit_milestone and state == "ACTIVE":
                    state = "PARTIAL"
                    active_stop = entry_price
                    
                if state == "PARTIAL" and not exit_triggered:
                    active_stop = max(active_stop, current_vwap)
                    
            elif exit_type == "E":
                if st_dir[j-1] == -1: 
                    exit_price = bar_open
                    exit_triggered = True
            
            elif exit_type == "F":
                if closes[j-1] < vwaps[j-1]: 
                    exit_price = bar_open
                    exit_triggered = True
                    
            if exit_triggered or j == len(df) - 1:
                if j == len(df) - 1 and not exit_triggered:
                    exit_price = bar_close
                    
                final_leg_gross_pct = exit_price / entry_price - 1.0
                
                if state == "PARTIAL":
                    true_gross_pct = (0.5 * gross_milestone_pct) + (0.5 * final_leg_gross_pct)
                    net_ret = true_gross_pct - rt_cost_pct
                else:
                    true_gross_pct = final_leg_gross_pct
                    net_ret = true_gross_pct - rt_cost_pct
                
                events.append({
                    "signal_idx": i,
                    "entry_idx": entry_idx,
                    "exit_idx": j,
                    "gross_return_pct": true_gross_pct,
                    "net_return_pct": net_ret,
                    "mfe_pct": mfe_val / entry_price - 1.0,
                    "mae_pct": mae_val / entry_price - 1.0,
                    "holding_bars": j - entry_idx
                })
                break
                
    return events

def analyze_period(df, period_name, generate_csv=False):
    config = {
        'vol_mult': 1.25,
        'vol_window': 5,
        'anti_chop_variant': 'A',
        'round_trip_cost_bps': 8,
        'net_milestone_bps': 80,
        'stop_bps': 0
    }
    
    df_features = prepare_features(df, vol_mult=config['vol_mult'], vol_window=config['vol_window'], anti_chop_variant=config['anti_chop_variant'])
    df_fwd = build_forward_returns(df_features)
    
    long_signals, _ = generate_signals(df_fwd, use_vol=True, use_chop=True)
    n_signals = long_signals.sum()
    
    r60 = df_fwd.loc[long_signals, 'fwd_60m_ret'] * 10000
    r120 = df_fwd.loc[long_signals, 'fwd_120m_ret'] * 10000
    
    exits = {}
    for et in ["A", "B", "C", "D", "E", "F"]:
        evs = simulate_exits(df_fwd, long_signals, config, exit_type=et)
        if len(evs) > 0:
            df_evs = pd.DataFrame(evs)
            exits[et] = {
                "trades": len(df_evs),
                "mean_gross_bps": df_evs['gross_return_pct'].mean() * 10000,
                "mean_net_bps": df_evs['net_return_pct'].mean() * 10000,
                "median_net_bps": df_evs['net_return_pct'].median() * 10000,
                "win_rate": (df_evs['gross_return_pct'] > 0).mean(),
                "net_win_rate": (df_evs['net_return_pct'] > 0).mean(),
                "avg_hold": df_evs['holding_bars'].mean(),
                "max_dd": df_evs['net_return_pct'].min() * 10000
            }
        else:
            exits[et] = None
            
    costs = [8, 12, 16, 20]
    sens_res = {}
    for c in costs:
        cfg = config.copy()
        cfg['round_trip_cost_bps'] = c
        evs = simulate_exits(df_fwd, long_signals, cfg, exit_type="A")
        if len(evs) > 0:
            df_evs = pd.DataFrame(evs)
            sens_res[c] = {
                "mean_net_bps": df_evs['net_return_pct'].mean() * 10000,
                "net_win_rate": (df_evs['net_return_pct'] > 0).mean(),
            }
            
    quarter_res = {}
    if n_signals > 0:
        df_evs_A = pd.DataFrame(simulate_exits(df_fwd, long_signals, config, exit_type="A")).set_index("signal_idx")
        signals_df = df_fwd[long_signals].copy()
        signals_df['signal_idx'] = signals_df.index
        signals_df = signals_df.join(df_evs_A, on='signal_idx')
        
        signals_df['quarter'] = signals_df['timestamp'].dt.to_period('Q')
        for q, grp in signals_df.groupby('quarter'):
            quarter_res[str(q)] = {
                "trades": len(grp),
                "mean_60m_bps": grp['fwd_60m_ret'].mean() * 10000,
                "mean_net_bps": grp['net_return_pct'].mean() * 10000,
                "net_win_rate": (grp['net_return_pct'] > 0).mean()
            }
        
        if generate_csv:
            csv_cols = [
                'timestamp', 'open', 'high', 'low', 'close', 'VWAP', 'ST_Direction',
                'vol_expansion', 'delta_long', 'not_choppy_long',
                'fwd_5m_ret', 'fwd_15m_ret', 'fwd_30m_ret', 'fwd_60m_ret', 'fwd_120m_ret',
                'mfe_60m', 'mae_60m', 'gross_return_pct', 'net_return_pct', 'holding_bars'
            ]
            signals_df[csv_cols].to_csv(f"ETH_LONG_signals_{period_name}.csv", index=False)

    return {
        "trades": int(n_signals),
        "mean_60m_bps": float(r60.mean()) if len(r60)>0 else 0,
        "median_60m_bps": float(r60.median()) if len(r60)>0 else 0,
        "mean_120m_bps": float(r120.mean()) if len(r120)>0 else 0,
        "exits": exits,
        "costs": sens_res,
        "quarters": quarter_res
    }

def main():
    loader = ResearchDataLoader()
    df_raw = loader.load_symbol("ETHUSDT")
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], unit='ms')
    
    df_5m = df_raw.resample('5min', on='timestamp').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 
        'volume': 'sum', 'delta_v': 'sum'
    }).dropna().reset_index()
    
    dev_mask = df_5m['timestamp'] <= "2023-10-31"
    holdout_mask = (df_5m['timestamp'] >= "2023-11-01") & (df_5m['timestamp'] <= "2023-12-31")
    
    df_dev = df_5m[dev_mask].copy()
    df_holdout = df_5m[holdout_mask].copy()
    
    print("Running DEV...")
    dev_res = analyze_period(df_dev, "DEVELOPMENT", generate_csv=True)
    
    print("Running HOLDOUT...")
    ho_res = analyze_period(df_holdout, "BLIND_HOLDOUT", generate_csv=True)
    
    res = {
        "DEV": dev_res,
        "HOLDOUT": ho_res
    }
    
    with open("eth_long_validation_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Done")

if __name__ == "__main__":
    main()
