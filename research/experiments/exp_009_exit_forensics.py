import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.VWAP_SUPERTREND_VOLUME_SOL_ETH_V1_1.vwap_st_v1_1_backtest import (
    prepare_features, generate_signals, calculate_net_returns
)

def run_simulation_exit_variant(df, symbol, config, exit_type):
    # Generates signals according to Config H (V1.1 Full)
    long_signals, short_signals = generate_signals(df, use_vol=True, use_chop=True)
    
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    vwaps = df['VWAP'].values
    st_dirs = df['ST_Direction'].values
    timestamps = df['timestamp'].values
    
    gross_milestone_bps = config['net_milestone_bps'] + config['round_trip_cost_bps']
    round_trip_cost_bps = config['round_trip_cost_bps']
    
    state = "FLAT"
    side = 0
    entry_price = 0.0
    active_stop = 0.0
    milestone_price = 0.0
    entry_idx = 0
    
    events = []
    
    for i in range(len(df) - 1):
        current_vwap = vwaps[i]
        
        if state != "FLAT":
            bar_high = highs[i]
            bar_low = lows[i]
            bar_open = opens[i]
            bar_close = closes[i]
            
            exit_price = None
            exit_idx = i
            
            if exit_type == "A":
                # V1.1 Exit
                hit_stop = False
                hit_milestone = False
                
                if side == 1:
                    if bar_low <= active_stop: hit_stop = True
                    if bar_high >= milestone_price: hit_milestone = True
                elif side == -1:
                    if bar_high >= active_stop: hit_stop = True
                    if bar_low <= milestone_price: hit_milestone = True
                        
                if hit_stop and hit_milestone: hit_milestone = False
                
                if hit_stop:
                    exit_price = active_stop
                    if (side == 1 and bar_open < active_stop) or (side == -1 and bar_open > active_stop):
                        exit_price = bar_open
                    state = "FLAT"
                elif hit_milestone:
                    if state == "LONG":
                        state = "LONG_PARTIAL"
                        active_stop = entry_price
                        new_stop = current_vwap - config['stop_buffer']
                        active_stop = max(active_stop, new_stop)
                    elif state == "SHORT":
                        state = "SHORT_PARTIAL"
                        active_stop = entry_price
                        new_stop = current_vwap + config['stop_buffer']
                        active_stop = min(active_stop, new_stop)
                else:
                    if state == "LONG_PARTIAL":
                        new_stop = current_vwap - config['stop_buffer']
                        active_stop = max(active_stop, new_stop)
                    elif state == "SHORT_PARTIAL":
                        new_stop = current_vwap + config['stop_buffer']
                        active_stop = min(active_stop, new_stop)
                
                if state == "FLAT":
                    gross_ret = (exit_price / entry_price - 1.0) * side
                    events.append({
                        "entry_idx": entry_idx, "exit_idx": exit_idx, "side": side,
                        "entry_price": entry_price, "exit_price": exit_price,
                        "gross_ret": gross_ret, "hit_milestone": False
                    })
                elif state in ["LONG_PARTIAL", "SHORT_PARTIAL"] and hit_milestone:
                    events.append({
                        "entry_idx": entry_idx, "exit_idx": exit_idx, "side": side,
                        "entry_price": entry_price, "exit_price": milestone_price,
                        "gross_ret": (milestone_price / entry_price - 1.0) * side, "hit_milestone": True
                    })
                    
            elif exit_type in ["B", "C", "D"]:
                # Fixed time exits: B=3, C=6, D=12 bars
                target_bars = {"B": 3, "C": 6, "D": 12}[exit_type]
                if i - entry_idx >= target_bars:
                    exit_price = bar_open
                    gross_ret = (exit_price / entry_price - 1.0) * side
                    events.append({
                        "entry_idx": entry_idx, "exit_idx": exit_idx, "side": side,
                        "entry_price": entry_price, "exit_price": exit_price,
                        "gross_ret": gross_ret, "hit_milestone": False
                    })
                    state = "FLAT"
                    
            elif exit_type == "E":
                # Opposite ST
                if side == 1 and st_dirs[i-1] == -1: # Wait, ST flipped at i-1 close
                    exit_price = bar_open
                    state = "FLAT"
                elif side == -1 and st_dirs[i-1] == 1:
                    exit_price = bar_open
                    state = "FLAT"
                
                if state == "FLAT":
                    gross_ret = (exit_price / entry_price - 1.0) * side
                    events.append({
                        "entry_idx": entry_idx, "exit_idx": exit_idx, "side": side,
                        "entry_price": entry_price, "exit_price": exit_price,
                        "gross_ret": gross_ret, "hit_milestone": False
                    })
            
            elif exit_type == "F":
                # VWAP loss exit
                if side == 1 and closes[i-1] < vwaps[i-1]:
                    exit_price = bar_open
                    state = "FLAT"
                elif side == -1 and closes[i-1] > vwaps[i-1]:
                    exit_price = bar_open
                    state = "FLAT"
                
                if state == "FLAT":
                    gross_ret = (exit_price / entry_price - 1.0) * side
                    events.append({
                        "entry_idx": entry_idx, "exit_idx": exit_idx, "side": side,
                        "entry_price": entry_price, "exit_price": exit_price,
                        "gross_ret": gross_ret, "hit_milestone": False
                    })

        if state == "FLAT":
            if long_signals[i]:
                state = "LONG"
                side = 1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                active_stop = vwaps[i] - config['stop_buffer']
                milestone_price = entry_price * (1 + gross_milestone_bps)
            elif short_signals[i]:
                state = "SHORT"
                side = -1
                entry_idx = i + 1
                entry_price = opens[i + 1]
                active_stop = vwaps[i] + config['stop_buffer']
                milestone_price = entry_price * (1 - gross_milestone_bps)
                
    return events

def aggregate_exit_events(events, cost_bps):
    if not events:
        return {}
        
    trades = {}
    for ev in events:
        eid = ev['entry_idx']
        if eid not in trades:
            trades[eid] = []
        trades[eid].append(ev)
        
    gross_rets = []
    net_rets = []
    holding_times = []
    
    cost = cost_bps / 10000.0
    
    for eid, evs in trades.items():
        if len(evs) == 1:
            g = evs[0]['gross_ret']
            gross_rets.append(g)
            net_rets.append(g - cost)
            holding_times.append(evs[0]['exit_idx'] - eid)
        else: # partial
            g1 = evs[0]['gross_ret']
            g2 = evs[1]['gross_ret']
            g_avg = (g1 + g2) / 2.0
            gross_rets.append(g_avg)
            net_rets.append(g_avg - cost)
            holding_times.append(evs[1]['exit_idx'] - eid)
            
    net_rets = np.array(net_rets)
    gross_rets = np.array(gross_rets)
    holding_times = np.array(holding_times)
    
    win_rate = (net_rets > 0).mean()
    mean_net = net_rets.mean() * 10000
    mean_gross = gross_rets.mean() * 10000
    median_net = np.median(net_rets) * 10000
    
    gross_profits = gross_rets[gross_rets > 0].sum()
    gross_losses = abs(gross_rets[gross_rets < 0].sum())
    pf = gross_profits / gross_losses if gross_losses > 0 else float('inf')
    
    return {
        "trades": len(trades),
        "mean_gross_bps": float(mean_gross),
        "mean_net_bps": float(mean_net),
        "median_net_bps": float(median_net),
        "win_rate": float(win_rate),
        "avg_holding_bars": float(holding_times.mean()),
        "profit_factor": float(pf)
    }

def main():
    loader = ResearchDataLoader()
    results = {}
    
    for sym in ["SOLUSDT", "ETHUSDT"]:
        print(f"Loading {sym} for Exits...")
        df_raw = loader.load_symbol(sym)
        df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], unit='ms')
        df_raw = df_raw[df_raw['timestamp'] <= "2023-10-31"]
        
        df_5m = df_raw.resample('5min', on='timestamp').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 
            'volume': 'sum', 'delta_v': 'sum'
        }).dropna().reset_index()
        
        vol_mult = 1.5 if sym == "SOLUSDT" else 1.25
        df = prepare_features(df_5m, vol_mult=vol_mult, vol_window=5, anti_chop_variant='A')
        
        config = {
            'net_milestone_bps': 0.0080,
            'round_trip_cost_bps': 0.0016, # will be overridden in aggregate
            'stop_buffer': df['close'].mean() * 0.0010
        }
        
        for exit_type in ["A", "B", "C", "D", "E", "F"]:
            events = run_simulation_exit_variant(df, sym, config, exit_type)
            
            for cost in [8, 12, 16, 20]:
                stats = aggregate_exit_events(events, cost)
                results[f"{sym}_Exit_{exit_type}_Cost_{cost}"] = stats

    with open(os.path.join(os.path.dirname(__file__), "component_forensics_exit.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("Saved exit results.")

if __name__ == "__main__":
    main()
