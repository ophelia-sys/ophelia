import os
import sys
import json
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from numba import njit

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.vwap_supertrend.indicators import calc_session_vwap, _calc_rma, _calc_supertrend_core

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

def fetch_binance_futures_klines(symbol, interval, start_time_ms, end_time_ms):
    url = "https://fapi.binance.com/fapi/v1/klines"
    all_klines = []
    current_start = start_time_ms
    
    while current_start < end_time_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_time_ms,
            "limit": 1500
        }
        res = requests.get(url, params=params)
        if res.status_code != 200:
            raise Exception(f"Failed to fetch data: {res.text}")
            
        data = res.json()
        if not data:
            break
            
        all_klines.extend(data)
        current_start = data[-1][0] + 1
        time.sleep(0.1) # basic rate limit
        
    df = pd.DataFrame(all_klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit='ms')
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

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
    df['Supertrend'] = supertrend
    df['ST_Direction'] = direction
    df['Prev_ST_Direction'] = df['ST_Direction'].shift(1)
    df['Pine_Direction'] = -df['ST_Direction']
    return df

def run_backtest(df_5m: pd.DataFrame, df_1h: pd.DataFrame, strategy_type: str) -> tuple:
    # Causal Alignment Setup
    # Evaluate 5m candle at its close
    df_5m = df_5m.copy()
    df_5m['evaluation_time'] = df_5m['timestamp'] + pd.Timedelta(minutes=5)
    
    df_1h = df_1h.copy()
    df_1h['completed_at'] = df_1h['timestamp'] + pd.Timedelta(hours=1)
    df_1h['sma200'] = df_1h['close'].rolling(window=200).mean()
    
    df_1h['close_gt_sma'] = df_1h['close'] > df_1h['sma200']
    df_1h['close_lt_sma'] = df_1h['close'] < df_1h['sma200']
    
    df_1h['long_regime_valid'] = df_1h['close_gt_sma'] & df_1h['close_gt_sma'].shift(1)
    df_1h['short_regime_valid'] = df_1h['close_lt_sma'] & df_1h['close_lt_sma'].shift(1)
    
    # Store references for forensic output
    df_1h_for_merge = df_1h[['completed_at', 'timestamp', 'close', 'sma200', 'long_regime_valid', 'short_regime_valid']].copy()
    df_1h_for_merge.rename(columns={
        'timestamp': '1h_timestamp', 
        'close': '1h_close',
        'sma200': '1h_sma200'
    }, inplace=True)
    
    # Shift to get the previous 1h candle as well
    df_1h_for_merge['1h_timestamp_prev'] = df_1h_for_merge['1h_timestamp'].shift(1)
    df_1h_for_merge['1h_close_prev'] = df_1h_for_merge['1h_close'].shift(1)
    df_1h_for_merge['1h_sma200_prev'] = df_1h_for_merge['1h_sma200'].shift(1)
    
    df = pd.merge_asof(df_5m, df_1h_for_merge, left_on='evaluation_time', right_on='completed_at', direction='backward')
    
    df['long_regime_valid'] = df['long_regime_valid'].fillna(False).astype(bool)
    df['short_regime_valid'] = df['short_regime_valid'].fillna(False).astype(bool)
    
    df['VWAP'] = calc_session_vwap(df)
    df = calc_supertrend_forensic(df, length=10, factor=3.0)
    
    st_flip_long = (df['Prev_ST_Direction'] == -1) & (df['ST_Direction'] == 1)
    st_flip_short = (df['Prev_ST_Direction'] == 1) & (df['ST_Direction'] == -1)
    
    close_gt_vwap = df['close'] > df['VWAP']
    close_lt_vwap = df['close'] < df['VWAP']
    
    # Restrict to August 1 -> August 21
    mask_eval = (df['timestamp'] >= pd.to_datetime('2026-08-01 00:00:00')) & (df['timestamp'] <= pd.to_datetime('2026-08-21 23:55:00'))
    df['in_window'] = mask_eval
    
    if strategy_type == "BASE":
        df['Signal_Long'] = st_flip_long & close_gt_vwap & df['in_window']
        df['Signal_Short'] = st_flip_short & close_lt_vwap & df['in_window']
    elif strategy_type == "FILTERED":
        df['Signal_Long'] = st_flip_long & close_gt_vwap & df['long_regime_valid'] & df['in_window']
        df['Signal_Short'] = st_flip_short & close_lt_vwap & df['short_regime_valid'] & df['in_window']
    elif strategy_type == "DIAGNOSTIC":
        # Purely trade the regime flips, ignore VWAP/ST
        df['Signal_Long'] = df['long_regime_valid'] & (~df['long_regime_valid'].shift(1).fillna(False)) & df['in_window']
        df['Signal_Short'] = df['short_regime_valid'] & (~df['short_regime_valid'].shift(1).fillna(False)) & df['in_window']
        
    # Log rejected signals
    df['Rejected_Long'] = False
    df['Rejected_Short'] = False
    if strategy_type == "FILTERED":
        df['Rejected_Long'] = st_flip_long & close_gt_vwap & (~df['long_regime_valid']) & df['in_window']
        df['Rejected_Short'] = st_flip_short & close_lt_vwap & (~df['short_regime_valid']) & df['in_window']

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
    rejected_log = []
    
    state = "FLAT"
    side = 0
    entry_price = 0.0
    active_stop = 0.0
    target_price = 0.0
    entry_idx = 0
    trade_id = ""
    signal_vwap = 0.0
    signal_timestamp = ""
    
    mfe_val = 0.0
    mae_val = 0.0
    
    for i in range(1, len(df) - 1):
        if not df['in_window'].iloc[i]:
            continue
            
        if df['Rejected_Long'].iloc[i] or df['Rejected_Short'].iloc[i]:
            rejected_log.append({
                "timestamp": timestamps[i],
                "direction": "LONG" if df['Rejected_Long'].iloc[i] else "SHORT",
                "VWAP": float(vwaps[i]),
                "Supertrend": float(df['Supertrend'].iloc[i]),
                "1h_close": float(df['1h_close'].iloc[i]),
                "1h_sma200": float(df['1h_sma200'].iloc[i]),
                "reason": "Regime Failed (Missing two consecutive 1H closes above/below SMA200)"
            })
            
        if sig_longs[i] or sig_shorts[i]:
            signals_log.append({
                "trade_id": f"SOLUSDT_{'L' if sig_longs[i] else 'S'}_{int(df['timestamp'].iloc[i].timestamp())}",
                "direction": "LONG" if sig_longs[i] else "SHORT",
                "signal_timestamp": timestamps[i],
                "signal_open": opens[i],
                "signal_high": highs[i],
                "signal_low": lows[i],
                "signal_close": closes[i],
                "signal_vwap": vwaps[i],
                "supertrend": df['Supertrend'].iloc[i],
                "previous_ST": df['Prev_ST_Direction'].iloc[i],
                "current_ST": df['ST_Direction'].iloc[i],
                "1h_candle_1_timestamp": str(df['1h_timestamp_prev'].iloc[i]),
                "1h_close_1": df['1h_close_prev'].iloc[i],
                "1h_sma200_1": df['1h_sma200_prev'].iloc[i],
                "1h_candle_2_timestamp": str(df['1h_timestamp'].iloc[i]),
                "1h_close_2": df['1h_close'].iloc[i],
                "1h_sma200_2": df['1h_sma200'].iloc[i],
                "regime_status": "VALID",
                "entry_timestamp": timestamps[i+1],
                "entry_price": opens[i+1],
                "stop_price": vwaps[i] * (1.0 - 1.0/10000.0) if sig_longs[i] else vwaps[i] * (1.0 + 1.0/10000.0),
                "target_price": opens[i+1] * 1.007 if sig_longs[i] else opens[i+1] * 0.993
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
                if bar_close >= target_price: hit_target = True
                elif bar_close <= active_stop: hit_stop = True
            elif side == -1:
                if bar_close <= target_price: hit_target = True
                elif bar_close >= active_stop: hit_stop = True
                
            if hit_target or hit_stop:
                exit_price = bar_close
                exit_reason = "TARGET" if hit_target else "STOP"
                ret_pct = (exit_price / entry_price - 1.0) * side
                
                trades.append({
                    "trade_id": trade_id,
                    "direction": "LONG" if side == 1 else "SHORT",
                    "signal_timestamp": signal_timestamp,
                    "entry_timestamp": timestamps[entry_idx],
                    "entry_price": float(entry_price),
                    "signal_vwap": float(signal_vwap),
                    "supertrend": float(df['Supertrend'].iloc[entry_idx-1]),
                    "previous_ST": float(df['Prev_ST_Direction'].iloc[entry_idx-1]),
                    "current_ST": float(df['ST_Direction'].iloc[entry_idx-1]),
                    "1h_regime": "LONG ENABLED" if side == 1 else "SHORT ENABLED",
                    "first_qualifying_1h_close_timestamp": str(df['1h_timestamp_prev'].iloc[entry_idx-1]),
                    "second_qualifying_1h_close_timestamp": str(df['1h_timestamp'].iloc[entry_idx-1]),
                    "first_1h_close": float(df['1h_close_prev'].iloc[entry_idx-1]),
                    "second_1h_close": float(df['1h_close'].iloc[entry_idx-1]),
                    "first_200MA": float(df['1h_sma200_prev'].iloc[entry_idx-1]),
                    "second_200MA": float(df['1h_sma200'].iloc[entry_idx-1]),
                    "stop_price": float(active_stop),
                    "target_price": float(target_price),
                    "exit_timestamp": timestamps[i],
                    "exit_price": float(exit_price),
                    "exit_reason": exit_reason,
                    "holding_5m_bars": i - entry_idx,
                    "holding_minutes": (i - entry_idx) * 5,
                    "gross_return_bps": float(ret_pct * 10000.0),
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
                target_price = entry_price * 1.007
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"SOLUSDT_L_{int(df['timestamp'].iloc[i].timestamp())}"
                
            elif sig_shorts[i]:
                side = -1
                state = "ACTIVE"
                signal_timestamp = timestamps[i]
                signal_vwap = vwaps[i]
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                active_stop = signal_vwap * (1.0 + 1.0/10000.0)
                target_price = entry_price * 0.993
                mfe_val = entry_price
                mae_val = entry_price
                trade_id = f"SOLUSDT_S_{int(df['timestamp'].iloc[i].timestamp())}"
                
    return trades, signals_log, rejected_log, df

def analyze_trades(trades: list, direction: str):
    f_trades = [t for t in trades if t['direction'] == direction]
    n = len(f_trades)
    if n == 0:
        return {}
        
    targets = [t for t in f_trades if t['exit_reason'] == "TARGET"]
    stops = [t for t in f_trades if t['exit_reason'] == "STOP"]
    
    ret = [t['gross_return_bps'] for t in f_trades]
    holds = [t['holding_minutes'] for t in f_trades]
    
    mfe = [(t['mfe_close'] / t['entry_price'] - 1.0) * (1 if direction == "LONG" else -1) * 100 for t in f_trades]
    mae = [(t['mae_close'] / t['entry_price'] - 1.0) * (1 if direction == "LONG" else -1) * 100 for t in f_trades]
    
    # Calculate drawdown & streaks
    cum_ret = np.cumsum(ret)
    peak = np.maximum.accumulate(cum_ret)
    drawdowns = peak - cum_ret
    max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0
    
    wins = [1 if t['exit_reason'] == "TARGET" else 0 for t in f_trades]
    loss = [1 if t['exit_reason'] == "STOP" else 0 for t in f_trades]
    
    def max_streak(arr):
        max_s = 0; s = 0
        for x in arr:
            if x == 1: s += 1; max_s = max(max_s, s)
            else: s = 0
        return max_s
    
    return {
        "direction": direction,
        "total_trades": n,
        "targets": len(targets),
        "stops": len(stops),
        "target_rate": len(targets) / n,
        "stop_rate": len(stops) / n,
        "mean_bps": float(np.mean(ret)),
        "median_bps": float(np.median(ret)),
        "mean_mfe_pct": float(np.mean(mfe)),
        "mean_mae_pct": float(np.mean(mae)),
        "mean_hold_m": float(np.mean(holds)),
        "median_hold_m": float(np.median(holds)),
        "max_drawdown_bps": max_drawdown,
        "longest_win_streak": max_streak(wins),
        "longest_loss_streak": max_streak(loss)
    }

def main():
    print("Fetching Binance Data...")
    
    start_ts = int(pd.to_datetime("2026-07-10 00:00:00").timestamp() * 1000)
    end_ts = int(pd.to_datetime("2026-08-22 00:00:00").timestamp() * 1000)
    
    df_5m = fetch_binance_futures_klines("SOLUSDT", "5m", start_ts, end_ts)
    df_1h = fetch_binance_futures_klines("SOLUSDT", "1h", start_ts, end_ts)
    
    print(f"5m Gaps Check: Expected {int((end_ts - start_ts)/300000)}, Got {len(df_5m)}")
    print(f"1h Gaps Check: Expected {int((end_ts - start_ts)/3600000)}, Got {len(df_1h)}")
    
    with open(os.path.join(RESULTS_DIR, 'data_quality_report.json'), 'w') as f:
        json.dump({
            "5m_count": len(df_5m),
            "1h_count": len(df_1h),
            "first_5m": str(df_5m['timestamp'].min()),
            "last_5m": str(df_5m['timestamp'].max()),
            "first_1h": str(df_1h['timestamp'].min()),
            "last_1h": str(df_1h['timestamp'].max())
        }, f, indent=4)
        
    print("Running Baseline (Pure)...")
    trades_base, sigs_base, _, _ = run_backtest(df_5m, df_1h, "BASE")
    print("Running Filtered (VWAP + ST + 200MA)...")
    trades_filt, sigs_filt, rej_filt, df_merged = run_backtest(df_5m, df_1h, "FILTERED")
    print("Running Diagnostic (Regime Only)...")
    trades_diag, _, _, _ = run_backtest(df_5m, df_1h, "DIAGNOSTIC")
    
    # Save CSVs for Filtered
    pd.DataFrame(trades_filt).to_csv(os.path.join(RESULTS_DIR, 'SOL_VWAP_SUPERTREND_200MA_ALL_TRADES.csv'), index=False)
    pd.DataFrame(sigs_filt).to_csv(os.path.join(RESULTS_DIR, 'SOL_VWAP_SUPERTREND_200MA_SIGNALS.csv'), index=False)
    pd.DataFrame(rej_filt).to_csv(os.path.join(RESULTS_DIR, 'SOL_VWAP_SUPERTREND_200MA_REJECTED_SIGNALS.csv'), index=False)
    
    stats = {
        "BASE": [analyze_trades(trades_base, "LONG"), analyze_trades(trades_base, "SHORT")],
        "FILTERED": [analyze_trades(trades_filt, "LONG"), analyze_trades(trades_filt, "SHORT")],
        "DIAGNOSTIC": [analyze_trades(trades_diag, "LONG"), analyze_trades(trades_diag, "SHORT")]
    }
    
    with open(os.path.join(RESULTS_DIR, 'SOL_VWAP_SUPERTREND_200MA_RESULTS.json'), 'w') as f:
        json.dump(stats, f, indent=4)
        
    # Manual Validation Set
    val_set = []
    for d in ["LONG", "SHORT"]:
        f_sigs = [s for s in sigs_filt if s['direction'] == d]
        sample_sigs = pd.DataFrame(f_sigs).sample(n=min(10, len(f_sigs)), random_state=42).to_dict('records')
        val_set.extend(sample_sigs)
        
    with open(os.path.join(RESULTS_DIR, 'VWAP_SUPERTREND_200MA_VALIDATION.json'), 'w') as f:
        json.dump(val_set, f, indent=4)
        
    print("Done")

if __name__ == "__main__":
    main()
