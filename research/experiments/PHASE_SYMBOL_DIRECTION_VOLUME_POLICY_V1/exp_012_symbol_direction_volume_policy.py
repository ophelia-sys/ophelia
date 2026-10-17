import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.VWAP_SUPERTREND_VOLUME_SOL_ETH_V1_1.vwap_st_v1_1_backtest import (
    prepare_features
)

def build_forward_returns(df):
    """
    Compute forward returns relative to the OPEN of the NEXT candle (t+1).
    Signal is at t. Entry is open[t+1].
    """
    df = df.copy()
    entry_price = df['open'].shift(-1)
    
    df['fwd_5m_ret'] = df['close'].shift(-2) / entry_price - 1.0
    df['fwd_15m_ret'] = df['close'].shift(-4) / entry_price - 1.0
    df['fwd_30m_ret'] = df['close'].shift(-7) / entry_price - 1.0
    df['fwd_60m_ret'] = df['close'].shift(-13) / entry_price - 1.0
    
    df['fwd_60m_high'] = df['high'].shift(-1).rolling(window=12).max().shift(-11)
    df['fwd_60m_low'] = df['low'].shift(-1).rolling(window=12).min().shift(-11)
    
    df['mfe_long'] = df['fwd_60m_high'] / entry_price - 1.0
    df['mae_long'] = df['fwd_60m_low'] / entry_price - 1.0
    
    df['mfe_short'] = 1.0 - df['fwd_60m_low'] / entry_price
    df['mae_short'] = 1.0 - df['fwd_60m_high'] / entry_price
    
    return df

def generate_configs(df):
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
    
    config_a_long = st_flip_long & vwap_long & vol_long & chop_long
    config_a_short = st_flip_short & vwap_short & vol_short & chop_short
    
    config_b_long = st_flip_long & vwap_long & chop_long
    config_b_short = st_flip_short & vwap_short & chop_short
    
    rejected_long = config_b_long & (~config_a_long)
    rejected_short = config_b_short & (~config_a_short)
    
    return {
        "ConfigA_L": config_a_long,
        "ConfigA_S": config_a_short,
        "ConfigB_L": config_b_long,
        "ConfigB_S": config_b_short,
        "Rejected_L": rejected_long,
        "Rejected_S": rejected_short
    }

def calc_metrics(df, mask, direction):
    signals = df[mask]
    n = len(signals)
    if n == 0:
        return {"trades": 0}
        
    side = 1 if direction == "L" else -1
    
    r5 = (signals['fwd_5m_ret'] * side).dropna()
    r15 = (signals['fwd_15m_ret'] * side).dropna()
    r30 = (signals['fwd_30m_ret'] * side).dropna()
    r60 = (signals['fwd_60m_ret'] * side).dropna()
    
    mfe = signals['mfe_long'].dropna() if direction == "L" else signals['mfe_short'].dropna()
    mae = signals['mae_long'].dropna() if direction == "L" else signals['mae_short'].dropna()
    
    res = {
        "trades": n,
        "mean_5m_bps": float(r5.mean() * 10000) if len(r5) else 0.0,
        "median_5m_bps": float(r5.median() * 10000) if len(r5) else 0.0,
        "mean_15m_bps": float(r15.mean() * 10000) if len(r15) else 0.0,
        "median_15m_bps": float(r15.median() * 10000) if len(r15) else 0.0,
        "mean_30m_bps": float(r30.mean() * 10000) if len(r30) else 0.0,
        "median_30m_bps": float(r30.median() * 10000) if len(r30) else 0.0,
        "mean_60m_bps": float(r60.mean() * 10000) if len(r60) else 0.0,
        "median_60m_bps": float(r60.median() * 10000) if len(r60) else 0.0,
        "mean_mfe_bps": float(mfe.mean() * 10000) if len(mfe) else 0.0,
        "mean_mae_bps": float(mae.mean() * 10000) if len(mae) else 0.0,
        "win_rate": float((r60 > 0).mean()) if len(r60) else 0.0,
        "pct_10bps": float((mfe > 0.001).mean()) if len(mfe) else 0.0,
        "pct_20bps": float((mfe > 0.002).mean()) if len(mfe) else 0.0,
        "pct_50bps": float((mfe > 0.005).mean()) if len(mfe) else 0.0,
        "pct_80bps_gross": float((mfe > 0.0088).mean()) if len(mfe) else 0.0,
    }
    return res

def simulate_exits(df, mask, config, direction):
    if not mask.any():
        return []
    
    events = []
    signal_indices = np.where(mask)[0]
    
    closes = df['close'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    vwaps = df['VWAP'].values
    
    gross_milestone_pct = (config['net_milestone_bps'] + config['round_trip_cost_bps']) / 10000.0
    rt_cost_pct = config['round_trip_cost_bps'] / 10000.0
    
    side = 1 if direction == "L" else -1
    
    for i in signal_indices:
        entry_idx = i + 1
        if entry_idx >= len(df) - 1:
            continue
            
        entry_price = opens[entry_idx]
        active_stop = vwaps[i]
        
        if side == 1:
            milestone_price = entry_price * (1.0 + gross_milestone_pct)
        else:
            milestone_price = entry_price * (1.0 - gross_milestone_pct)
            
        state = "ACTIVE"
        mfe_val = -np.inf if side == 1 else np.inf
        mae_val = np.inf if side == 1 else -np.inf
        
        for j in range(entry_idx, len(df)):
            bar_high = highs[j]
            bar_low = lows[j]
            bar_open = opens[j]
            bar_close = closes[j]
            current_vwap = vwaps[j]
            
            if side == 1:
                mfe_val = max(mfe_val, bar_high)
                mae_val = min(mae_val, bar_low)
            else:
                mfe_val = min(mfe_val, bar_low)
                mae_val = max(mae_val, bar_high)
            
            exit_triggered = False
            exit_price = 0.0
            
            if side == 1:
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
            else:
                hit_stop = bar_high >= active_stop
                hit_milestone = bar_low <= milestone_price
                
                if hit_stop and hit_milestone:
                    hit_milestone = False
                    
                if hit_stop:
                    exit_price = active_stop if bar_open <= active_stop else bar_open
                    exit_triggered = True
                elif hit_milestone and state == "ACTIVE":
                    state = "PARTIAL"
                    active_stop = entry_price
                    
                if state == "PARTIAL" and not exit_triggered:
                    active_stop = min(active_stop, current_vwap)
                    
            if exit_triggered or j == len(df) - 1:
                if j == len(df) - 1 and not exit_triggered:
                    exit_price = bar_close
                    
                if side == 1:
                    final_leg_gross_pct = exit_price / entry_price - 1.0
                else:
                    final_leg_gross_pct = 1.0 - exit_price / entry_price
                
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
                    "holding_bars": j - entry_idx,
                    "state": state
                })
                break
                
    return events

def evaluate_exits(df, mask, direction, cost_bps=12):
    config = {
        'round_trip_cost_bps': cost_bps,
        'net_milestone_bps': 80
    }
    
    evs = simulate_exits(df, mask, config, direction)
    if len(evs) == 0:
        return {"trades": 0, "mean_net_bps": 0.0, "net_win_rate": 0.0}
        
    df_evs = pd.DataFrame(evs)
    
    metrics = {
        "trades": len(df_evs),
        "mean_net_bps": float(df_evs['net_return_pct'].mean() * 10000),
        "median_net_bps": float(df_evs['net_return_pct'].median() * 10000),
        "net_win_rate": float((df_evs['net_return_pct'] > 0).mean()),
        "avg_hold": float(df_evs['holding_bars'].mean()),
        "median_hold": float(df_evs['holding_bars'].median()),
        "milestone_hit_rate": float((df_evs['state'] == 'PARTIAL').mean())
    }
    
    return metrics

def do_evaluation(df_fwd, masks, side, cost_bps=12):
    m_a = masks[f"ConfigA_{side}"]
    m_b = masks[f"ConfigB_{side}"]
    m_rej = masks[f"Rejected_{side}"]
    
    res = {
        "ConfigA": {
            "entry": calc_metrics(df_fwd, m_a, side),
            "exit": evaluate_exits(df_fwd, m_a, side, cost_bps=cost_bps)
        },
        "ConfigB": {
            "entry": calc_metrics(df_fwd, m_b, side),
            "exit": evaluate_exits(df_fwd, m_b, side, cost_bps=cost_bps)
        },
        "Rejected": {
            "entry": calc_metrics(df_fwd, m_rej, side),
            "exit": evaluate_exits(df_fwd, m_rej, side, cost_bps=cost_bps)
        }
    }
    return res

def get_folds():
    # 6mo train, 2mo test, 2mo step
    # Start: 2022-01-01
    # End of walk forward: 2023-10-31
    folds = []
    start_dt = datetime(2022, 1, 1)
    end_dt = datetime(2023, 10, 31)
    
    current_train_start = start_dt
    
    while True:
        current_train_end = current_train_start + relativedelta(months=6) - relativedelta(days=1)
        current_test_start = current_train_start + relativedelta(months=6)
        current_test_end = current_test_start + relativedelta(months=2) - relativedelta(days=1)
        
        if current_test_end > end_dt:
            # Maybe adjust last fold or break. We'll just break.
            break
            
        folds.append({
            "train_start": current_train_start.strftime("%Y-%m-%d"),
            "train_end": current_train_end.strftime("%Y-%m-%d"),
            "test_start": current_test_start.strftime("%Y-%m-%d"),
            "test_end": current_test_end.strftime("%Y-%m-%d")
        })
        
        current_train_start += relativedelta(months=2)
        
    return folds

def apply_fold(df, start, end):
    return df[(df['timestamp'] >= start) & (df['timestamp'] <= end + " 23:59:59")]

def determine_winner(train_res):
    ca_tr = train_res["ConfigA"]["exit"]["trades"]
    ca_net = train_res["ConfigA"]["exit"]["mean_net_bps"]
    
    cb_tr = train_res["ConfigB"]["exit"]["trades"]
    cb_net = train_res["ConfigB"]["exit"]["mean_net_bps"]
    
    # If sample size too small (< 10 trades), indeterminate
    if ca_tr < 10 and cb_tr < 10:
        return "INDETERMINATE"
        
    if ca_net > cb_net:
        return "WITH_VOLUME"
    elif cb_net > ca_net:
        return "WITHOUT_VOLUME"
    else:
        return "INDETERMINATE"

def analyze_symbol(sym):
    loader = ResearchDataLoader()
    print(f"Loading {sym}...")
    df_raw = loader.load_symbol(sym)
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], unit='ms')
    
    # Filter dataset for 2022-01-01 to 2023-12-31
    df_raw = df_raw[(df_raw['timestamp'] >= "2022-01-01") & (df_raw['timestamp'] <= "2023-12-31 23:59:59")]
    
    df_5m = df_raw.resample('5min', on='timestamp').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 
        'volume': 'sum', 'delta_v': 'sum'
    }).dropna().reset_index()
    
    vol_mult = 1.5 if sym == "SOLUSDT" else 1.25
    df_features = prepare_features(df_5m, vol_mult=vol_mult, vol_window=5, anti_chop_variant='A')
    df_fwd = build_forward_returns(df_features)
    
    folds = get_folds()
    
    wf_results = []
    
    for side in ["L", "S"]:
        print(f"  Doing {sym} {side} Walk-Forward...")
        fold_idx = 1
        for fold in folds:
            df_train = apply_fold(df_fwd, fold["train_start"], fold["train_end"])
            masks_train = generate_configs(df_train)
            train_eval = do_evaluation(df_train, masks_train, side)
            
            df_test = apply_fold(df_fwd, fold["test_start"], fold["test_end"])
            masks_test = generate_configs(df_test)
            test_eval = do_evaluation(df_test, masks_test, side)
            
            winner = determine_winner(train_eval)
            
            wf_results.append({
                "symbol": sym,
                "direction": side,
                "fold": fold_idx,
                "train_start": fold["train_start"],
                "train_end": fold["train_end"],
                "test_start": fold["test_start"],
                "test_end": fold["test_end"],
                "selection_winner": winner,
                "train_eval": train_eval,
                "test_eval": test_eval
            })
            fold_idx += 1
            
        print(f"  Doing {sym} {side} Holdout...")
        # Holdout
        df_holdout = apply_fold(df_fwd, "2023-11-01", "2023-12-31")
        masks_holdout = generate_configs(df_holdout)
        
        # Calculate full holdout
        holdout_eval = do_evaluation(df_holdout, masks_holdout, side)
        
        # Determine aggregate policy across folds
        with_count = sum([1 for r in wf_results if r['symbol'] == sym and r['direction'] == side and r['selection_winner'] == 'WITH_VOLUME'])
        without_count = sum([1 for r in wf_results if r['symbol'] == sym and r['direction'] == side and r['selection_winner'] == 'WITHOUT_VOLUME'])
        
        if with_count > without_count + 1:
            final_policy = "WITH_VOLUME"
        elif without_count > with_count + 1:
            final_policy = "WITHOUT_VOLUME"
        else:
            final_policy = "MIXED/INDETERMINATE"
            
        # Store holdout info
        wf_results.append({
            "symbol": sym,
            "direction": side,
            "fold": "HOLDOUT",
            "train_start": "N/A",
            "train_end": "N/A",
            "test_start": "2023-11-01",
            "test_end": "2023-12-31",
            "selection_winner": "HOLDOUT_PERIOD",
            "final_policy_determined": final_policy,
            "holdout_eval": holdout_eval
        })

    return wf_results

def main():
    all_results = []
    for sym in ["SOLUSDT", "ETHUSDT"]:
        sym_res = analyze_symbol(sym)
        all_results.extend(sym_res)
        
    with open("research/experiments/PHASE_SYMBOL_DIRECTION_VOLUME_POLICY_V1/volume_policy_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
        
    # Also save a CSV summary
    csv_rows = []
    for r in all_results:
        if r["fold"] != "HOLDOUT":
            csv_rows.append({
                "Symbol": r["symbol"],
                "Direction": r["direction"],
                "Fold": r["fold"],
                "Train": f"{r['train_start']} to {r['train_end']}",
                "Test": f"{r['test_start']} to {r['test_end']}",
                "Winner": r["selection_winner"],
                "Train_ConfigA_Net": r["train_eval"]["ConfigA"]["exit"]["mean_net_bps"],
                "Train_ConfigB_Net": r["train_eval"]["ConfigB"]["exit"]["mean_net_bps"],
                "Test_ConfigA_Net": r["test_eval"]["ConfigA"]["exit"]["mean_net_bps"],
                "Test_ConfigB_Net": r["test_eval"]["ConfigB"]["exit"]["mean_net_bps"],
            })
        else:
            csv_rows.append({
                "Symbol": r["symbol"],
                "Direction": r["direction"],
                "Fold": "HOLDOUT",
                "Train": "N/A",
                "Test": f"{r['test_start']} to {r['test_end']}",
                "Winner": r.get("final_policy_determined", "N/A"),
                "Train_ConfigA_Net": None,
                "Train_ConfigB_Net": None,
                "Test_ConfigA_Net": r["holdout_eval"]["ConfigA"]["exit"]["mean_net_bps"],
                "Test_ConfigB_Net": r["holdout_eval"]["ConfigB"]["exit"]["mean_net_bps"],
            })
            
    df_csv = pd.DataFrame(csv_rows)
    df_csv.to_csv("research/experiments/PHASE_SYMBOL_DIRECTION_VOLUME_POLICY_V1/volume_policy_walk_forward.csv", index=False)
    print("Done")

if __name__ == "__main__":
    main()
