import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from numba import njit

# Adjust PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.vwap_supertrend.indicators import calc_session_vwap, _calc_rma, _calc_supertrend_core

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

def _calc_supertrend_forensic(high: np.ndarray, low: np.ndarray, close: np.ndarray, atr: np.ndarray, factor: float) -> tuple:
    n = len(close)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + factor * atr
    basic_lower = hl2 - factor * atr
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    direction = np.ones(n, dtype=np.int32)
    supertrend = np.full(n, np.nan)
    
    for i in range(n):
        if not np.isnan(basic_upper[i]):
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            direction[i] = 1
            supertrend[i] = final_lower[i]
            start_idx = i + 1
            break
    else:
        return supertrend, direction, basic_upper, basic_lower, final_upper, final_lower
        
    for i in range(start_idx, n):
        if np.isnan(final_upper[i-1]):
            final_upper[i] = basic_upper[i]
        elif basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        if np.isnan(final_lower[i-1]):
            final_lower[i] = basic_lower[i]
        elif basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        if np.isnan(supertrend[i-1]):
            direction[i] = 1
        elif direction[i-1] == 1 and close[i] < final_lower[i]:
            direction[i] = -1
        elif direction[i-1] == -1 and close[i] > final_upper[i]:
            direction[i] = 1
        else:
            direction[i] = direction[i-1]
            
        if direction[i] == 1:
            supertrend[i] = final_lower[i]
        else:
            supertrend[i] = final_upper[i]
            
    return supertrend, direction, basic_upper, basic_lower, final_upper, final_lower

def calc_supertrend_forensic(df: pd.DataFrame, length: int = 10, factor: float = 3.0) -> pd.DataFrame:
    df = df.copy()
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    prev_close = df['close'].shift(1).values
    
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    with np.errstate(invalid='ignore'):
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]
    
    atr = _calc_rma(tr, length)
    supertrend, direction, bu, bl, fu, fl = _calc_supertrend_forensic(high, low, close, atr, factor)
    
    df['TR'] = tr
    df['ATR'] = atr
    df['Basic_Upper'] = bu
    df['Basic_Lower'] = bl
    df['Final_Upper'] = fu
    df['Final_Lower'] = fl
    df['Supertrend'] = supertrend
    df['ST_Direction'] = direction
    df['Prev_ST_Direction'] = df['ST_Direction'].shift(1)
    
    # Mapping to Pine: internal 1 (bullish) -> -1, internal -1 (bearish) -> 1
    df['Pine_Direction'] = -df['ST_Direction']
    return df

def run_backtest(df: pd.DataFrame, symbol: str) -> tuple:
    print(f"[{symbol}] Processing...")
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    df['VWAP'] = calc_session_vwap(df)
    df = calc_supertrend_forensic(df, length=10, factor=3.0)
    
    df['Typical_Price'] = (df['high'] + df['low'] + df['close']) / 3.0
    
    # Calculate VWAP internals for forensics
    session_key = df['timestamp'].dt.date
    df['PV'] = df['Typical_Price'] * df['volume']
    df['Cum_PV'] = df['PV'].groupby(session_key).cumsum()
    df['Cum_V'] = df['volume'].groupby(session_key).cumsum()
    
    # Signal conditions (User Requested Deterministic Variant)
    st_flip_long = (df['Prev_ST_Direction'] == -1) & (df['ST_Direction'] == 1)
    st_flip_short = (df['Prev_ST_Direction'] == 1) & (df['ST_Direction'] == -1)
    
    close_gt_vwap = df['close'] > df['VWAP']
    close_lt_vwap = df['close'] < df['VWAP']
    
    df['Signal_Long'] = st_flip_long & close_gt_vwap
    df['Signal_Short'] = st_flip_short & close_lt_vwap
    
    # Run loop
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    vwaps = df['VWAP'].values
    timestamps = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').values
    sig_longs = df['Signal_Long'].values
    sig_shorts = df['Signal_Short'].values
    
    trades = []
    signals_log = []
    
    state = "FLAT"
    side = 0
    entry_price = 0.0
    active_stop = 0.0
    target_price = 0.0
    entry_idx = 0
    trade_id = ""
    signal_vwap = 0.0
    signal_timestamp = ""
    signal_idx = 0
    
    # MFE / MAE using closes
    mfe_val = 0.0
    mae_val = 0.0
    
    for i in range(1, len(df) - 1): # stop 1 before end to allow entry on i+1
        # Log all genuine signals for forensic output
        if sig_longs[i] or sig_shorts[i]:
            signals_log.append({
                "symbol": symbol,
                "direction": "LONG" if sig_longs[i] else "SHORT",
                "timestamp": timestamps[i],
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "VWAP": vwaps[i],
                "Supertrend": df['Supertrend'].iloc[i],
                "prev_ST_dir": df['Prev_ST_Direction'].iloc[i],
                "curr_ST_dir": df['ST_Direction'].iloc[i],
                "pine_dir": df['Pine_Direction'].iloc[i],
                "ATR": df['ATR'].iloc[i],
                "close_minus_vwap": closes[i] - vwaps[i],
                "close_minus_st": closes[i] - df['Supertrend'].iloc[i],
                "next_bar_timestamp": timestamps[i+1],
                "next_bar_entry_price": opens[i+1]
            })
            
        if state != "FLAT":
            bar_close = closes[i]
            
            if side == 1:
                mfe_val = max(mfe_val, bar_close)
                mae_val = min(mae_val, bar_close)
            else:
                mfe_val = min(mfe_val, bar_close)
                mae_val = max(mae_val, bar_close)
                
            hit_target = False
            hit_stop = False
            
            if side == 1:
                if bar_close >= target_price:
                    hit_target = True
                elif bar_close <= active_stop:
                    hit_stop = True
            elif side == -1:
                if bar_close <= target_price:
                    hit_target = True
                elif bar_close >= active_stop:
                    hit_stop = True
                    
            if hit_target or hit_stop:
                exit_price = bar_close
                exit_reason = "TARGET" if hit_target else "STOP"
                
                ret_pct = (exit_price / entry_price - 1.0) * side
                
                trades.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": "LONG" if side == 1 else "SHORT",
                    "signal_timestamp": signal_timestamp,
                    "entry_timestamp": timestamps[entry_idx],
                    "entry_price": float(entry_price),
                    "signal_vwap": float(signal_vwap),
                    "initial_stop": float(active_stop),
                    "target_price": float(target_price),
                    "exit_timestamp": timestamps[i],
                    "exit_price": float(exit_price),
                    "exit_reason": exit_reason,
                    "exit_candle_open": float(opens[i]),
                    "exit_candle_high": float(highs[i]),
                    "exit_candle_low": float(lows[i]),
                    "exit_candle_close": float(closes[i]),
                    "gross_return_bps": float(ret_pct * 10000.0),
                    "holding_bars": i - entry_idx,
                    "holding_minutes": (i - entry_idx) * 5,
                    "mfe_close": mfe_val,
                    "mae_close": mae_val
                })
                state = "FLAT"
                side = 0
                
        if state == "FLAT":
            if sig_longs[i]:
                side = 1
                state = "ACTIVE"
                signal_timestamp = timestamps[i]
                signal_vwap = vwaps[i]
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = signal_vwap * (1.0 - 1.0/10000.0)
                target_price = entry_price * 1.008
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_L_{int(pd.to_datetime(signal_timestamp).timestamp())}"
                
            elif sig_shorts[i]:
                side = -1
                state = "ACTIVE"
                signal_timestamp = timestamps[i]
                signal_vwap = vwaps[i]
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = signal_vwap * (1.0 + 1.0/10000.0)
                target_price = entry_price * 0.992
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"{symbol}_S_{int(pd.to_datetime(signal_timestamp).timestamp())}"
                
    return trades, signals_log, df

def analyze_trades(trades: list, symbol: str, direction: str):
    f_trades = [t for t in trades if t['symbol'] == symbol and t['direction'] == direction]
    n = len(f_trades)
    if n == 0:
        return {}
        
    targets = [t for t in f_trades if t['exit_reason'] == "TARGET"]
    stops = [t for t in f_trades if t['exit_reason'] == "STOP"]
    
    ret = [t['gross_return_bps'] for t in f_trades]
    holds = [t['holding_minutes'] for t in f_trades]
    
    target_rate = len(targets) / n if n > 0 else 0
    
    # Close-based distributions
    dists = {
        '50': 0, '60': 0, '70': 0, '80': 0, '90': 0, '100': 0
    }
    
    for t in f_trades:
        side_mult = 1 if direction == "LONG" else -1
        max_favorable_pct = (t['mfe_close'] / t['entry_price'] - 1.0) * side_mult * 100.0
        
        if max_favorable_pct >= 0.50: dists['50'] += 1
        if max_favorable_pct >= 0.60: dists['60'] += 1
        if max_favorable_pct >= 0.70: dists['70'] += 1
        if max_favorable_pct >= 0.80: dists['80'] += 1
        if max_favorable_pct >= 0.90: dists['90'] += 1
        if max_favorable_pct >= 1.00: dists['100'] += 1
        
    return {
        "symbol": symbol,
        "direction": direction,
        "total_trades": n,
        "targets": len(targets),
        "stops": len(stops),
        "target_rate": target_rate,
        "mean_bps": float(np.mean(ret)),
        "median_bps": float(np.median(ret)),
        "mean_hold_m": float(np.mean(holds)),
        "median_hold_m": float(np.median(holds)),
        "distribution_pct": {k: (v/n)*100 for k,v in dists.items()}
    }

def calculate_costs(trades, costs=[0, 8, 12, 16, 20]):
    out = {}
    for c in costs:
        net = [t['gross_return_bps'] - c for t in trades]
        out[str(c)] = float(np.mean(net)) if len(net) > 0 else 0.0
    return out

def main():
    loader = ResearchDataLoader()
    
    all_trades = []
    all_signals = []
    
    sym_dfs = {}
    
    for symbol in ["SOLUSDT", "ETHUSDT"]:
        df = loader.load_symbol(symbol)
        print(f"{symbol} bounds: {df['timestamp'].min()} to {df['timestamp'].max()}, N={len(df)}")
        
        trades, signals, df_computed = run_backtest(df, symbol)
        all_trades.extend(trades)
        all_signals.extend(signals)
        sym_dfs[symbol] = df_computed
        
    pd.DataFrame(all_trades).to_csv(os.path.join(RESULTS_DIR, 'VWAP_SUPERTREND_NO_VOLUME_ALL_TRADES.csv'), index=False)
    pd.DataFrame(all_signals).to_csv(os.path.join(RESULTS_DIR, 'VWAP_SUPERTREND_NO_VOLUME_SIGNALS.csv'), index=False)
    
    stats = []
    for sym in ["SOLUSDT", "ETHUSDT"]:
        for d in ["LONG", "SHORT"]:
            s = analyze_trades(all_trades, sym, d)
            f_trades = [t for t in all_trades if t['symbol'] == sym and t['direction'] == d]
            s['costs_bps'] = calculate_costs(f_trades)
            stats.append(s)
            
    with open(os.path.join(RESULTS_DIR, 'VWAP_SUPERTREND_NO_VOLUME_RESULTS.json'), 'w') as f:
        json.dump(stats, f, indent=4)
        
    # Manual Validation Set
    val_set = []
    for sym in ["SOLUSDT", "ETHUSDT"]:
        for d in ["LONG", "SHORT"]:
            f_sigs = [s for s in all_signals if s['symbol'] == sym and s['direction'] == d]
            sample_sigs = pd.DataFrame(f_sigs).sample(n=min(10, len(f_sigs)), random_state=42).to_dict('records')
            
            for sig in sample_sigs:
                ts = sig['timestamp']
                idx = sym_dfs[sym].index[sym_dfs[sym]['timestamp'] == ts].tolist()[0]
                row = sym_dfs[sym].iloc[idx]
                
                val_set.append({
                    "symbol": sym,
                    "direction": d,
                    "timestamp": ts,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close']),
                    "volume": float(row['volume']),
                    "typical_price": float(row['Typical_Price']),
                    "cum_pv": float(row['Cum_PV']),
                    "cum_v": float(row['Cum_V']),
                    "vwap": float(row['VWAP']),
                    "tr": float(row['TR']),
                    "atr": float(row['ATR']),
                    "basic_upper": float(row['Basic_Upper']),
                    "basic_lower": float(row['Basic_Lower']),
                    "final_upper": float(row['Final_Upper']),
                    "final_lower": float(row['Final_Lower']),
                    "supertrend": float(row['Supertrend']),
                    "direction_internal": int(row['ST_Direction']),
                    "direction_pine": int(row['Pine_Direction']),
                    "entry_price": float(sig['next_bar_entry_price'])
                })
                
    with open(os.path.join(RESULTS_DIR, 'VWAP_SUPERTREND_NO_VOLUME_VALIDATION.json'), 'w') as f:
        json.dump(val_set, f, indent=4)
        
    print("Done")

if __name__ == "__main__":
    main()
