import os
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any

from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.VWAP_SUPERTREND_VOLUME_SOL_ETH_V1.indicators import calc_session_vwap, calc_supertrend

RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'results', 'VWAP_SUPERTREND_VOLUME_SOL_ETH_V1'))
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOLS = ['SOLUSDT', 'ETHUSDT']

def prepare_features(df_5m: pd.DataFrame, vol_mult: float, vol_window: int) -> pd.DataFrame:
    df_5m['VWAP'] = calc_session_vwap(df_5m)
    df_5m = calc_supertrend(df_5m, length=10, factor=3.0)
    
    # Volume Features
    df_5m['V_window'] = df_5m['volume'].rolling(vol_window).sum()
    df_5m['V_MA20'] = df_5m['V_window'].rolling(20).mean()
    df_5m['delta_v_window'] = df_5m['delta_v'].rolling(vol_window).sum()
    
    # Supertrend Transitions
    df_5m['st_dir'] = df_5m['ST_Direction']
    df_5m['st_dir_prev'] = df_5m['st_dir'].shift(1)
    
    is_bullish_flip = (df_5m['st_dir_prev'] > 0) & (df_5m['st_dir'] < 0)
    is_bearish_flip = (df_5m['st_dir_prev'] < 0) & (df_5m['st_dir'] > 0)
    
    vol_expansion = df_5m['V_window'] > (vol_mult * df_5m['V_MA20'])
    buy_pressure = df_5m['delta_v_window'] > 0
    sell_pressure = df_5m['delta_v_window'] < 0
    
    # Primary V1 Signal
    df_5m['long_signal_v1'] = is_bullish_flip & (df_5m['close'] > df_5m['VWAP']) & vol_expansion & buy_pressure
    df_5m['short_signal_v1'] = is_bearish_flip & (df_5m['close'] < df_5m['VWAP']) & vol_expansion & sell_pressure
    
    # Pine Reference Signal
    is_bullish_trend = df_5m['st_dir'] < 0
    is_bearish_trend = df_5m['st_dir'] > 0
    cross_above_vwap = (df_5m['close'].shift(1) < df_5m['VWAP'].shift(1)) & (df_5m['close'] > df_5m['VWAP'])
    cross_below_vwap = (df_5m['close'].shift(1) > df_5m['VWAP'].shift(1)) & (df_5m['close'] < df_5m['VWAP'])
    
    df_5m['long_signal_pine'] = cross_above_vwap & is_bullish_trend & vol_expansion & buy_pressure
    df_5m['short_signal_pine'] = cross_below_vwap & is_bearish_trend & vol_expansion & sell_pressure
    
    return df_5m

def run_simulation(df: pd.DataFrame, symbol: str, signal_prefix: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = []
    
    n = len(df)
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    vwaps = df['VWAP'].values
    timestamps = df['timestamp'].values
    
    long_signals = df[f'long_signal_{signal_prefix}'].values
    short_signals = df[f'short_signal_{signal_prefix}'].values
    
    state = "FLAT" # FLAT, ACTIVE, PARTIAL
    side = 0
    entry_price = 0.0
    active_stop = 0.0
    milestone_price = 0.0
    entry_idx = 0
    trade_id = None
    
    # Current MFE/MAE tracking
    mfe_val = 0.0
    mae_val = 0.0
    
    for i in range(1, n-1): # We need i+1 for next bar open entry
        current_vwap = vwaps[i]
        
        # 1. Update Trailing Stop at the END of the previous candle (i.e., start of this new intrabar evaluation)
        if state == "PARTIAL":
            if side == 1:
                new_stop = current_vwap * (1.0 - config['stop_bps']/10000.0)
                active_stop = max(active_stop, new_stop)
            else:
                new_stop = current_vwap * (1.0 + config['stop_bps']/10000.0)
                active_stop = min(active_stop, new_stop)
                
        # 2. Check Intrabar Stop & Milestone
        if state in ["ACTIVE", "PARTIAL"]:
            # Evaluate High/Low
            h = highs[i]
            l = lows[i]
            
            # Update MFE / MAE
            if side == 1:
                mfe_val = max(mfe_val, h)
                mae_val = min(mae_val, l)
            else:
                mfe_val = min(mfe_val, l)
                mae_val = max(mae_val, h)
                
            hit_stop = False
            hit_milestone = False
            
            if side == 1:
                if l <= active_stop:
                    hit_stop = True
                if state == "ACTIVE" and h >= milestone_price:
                    hit_milestone = True
            else:
                if h >= active_stop:
                    hit_stop = True
                if state == "ACTIVE" and l <= milestone_price:
                    hit_milestone = True
                    
            # Conservative rule: if both hit in same candle, stop hit first
            if hit_stop:
                # Close Position
                exit_price = active_stop
                # If opening gap passed the stop, we would get slippage, but let's assume stop price execution.
                # Actually, conservative gap: if open > stop for short, exit_price = open.
                if side == 1 and opens[i] < active_stop: exit_price = opens[i]
                if side == -1 and opens[i] > active_stop: exit_price = opens[i]
                
                # Calculate return
                if side == 1:
                    ret_pct = (exit_price / entry_price) - 1.0
                    mfe_pct = (mfe_val / entry_price) - 1.0
                    mae_pct = (mae_val / entry_price) - 1.0
                else:
                    ret_pct = 1.0 - (exit_price / entry_price)
                    mfe_pct = 1.0 - (mfe_val / entry_price)
                    mae_pct = 1.0 - (mae_val / entry_price)
                    
                events.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": "LONG" if side == 1 else "SHORT",
                    "entry_time": str(timestamps[entry_idx]),
                    "exit_time": str(timestamps[i]),
                    "holding_bars": i - entry_idx,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "return_pct": float(ret_pct * 100),
                    "mfe_pct": float(mfe_pct * 100),
                    "mae_pct": float(mae_pct * 100),
                    "partial_achieved": state == "PARTIAL",
                    "exit_reason": "STOP_LOSS" if state == "ACTIVE" else "TRAILING_STOP"
                })
                
                state = "FLAT"
                side = 0
            
            elif hit_milestone and state == "ACTIVE":
                # Execute 50% partial
                state = "PARTIAL"
                active_stop = entry_price # Breakeven
        
        # 3. Process Signals from Completed Candle
        if state == "FLAT":
            if long_signals[i]:
                side = 1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 - config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 + config['milestone_bps']/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"
                
            elif short_signals[i]:
                side = -1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 + config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 - config['milestone_bps']/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"
                
        else: # state in ["ACTIVE", "PARTIAL"]
            # Reverse signals
            if side == 1 and short_signals[i]:
                # Force close LONG
                exit_price = opens[i + 1]
                ret_pct = (exit_price / entry_price) - 1.0
                mfe_pct = (mfe_val / entry_price) - 1.0
                mae_pct = (mae_val / entry_price) - 1.0
                
                events.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_time": str(timestamps[entry_idx]),
                    "exit_time": str(timestamps[i + 1]),
                    "holding_bars": (i + 1) - entry_idx,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "return_pct": float(ret_pct * 100),
                    "mfe_pct": float(mfe_pct * 100),
                    "mae_pct": float(mae_pct * 100),
                    "partial_achieved": state == "PARTIAL",
                    "exit_reason": "REVERSE_SIGNAL"
                })
                
                # Open SHORT immediately on same tick
                side = -1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 + config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 - config['milestone_bps']/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"
                
            elif side == -1 and long_signals[i]:
                # Force close SHORT
                exit_price = opens[i + 1]
                ret_pct = 1.0 - (exit_price / entry_price)
                mfe_pct = 1.0 - (mfe_val / entry_price)
                mae_pct = 1.0 - (mae_val / entry_price)
                
                events.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": "SHORT",
                    "entry_time": str(timestamps[entry_idx]),
                    "exit_time": str(timestamps[i + 1]),
                    "holding_bars": (i + 1) - entry_idx,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "return_pct": float(ret_pct * 100),
                    "mfe_pct": float(mfe_pct * 100),
                    "mae_pct": float(mae_pct * 100),
                    "partial_achieved": state == "PARTIAL",
                    "exit_reason": "REVERSE_SIGNAL"
                })
                
                # Open LONG immediately on same tick
                side = 1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 - config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 + config['milestone_bps']/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"

    return events

def run_all_sensitivities():
    loader = ResearchDataLoader()
    
    # Initial Rule config
    base_config = {
        'stop_bps': 1,
        'milestone_bps': 80,
    }
    
    vol_configs = [
        {"mult": 1.00, "win": 3},
        {"mult": 1.10, "win": 3},
        {"mult": 1.25, "win": 3},
        {"mult": 1.50, "win": 3},
        {"mult": 1.00, "win": 5},
        {"mult": 1.10, "win": 5},
        {"mult": 1.25, "win": 5}, # V1 Candidate
        {"mult": 1.50, "win": 5},
        {"mult": 1.75, "win": 5},
        {"mult": 1.00, "win": 6},
        {"mult": 1.25, "win": 6},
    ]
    
    results = {}
    
    for sym in SYMBOLS:
        print(f"Loading {sym}...")
        df = loader.load_symbol(sym)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Resample 1m to 5m
        df_5m = df.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'delta_v': 'sum'
        }).dropna().reset_index()
        
        # Build features for each config and run backtest
        for vc in vol_configs:
            m = vc['mult']
            w = vc['win']
            key = f"{sym}_mult{m}_win{w}"
            
            print(f"Running {key} ...")
            df_feat = prepare_features(df_5m.copy(), vol_mult=m, vol_window=w)
            
            events = run_simulation(df_feat, sym, "v1", base_config)
            
            # Record events
            event_file = os.path.join(RESULTS_DIR, f"{key}_events.jsonl")
            with open(event_file, "w") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
                    
            # Compute stats
            df_ev = pd.DataFrame(events)
            if len(df_ev) > 0:
                # The return_pct represents the exit on 50% or 100%. 
                # Since 50% is exited at milestone, the actual realized position return is:
                # If partial_achieved: 50% @ +0.80%, 50% @ return_pct
                # If not: 100% @ return_pct
                
                realized_returns = []
                for _, row in df_ev.iterrows():
                    if row['partial_achieved']:
                        # 0.5 * 0.8% + 0.5 * remaining return
                        r = (0.5 * 0.80) + (0.5 * row['return_pct'])
                    else:
                        r = row['return_pct']
                    realized_returns.append(r)
                
                df_ev['realized_return_pct'] = realized_returns
                
                stats = {
                    "total_trades": len(df_ev),
                    "longs": len(df_ev[df_ev['direction'] == 'LONG']),
                    "shorts": len(df_ev[df_ev['direction'] == 'SHORT']),
                    "win_rate": float((df_ev['realized_return_pct'] > 0).mean()),
                    "mean_return_pct": float(df_ev['realized_return_pct'].mean()),
                    "partial_rate": float(df_ev['partial_achieved'].mean()),
                    "mean_holding_bars": float(df_ev['holding_bars'].mean()),
                    "mean_mfe_pct": float(df_ev['mfe_pct'].mean()),
                    "mean_mae_pct": float(df_ev['mae_pct'].mean())
                }
            else:
                stats = {"total_trades": 0}
            
            results[key] = stats
            
        # Run Pine Reference Variant on V1 config (mult=1.25, win=5)
        print(f"Running {sym} Pine Reference Variant ...")
        df_feat = prepare_features(df_5m.copy(), vol_mult=1.25, vol_window=5)
        events_pine = run_simulation(df_feat, sym, "pine", base_config)
        with open(os.path.join(RESULTS_DIR, f"{sym}_pine_ref_events.jsonl"), "w") as f:
            for e in events_pine:
                f.write(json.dumps(e) + "\n")
                
    with open(os.path.join(RESULTS_DIR, "sensitivity_results.json"), "w") as f:
        json.dump(results, f, indent=4)
        
    print("Backtest Complete. Results saved.")

if __name__ == "__main__":
    run_all_sensitivities()
