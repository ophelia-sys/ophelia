import os
import json
import pandas as pd
import numpy as np

# Adjust PYTHONPATH so we can import internal modules
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from research.pipeline.data_loader import ResearchDataLoader
from indicators.anti_chop import (
    calculate_er, calculate_nes, calculate_nslope, 
    calculate_bbs, calculate_rvol, calculate_natr, 
    calculate_macd, calculate_mrs
)
from research.experiments.vwap_supertrend.indicators import calc_session_vwap, calc_supertrend
from indicators.ema import EMA

SYMBOLS = ["SOLUSDT", "ETHUSDT"]
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(RESULTS_DIR, exist_ok=True)

def apply_anti_chop(df: pd.DataFrame, variant: str = 'A') -> pd.DataFrame:
    """
    Applies the anti_chop logic natively to the dataframe.
    Variant A: Uses the native default parameter values (e.g., 10 bars = 50m).
    Variant B: Uses time-equivalent parameter values (e.g., 10 mins = 2 bars).
    """
    df = df.copy()
    if variant == 'A':
        p_er = 10
        p_ema_fast = 9
        p_ema_slow = 21
        p_ema_200 = 200
        p_atr = 14
        p_nslope_lookback = 3
        p_bbs = 20
        p_bbs_base = 50
        p_rvol = 20
        p_macd = (12, 26, 9)
    elif variant == 'B':
        p_er = max(2, 10 // 5)
        p_ema_fast = max(2, 9 // 5)
        p_ema_slow = max(2, 21 // 5)
        p_ema_200 = max(2, 200 // 5)
        p_atr = max(2, 14 // 5)
        p_nslope_lookback = max(1, 3 // 5)
        p_bbs = max(2, 20 // 5)
        p_bbs_base = max(2, 50 // 5)
        p_rvol = max(2, 20 // 5)
        p_macd = (max(2, 12 // 5), max(2, 26 // 5), max(2, 9 // 5))
    else:
        raise ValueError("Variant must be 'A' or 'B'")

    df["ema9"] = EMA.calculate(df, p_ema_fast)
    df["ema21"] = EMA.calculate(df, p_ema_slow)
    df["ema200"] = EMA.calculate(df, p_ema_200)
    
    df["er10"] = calculate_er(df, p_er)
    df["nes"] = calculate_nes(df, p_ema_fast, p_ema_slow, p_atr)
    df["nslope"] = calculate_nslope(df, p_ema_slow, p_nslope_lookback, p_atr)
    df["bbs"] = calculate_bbs(df, p_bbs, 2.0, p_bbs_base)
    df["rvol20"] = calculate_rvol(df, p_rvol)
    df["natr14"] = calculate_natr(df, p_atr)
    
    macd_line, signal_line, macd_hist = calculate_macd(df, p_macd[0], p_macd[1], p_macd[2])
    df["macd_hist"] = macd_hist
    
    mrs_bullish = []
    mrs_bearish = []
    for i in range(len(df)):
        res = calculate_mrs(df, i)
        mrs_bullish.append(res['bullish_score'])
        mrs_bearish.append(res['bearish_score'])
        
    df["mrs_bullish"] = mrs_bullish
    df["mrs_bearish"] = mrs_bearish
    
    df['not_choppy_long'] = (
        (df['er10'] >= 0.50) & 
        (df['nes'].abs() >= 0.40) & 
        (df['nslope'].abs() >= 0.08) & 
        (df['bbs'] >= 0.75) & 
        (df['natr14'] >= 0.10) & 
        (df['mrs_bullish'] >= 65)
    )
    
    df['not_choppy_short'] = (
        (df['er10'] >= 0.50) & 
        (df['nes'].abs() >= 0.40) & 
        (df['nslope'].abs() >= 0.08) & 
        (df['bbs'] >= 0.75) & 
        (df['natr14'] >= 0.10) & 
        (df['mrs_bearish'] >= 65)
    )
    
    return df

def prepare_features(df_5m: pd.DataFrame, vol_mult=1.25, vol_window=5, anti_chop_variant='A') -> pd.DataFrame:
    df = df_5m.copy()
    
    if 'VWAP' not in df.columns:
        df['VWAP'] = calc_session_vwap(df)
    if 'ST_10_3.0' not in df.columns:
        df = calc_supertrend(df, length=10, factor=3.0)
    
    df['vol_sum'] = df['volume'].rolling(window=vol_window).sum()
    df['vol_sum_ma20'] = df['vol_sum'].rolling(window=20).mean()
    df['vol_expansion'] = df['vol_sum'] > (vol_mult * df['vol_sum_ma20'])
    
    df['delta_v_sum'] = df['delta_v'].rolling(window=vol_window).sum()
    df['delta_long'] = df['delta_v_sum'] > 0
    df['delta_short'] = df['delta_v_sum'] < 0
    
    df = apply_anti_chop(df, variant=anti_chop_variant)
    
    df = df.dropna().reset_index(drop=True)
    return df

def generate_signals(df: pd.DataFrame, use_vol: bool = True, use_chop: bool = True):
    prev_st_dir = df['ST_Direction'].shift(1)
    curr_st_dir = df['ST_Direction']
    
    st_flip_long = (prev_st_dir == -1) & (curr_st_dir == 1)
    st_flip_short = (prev_st_dir == 1) & (curr_st_dir == -1)
    
    close_gt_vwap = df['close'] > df['VWAP']
    close_lt_vwap = df['close'] < df['VWAP']
    
    vol_confirm_long = (df['vol_expansion'] & df['delta_long']) if use_vol else pd.Series(True, index=df.index)
    vol_confirm_short = (df['vol_expansion'] & df['delta_short']) if use_vol else pd.Series(True, index=df.index)
    
    chop_confirm_long = df['not_choppy_long'] if use_chop else pd.Series(True, index=df.index)
    chop_confirm_short = df['not_choppy_short'] if use_chop else pd.Series(True, index=df.index)
    
    long_signal = st_flip_long & close_gt_vwap & vol_confirm_long & chop_confirm_long
    short_signal = st_flip_short & close_lt_vwap & vol_confirm_short & chop_confirm_short
    
    return long_signal.values, short_signal.values

def run_simulation(df: pd.DataFrame, symbol: str, config: dict):
    df = prepare_features(df, vol_mult=config.get('vol_mult', 1.25), vol_window=config.get('vol_window', 5), anti_chop_variant=config.get('anti_chop_variant', 'A'))
    
    long_signals, short_signals = generate_signals(df, use_vol=config.get('use_vol', True), use_chop=config.get('use_chop', True))
    
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    vwaps = df['VWAP'].values
    timestamps = df['timestamp'].values
    
    gross_milestone_bps = config['net_milestone_bps'] + config['round_trip_cost_bps']
    
    state = "FLAT"
    side = 0
    entry_price = 0.0
    active_stop = 0.0
    milestone_price = 0.0
    entry_idx = 0
    trade_id = ""
    
    events = []
    mfe_val = 0.0
    mae_val = 0.0
    
    for i in range(len(df) - 1):
        current_vwap = vwaps[i]
        
        if state != "FLAT":
            bar_high = highs[i]
            bar_low = lows[i]
            bar_open = opens[i]
            
            if side == 1:
                mfe_val = max(mfe_val, bar_high)
                mae_val = min(mae_val, bar_low)
            else:
                mfe_val = min(mfe_val, bar_low)
                mae_val = max(mae_val, bar_high)
                
            hit_stop = False
            hit_milestone = False
            
            if side == 1:
                if bar_low <= active_stop:
                    hit_stop = True
                if bar_high >= milestone_price:
                    hit_milestone = True
            elif side == -1:
                if bar_high >= active_stop:
                    hit_stop = True
                if bar_low <= milestone_price:
                    hit_milestone = True
                    
            if hit_stop and hit_milestone:
                hit_milestone = False
                
            if hit_stop:
                exit_price = active_stop
                if (side == 1 and bar_open < active_stop) or (side == -1 and bar_open > active_stop):
                    exit_price = bar_open
                    
                ret_pct = (exit_price / entry_price - 1.0) * side
                mfe_pct = (mfe_val / entry_price - 1.0) * side
                mae_pct = (mae_val / entry_price - 1.0) * side
                
                events.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": "LONG" if side == 1 else "SHORT",
                    "entry_time": str(timestamps[entry_idx]),
                    "exit_time": str(timestamps[i]),
                    "holding_bars": i - entry_idx,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "gross_return_pct": float(ret_pct * 100),
                    "mfe_pct": float(mfe_pct * 100),
                    "mae_pct": float(mae_pct * 100),
                    "partial_achieved": state == "PARTIAL",
                    "exit_reason": "STOP"
                })
                state = "FLAT"
                side = 0
                
            elif hit_milestone and state == "ACTIVE":
                state = "PARTIAL"
                active_stop = entry_price
                
            if state == "PARTIAL" and not hit_stop:
                if side == 1:
                    new_stop = current_vwap * (1.0 - config['stop_bps'] / 10000.0)
                    active_stop = max(active_stop, new_stop)
                else:
                    new_stop = current_vwap * (1.0 + config['stop_bps'] / 10000.0)
                    active_stop = min(active_stop, new_stop)
                    
        if state == "FLAT":
            if long_signals[i]:
                side = 1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 - config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 + gross_milestone_bps/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"
                
            elif short_signals[i]:
                side = -1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 + config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 - gross_milestone_bps/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"
                
        else:
            if side == 1 and short_signals[i]:
                exit_price = opens[i + 1]
                ret_pct = (exit_price / entry_price - 1.0)
                mfe_pct = (mfe_val / entry_price - 1.0)
                mae_pct = (mae_val / entry_price - 1.0)
                
                events.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_time": str(timestamps[entry_idx]),
                    "exit_time": str(timestamps[i + 1]),
                    "holding_bars": (i + 1) - entry_idx,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "gross_return_pct": float(ret_pct * 100),
                    "mfe_pct": float(mfe_pct * 100),
                    "mae_pct": float(mae_pct * 100),
                    "partial_achieved": state == "PARTIAL",
                    "exit_reason": "REVERSE_SIGNAL"
                })
                
                side = -1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 + config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 - gross_milestone_bps/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"
                
            elif side == -1 and long_signals[i]:
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
                    "gross_return_pct": float(ret_pct * 100),
                    "mfe_pct": float(mfe_pct * 100),
                    "mae_pct": float(mae_pct * 100),
                    "partial_achieved": state == "PARTIAL",
                    "exit_reason": "REVERSE_SIGNAL"
                })
                
                side = 1
                state = "ACTIVE"
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = current_vwap * (1.0 - config['stop_bps']/10000.0)
                milestone_price = entry_price * (1.0 + gross_milestone_bps/10000.0)
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_{int(pd.to_datetime(timestamps[i]).timestamp())}"

    return calculate_net_returns(events, config)

def calculate_net_returns(events: list, config: dict):
    rt_cost_pct = config['round_trip_cost_bps'] / 100.0
    net_milestone_pct = config['net_milestone_bps'] / 100.0
    gross_milestone_pct = net_milestone_pct + rt_cost_pct
    
    for ev in events:
        final_leg_gross_pct = ev['gross_return_pct']
        if ev['partial_achieved']:
            true_gross_pct = (0.5 * gross_milestone_pct) + (0.5 * final_leg_gross_pct)
            ev['gross_return_pct'] = true_gross_pct
            ev['net_return_pct'] = true_gross_pct - rt_cost_pct
        else:
            ev['gross_return_pct'] = final_leg_gross_pct
            ev['net_return_pct'] = final_leg_gross_pct - rt_cost_pct
            
    return events
