import os
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator, _compute_barrier_numba
from research.experiments.vwap_supertrend.indicators import calc_session_vwap, calc_supertrend
from utils.logger import logger

RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'results'))
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']

EXCURSION_THRESHOLDS = [0.10, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 5.00]
COST_BPS = [0, 5, 10, 15, 20, 25]

def extract_events(df: pd.DataFrame, symbol: str) -> List[Dict[str, Any]]:
    D = df['VWAP'] - df['Supertrend']
    D_prev = D.shift(1)
    
    is_bullish = (D_prev <= 0) & (D > 0) & (df['close'] > df['VWAP']) & (df['close'] > df['Supertrend'])
    is_bearish = (D_prev >= 0) & (D < 0) & (df['close'] < df['VWAP']) & (df['close'] < df['Supertrend'])
    
    raw_signals = np.zeros(len(df), dtype=np.int32)
    raw_signals[is_bullish] = 1
    raw_signals[is_bearish] = -1
    
    events = []
    current_direction = 0
    
    closes = df['close'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    timestamps = df['timestamp'].values
    n = len(df)
    
    # We only iterate over the actual signal indices which are much fewer!
    signal_indices = np.where(raw_signals != 0)[0]
    
    for i in signal_indices:
        if i >= n - 1:
            continue
            
        dir_flag = raw_signals[i]
        
        if dir_flag != current_direction:
            current_direction = dir_flag
            entry_idx = i + 1
            entry_price = opens[entry_idx]
            
            end_idx = min(entry_idx + 60, n - 1)
            window_highs = highs[entry_idx:end_idx+1]
            window_lows = lows[entry_idx:end_idx+1]
            
            if dir_flag == 1:
                mfe_idx = np.argmax(window_highs)
                mfe_val = window_highs[mfe_idx]
                mae_idx = np.argmin(window_lows)
                mae_val = window_lows[mae_idx]
                mfe_pct = (mfe_val / entry_price - 1.0) * 100
                mae_pct = (mae_val / entry_price - 1.0) * 100
            else:
                mfe_idx = np.argmin(window_lows)
                mfe_val = window_lows[mfe_idx]
                mae_idx = np.argmax(window_highs)
                mae_val = window_highs[mae_idx]
                mfe_pct = (1.0 - mfe_val / entry_price) * 100
                mae_pct = (1.0 - mae_val / entry_price) * 100
                
            sub_highs = highs[entry_idx:entry_idx+61]
            sub_lows = lows[entry_idx:entry_idx+61]
            sub_closes = closes[entry_idx:entry_idx+61]
            if len(sub_closes) > 60:
                tb_outcomes, tb_exits = _compute_barrier_numba(
                    sub_highs, sub_lows, sub_closes,
                    0.0010, 0.0010, 60, is_long=(dir_flag==1)
                )
                tb_outcome = int(tb_outcomes[0])
            else:
                tb_outcome = 0
                
            def ret(bars):
                if entry_idx + bars < n:
                    if dir_flag == 1:
                        return (closes[entry_idx + bars - 1] / entry_price) - 1.0
                    else:
                        return 1.0 - (closes[entry_idx + bars - 1] / entry_price)
                return np.nan
            
            events.append({
                "event_id": f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}",
                "symbol": symbol,
                "timestamp": str(timestamps[i]),
                "year": pd.to_datetime(timestamps[i]).year,
                "direction": "LONG" if dir_flag == 1 else "SHORT",
                "entry_price": float(entry_price),
                "returns": {
                    "5m": ret(1),
                    "15m": ret(3),
                    "30m": ret(6),
                    "60m": ret(12),
                    "4h": ret(48)
                },
                "excursions": {
                    "MFE_pct": float(mfe_pct),
                    "MAE_pct": float(mae_pct),
                    "time_to_MFE_bars": int(mfe_idx),
                    "time_to_MAE_bars": int(mae_idx)
                },
                "vwap_st_directional_tb_60_10": tb_outcome
            })
            
    return events

def run_backtest():
    loader = ResearchDataLoader()
    all_events = []
    
    for sym in SYMBOLS:
        print(f"Processing {sym}...")
        df = loader.load_symbol(sym)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df_5m = df.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()
        
        df_5m['VWAP'] = calc_session_vwap(df_5m)
        df_5m = calc_supertrend(df_5m, length=10, factor=3.0)
        
        events = extract_events(df_5m, sym)
        all_events.extend(events)
        
    with open(os.path.join(RESULTS_DIR, "vwap_supertrend_events.jsonl"), "w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\n")
            
    # Compile Backtest Stats
    compile_stats(all_events)
    compile_excursions(all_events)

def compile_stats(events: List[Dict[str, Any]]):
    df = pd.json_normalize(events)
    df['return_5m'] = df['returns.5m']
    df['return_60m'] = df['returns.60m']
    
    results = {}
    
    for year in [2022, 2023, 'Combined']:
        year_df = df if year == 'Combined' else df[df['year'] == year]
        if len(year_df) == 0:
            continue
            
        stats = {
            "total_signals": len(year_df),
            "long_signals": len(year_df[year_df['direction'] == 'LONG']),
            "short_signals": len(year_df[year_df['direction'] == 'SHORT']),
            "win_rate_60m": float((year_df['return_60m'] > 0).mean()),
            "mean_return_60m": float(year_df['return_60m'].mean()),
            "median_return_60m": float(year_df['return_60m'].median())
        }
        
        # Calculate costs
        for c in COST_BPS:
            cost_frac = c / 10000.0
            net_ret = year_df['return_60m'] - cost_frac
            stats[f"net_mean_{c}bps"] = float(net_ret.mean())
            stats[f"net_win_rate_{c}bps"] = float((net_ret > 0).mean())
            
        results[str(year)] = stats
        
    with open(os.path.join(RESULTS_DIR, "vwap_supertrend_backtest.json"), "w") as f:
        json.dump(results, f, indent=4)

def compile_excursions(events: List[Dict[str, Any]]):
    df = pd.json_normalize(events)
    df['MFE'] = df['excursions.MFE_pct']
    df['MAE'] = df['excursions.MAE_pct']
    df['time_to_MFE'] = df['excursions.time_to_MFE_bars']
    df['time_to_MAE'] = df['excursions.time_to_MAE_bars']
    
    results = {}
    for year in [2022, 2023, 'Combined']:
        year_df = df if year == 'Combined' else df[df['year'] == year]
        if len(year_df) == 0:
            continue
            
        thresh_stats = {}
        for t in EXCURSION_THRESHOLDS:
            reached = year_df['MFE'] >= t
            thresh_stats[f"{t}%"] = {
                "count": int(reached.sum()),
                "percentage": float(reached.mean() * 100),
                "mean_time_bars": float(year_df[reached]['time_to_MFE'].mean()),
                "median_time_bars": float(year_df[reached]['time_to_MFE'].median()),
                "reached_before_adverse": float(((year_df['MFE'] >= t) & ((year_df['time_to_MFE'] < year_df['time_to_MAE']) | (year_df['MAE'] > -1.0))).mean() * 100)
            }
        results[str(year)] = thresh_stats
        
    with open(os.path.join(RESULTS_DIR, "vwap_supertrend_excursions.json"), "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    run_backtest()
