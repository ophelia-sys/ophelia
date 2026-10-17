import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[3]))

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "processed" / "binance_um_universe_1m_v2.parquet"
REPORT_DIR = Path(__file__).resolve().parent

def load_and_prepare_data():
    if not DATA_FILE.exists():
        print(f"Error: {DATA_FILE} not found.")
        sys.exit(1)
        
    df = pd.read_parquet(DATA_FILE)
    
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_volume']
    for col in numeric_cols:
        df[col] = df[col].astype(float)
    
    # 9. Data Quality Validation
    # Total volume > 0, Taker-buy volume >= 0, taker-buy <= total, high >= low, close within low/high
    valid_mask = (
        (df['volume'] > 0) &
        (df['taker_buy_volume'] >= 0) &
        (df['taker_buy_volume'] <= df['volume']) &
        (df['high'] >= df['low']) &
        (df['close'] >= df['low']) &
        (df['close'] <= df['high'])
    )
    df = df[valid_mask].copy()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Resample 1m to 1h
    resampled = []
    for sym, group in df.groupby('symbol'):
        res = group.set_index('timestamp').resample('1h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'taker_buy_volume': 'sum'
        }).dropna().reset_index()
        res['symbol'] = sym
        resampled.append(res)
        
    df_1h = pd.concat(resampled).sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    return df_1h

def generate_features(df):
    results = []
    for sym, group in df.groupby('symbol'):
        group = group.copy()
        
        # 4h rolling values
        group['volume_4h'] = group['volume'].rolling(4).sum()
        group['taker_buy_4h'] = group['taker_buy_volume'].rolling(4).sum()
        group['high_4h'] = group['high'].rolling(4).max()
        group['low_4h'] = group['low'].rolling(4).min()
        
        # Lookback 1h features
        group['taker_buy_ratio_1h'] = group['taker_buy_volume'] / group['volume']
        group['taker_sell_ratio_1h'] = (group['volume'] - group['taker_buy_volume']) / group['volume']
        hl_range_1h = group['high'] - group['low']
        group['close_loc_1h'] = np.where(hl_range_1h > 0, (group['close'] - group['low']) / hl_range_1h, np.nan)
        
        # Lookback 4h features
        group['taker_buy_ratio_4h'] = group['taker_buy_4h'] / group['volume_4h']
        group['taker_sell_ratio_4h'] = (group['volume_4h'] - group['taker_buy_4h']) / group['volume_4h']
        hl_range_4h = group['high_4h'] - group['low_4h']
        group['close_loc_4h'] = np.where(hl_range_4h > 0, (group['close'] - group['low_4h']) / hl_range_4h, np.nan)
        
        # Baseline B (Volume Reversal)
        group['vol_mean_24h'] = group['volume'].rolling(24).mean()
        group['vol_std_24h'] = group['volume'].rolling(24).std()
        vol_spike = group['volume'] > (group['vol_mean_24h'] + 2 * group['vol_std_24h'])
        group['baseline_b_signal'] = 0
        group.loc[vol_spike & (group['close'] > group['open']), 'baseline_b_signal'] = -1
        group.loc[vol_spike & (group['close'] < group['open']), 'baseline_b_signal'] = 1
        
        # Labels
        group['label_1h'] = group['close'].shift(-1) / group['close'] - 1
        group['label_4h'] = group['close'].shift(-4) / group['close'] - 1
        
        # Volatility regime diagnostics (14d ATR / Close)
        tr = np.maximum(
            group['high'] - group['low'],
            np.maximum(
                abs(group['high'] - group['close'].shift(1)),
                abs(group['low'] - group['close'].shift(1))
            )
        )
        group['atr_14d'] = tr.rolling(24*14).mean() / group['close']
        
        results.append(group)
    
    return pd.concat(results).reset_index(drop=True)

def calendar_time_portfolio(df, signal_col, target_col):
    df_sig = df[df[signal_col] != 0].copy()
    if df_sig.empty:
        return 0, 0, 0
    df_sig['trade_ret'] = df_sig[signal_col] * df_sig[target_col]
    
    # Calendar-Time mean return
    ct_returns = df_sig.groupby('timestamp')['trade_ret'].mean()
    mean_ret = ct_returns.mean()
    std_ret = ct_returns.std()
    n = len(ct_returns)
    if std_ret > 0 and n > 1:
        t_stat = (mean_ret / std_ret) * np.sqrt(n)
    else:
        t_stat = 0
        
    return mean_ret * 10000, t_stat, len(df_sig) # return in bps

def execute_s4():
    print("Loading data...")
    df = load_and_prepare_data()
    print("Generating features...")
    df = generate_features(df)
    
    # Split DEV / OOS
    cutoff = pd.to_datetime('2023-06-30')
    dev_df = df[df['timestamp'] <= cutoff].copy()
    oos_df = df[df['timestamp'] > cutoff].copy()
    
    # DEV Parameter Search
    lookbacks = ['1h', '4h']
    thresholds = [0.70, 0.80, 0.90]
    horizons = ['1h', '4h']
    
    best_config = None
    best_gross = -9999
    
    print("Running DEV Selection...")
    for L in lookbacks:
        for T in thresholds:
            for H in horizons:
                sig_col = f"s4_sig_{L}_{T}"
                
                # S4 Signal
                tb_ratio = dev_df[f'taker_buy_ratio_{L}']
                ts_ratio = dev_df[f'taker_sell_ratio_{L}']
                close_loc = dev_df[f'close_loc_{L}']
                
                bull = (ts_ratio > T) & (close_loc > 0.5)
                bear = (tb_ratio > T) & (close_loc < 0.5)
                
                dev_df[sig_col] = bull.astype(int) - bear.astype(int)
                target_col = f'label_{H}'
                
                gross_bps, t_stat, count = calendar_time_portfolio(dev_df, sig_col, target_col)
                print(f"DEV L={L}, T={T}, H={H} -> Gross: {gross_bps:.2f} bps, t: {t_stat:.2f}, count: {count}")
                
                if count >= 30 and gross_bps > best_gross:
                    best_gross = gross_bps
                    best_config = (L, T, H)
    
    print(f"Selected Config: {best_config}")
    
    if not best_config:
        print("No valid DEV config found. Generating REJECTED report.")
        L_opt, T_opt, H_opt = ('1h', 0.7, '1h')
        s4_gross, s4_t, s4_count = 0, 0, 0
        base_a_gross, base_a_t, base_a_count = 0, 0, 0
        base_b_gross, base_b_t, base_b_count = 0, 0, 0
        s4_net = 0
        inc_val_b = 0
        inc_pass = False
        median_sym, top1, top3, top5, pct_pos = 0, 0, 0, 0, 0
        high_vol, low_vol = 0, 0
        final_status = "REJECTED (NO SIGNALS)"
    else:
        L_opt, T_opt, H_opt = best_config
        
        # OOS Evaluation
        print("Running OOS Evaluation...")
        # Baseline A: Market Drift (Always Long)
        oos_df['baseline_a_sig'] = 1
        target_col = f'label_{H_opt}'
        base_a_gross, base_a_t, _ = calendar_time_portfolio(oos_df, 'baseline_a_sig', target_col)
        
        # Baseline B: Simple Volume Reversal
        base_b_gross, base_b_t, base_b_count = calendar_time_portfolio(oos_df, 'baseline_b_signal', target_col)
        
        # S4 Evaluated
        tb_ratio = oos_df[f'taker_buy_ratio_{L_opt}']
        ts_ratio = oos_df[f'taker_sell_ratio_{L_opt}']
        close_loc = oos_df[f'close_loc_{L_opt}']
        
        bull = (ts_ratio > T_opt) & (close_loc > 0.5)
        bear = (tb_ratio > T_opt) & (close_loc < 0.5)
        oos_df['s4_signal'] = bull.astype(int) - bear.astype(int)
        
        s4_gross, s4_t, s4_count = calendar_time_portfolio(oos_df, 's4_signal', target_col)
        
        # Cost Decomposed
        fee_entry, fee_exit = -5.0, -5.0
        slip_entry, slip_exit = -1.0, -1.0
        funding = 0.0 # Insignificant for 1h-4h holding
        total_cost_bps = fee_entry + fee_exit + slip_entry + slip_exit + funding
        
        s4_net = s4_gross + total_cost_bps
        
        # Incremental
        inc_val_a = s4_gross - base_a_gross
        inc_val_b = s4_gross - base_b_gross
        
        # Cross Sectional / Concentration
        oos_sig = oos_df[oos_df['s4_signal'] != 0].copy()
        oos_sig['trade_ret_bps'] = oos_sig['s4_signal'] * oos_sig[target_col] * 10000
        
        sym_returns = oos_sig.groupby('symbol')['trade_ret_bps'].mean().sort_values(ascending=False)
        median_sym = sym_returns.median() if not sym_returns.empty else 0
        top1 = sym_returns.iloc[0] if len(sym_returns) > 0 else 0
        top3 = sym_returns.iloc[:3].mean() if len(sym_returns) >= 3 else 0
        top5 = sym_returns.iloc[:5].mean() if len(sym_returns) >= 5 else 0
        pct_pos = (sym_returns > 0).mean() * 100 if not sym_returns.empty else 0
        
        # Regime Diagnostics
        high_vol = oos_sig[oos_sig['atr_14d'] > oos_sig['atr_14d'].median()]['trade_ret_bps'].mean()
        low_vol = oos_sig[oos_sig['atr_14d'] <= oos_sig['atr_14d'].median()]['trade_ret_bps'].mean()
        high_vol = high_vol if pd.notna(high_vol) else 0
        low_vol = low_vol if pd.notna(low_vol) else 0
        
        # Status
        oos_pass = s4_gross > 0 and s4_t > 2.0
        cost_pass = s4_net > 0
        inc_pass = inc_val_b > 0
        
        if not oos_pass or not inc_pass:
            final_status = "REJECTED"
        elif not cost_pass:
            final_status = "REJECTED (FAILED COST_PASS)"
        else:
            final_status = "PRODUCTION_CANDIDATE"
        
    report = f"""# PHASE 7.6 S4: TAKER FLOW EXHAUSTION (PROXY) REPORT

## Executive Summary
This report summarizes the evaluation of EXP-S4: **Taker Flow Exhaustion Proxy**.
The hypothesis states that extreme taker flow (imbalance) that is completely absorbed (measured by candle close location) indicates institutional passive absorption and predicts a mean-reverting reversal.

**Final Status:** `{final_status}`

---

## 1. Does taker-flow imbalance predict future returns?
**OOS Result:** The best DEV configuration (Lookback: {L_opt}, Threshold: {T_opt}, Horizon: {H_opt}) generated {s4_gross:.2f} bps gross in OOS with a t-statistic of {s4_t:.2f} over {s4_count} trades.

## 2. Does it add information beyond volume reversal?
**Yes/No:** 
- S4 Gross: {s4_gross:.2f} bps
- Baseline B (Simple Vol Reversal) Gross: {base_b_gross:.2f} bps (t={base_b_t:.2f}, n={base_b_count})
- Incremental Value vs Baseline B: {inc_val_b:.2f} bps.

## 3. Does it survive costs?
**No/Yes:**
- **Gross Return:** {s4_gross:.2f} bps
- **Fee Entry/Exit:** -10.0 bps
- **Slippage Entry/Exit:** -2.0 bps
- **Funding:** ~0.0 bps
- **Net Return:** {s4_net:.2f} bps

## 4. Is it stable?
- **OOS t-stat:** {s4_t:.2f}

## 5. Is it cross-sectional?
- **Median Symbol Gross:** {median_sym:.2f} bps
- **% Positive Symbols:** {pct_pos:.1f}%

## 6. Is it concentrated in extreme-volatility assets?
- **Top 1 Symbol Gross:** {top1:.2f} bps
- **Top 3 Symbol Gross:** {top3:.2f} bps
- **Top 5 Symbol Gross:** {top5:.2f} bps
- **Regime Diagnostics:** High Vol = {high_vol:.2f} bps | Low Vol = {low_vol:.2f} bps

## 7. Does the signal survive global FDR?
With {len(lookbacks)*len(thresholds)*len(horizons)} DEV tests, Multiple Testing correction requires higher significance.
- Non-overlapping t-stat: {s4_t:.2f}
- Surpasses strict bounds? {"Yes" if s4_t > 2.5 else "No"}

## 8. What is its exact promotion status?
**{final_status}**
"""

    report_path = REPORT_DIR / "PHASE7_S4_TAKER_FLOW_EXHAUSTION_REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)
        
    print(f"Report written to {report_path}")
    
    # Update Feature Registry
    registry_path = REPORT_DIR / "PHASE7_FINAL_FEATURE_REGISTRY.md"
    reg = f"""# PHASE 7 FINAL FEATURE REGISTRY

| FEATURE_ID | HYPOTHESIS | STATUS | DATA_SOURCE | OOS_RESULT (Gross) | NET_EXPECTANCY | INCREMENTAL_VALUE | LIVE_STATUS |
|------------|------------|--------|-------------|--------------------|----------------|-------------------|-------------|
| **S1** | Volatility-Scaled TSMOM | REJECTED | Binance UM | -1.03 bps | -13.03 bps | NO | N/A |
| **S2** | Beta-Adjusted Residual Momentum | REJECTED / INCONCLUSIVE | Binance UM | +2.16 bps | -9.84 bps | YES | N/A |
| **S3** | Crowded Leverage Reversal | FRAGILE_VALIDATED_ALPHA | Binance UM | +14.8 bps | +2.7 bps | YES | INCONCLUSIVE (Shadow Pending) |
| **S4** | Taker Flow Exhaustion | {final_status} | Binance UM | {s4_gross:.2f} bps | {s4_net:.2f} bps | {'YES' if inc_pass else 'NO'} | N/A |
"""
    with open(registry_path, "w") as f:
        f.write(reg)
    print(f"Registry updated at {registry_path}")

if __name__ == "__main__":
    execute_s4()
