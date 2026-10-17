import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[3]))

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "processed" / "binance_um_universe_1m_v2.parquet"
REPORT_DIR = Path(__file__).resolve().parent
EPSILON = 1e-8

def load_and_resample():
    if not DATA_FILE.exists():
        print(f"Error: {DATA_FILE} not found.")
        sys.exit(1)
        
    df = pd.read_parquet(DATA_FILE)
    
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_volume']
    for col in numeric_cols:
        df[col] = df[col].astype(float)
        
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # 2. Validation
    valid_mask = (
        (df['volume'] > 0) &
        (df['taker_buy_volume'] >= 0) &
        (df['taker_buy_volume'] <= df['volume']) &
        (df['high'] >= df['low']) &
        (df['close'] >= df['low']) &
        (df['close'] <= df['high'])
    )
    df = df[valid_mask].copy()
    
    resampled_dict = {}
    for W in ['5min', '15min']:
        print(f"Resampling to {W}...")
        res_list = []
        for sym, group in df.groupby('symbol'):
            res = group.set_index('timestamp').resample(W).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'taker_buy_volume': 'sum'
            }).dropna().reset_index()
            res['symbol'] = sym
            res_list.append(res)
            
        df_w = pd.concat(res_list).sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        resampled_dict[W] = df_w
        
    return resampled_dict

def generate_features(df_w, W):
    print(f"Generating features for {W}...")
    results = []
    
    # Define 24h window size
    if W == '5min':
        roll_window = 12 * 24 # 288 bars
        shift_15m, shift_30m, shift_1h = 3, 6, 12
    else: # 15min
        roll_window = 4 * 24 # 96 bars
        shift_15m, shift_30m, shift_1h = 1, 2, 4
        
    for sym, group in df_w.groupby('symbol'):
        group = group.copy()
        
        group['taker_sell_volume'] = group['volume'] - group['taker_buy_volume']
        group['signed_flow'] = (group['taker_buy_volume'] - group['taker_sell_volume']) / group['volume']
        
        # Z_Flow
        roll_mean = group['signed_flow'].rolling(roll_window).mean()
        roll_std = group['signed_flow'].rolling(roll_window).std()
        group['z_flow'] = np.where(roll_std > EPSILON, (group['signed_flow'] - roll_mean) / roll_std, np.nan)
        
        # Price Response
        group['r_w'] = np.log(group['close'] / group['close'].shift(1))
        sigma_w = group['r_w'].rolling(roll_window).std()
        group['r_norm'] = np.where(sigma_w > EPSILON, group['r_w'] / sigma_w, np.nan)
        
        # Labels (Log returns)
        group['label_15m'] = np.log(group['close'].shift(-shift_15m) / group['close'])
        group['label_30m'] = np.log(group['close'].shift(-shift_30m) / group['close'])
        group['label_1h'] = np.log(group['close'].shift(-shift_1h) / group['close'])
        
        # Vol diagnostic
        tr = np.maximum(
            group['high'] - group['low'],
            np.maximum(
                abs(group['high'] - group['close'].shift(1)),
                abs(group['low'] - group['close'].shift(1))
            )
        )
        group['atr_vol'] = tr.rolling(roll_window).mean() / group['close']
        
        results.append(group)
        
    return pd.concat(results).reset_index(drop=True)

def calendar_time_portfolio(df, signal_col, target_col):
    df_sig = df[df[signal_col] != 0].copy()
    if df_sig.empty:
        return 0.0, 0.0, 0
    df_sig['trade_ret'] = df_sig[signal_col] * (np.exp(df_sig[target_col]) - 1)
    
    ct_returns = df_sig.groupby('timestamp')['trade_ret'].mean()
    mean_ret = ct_returns.mean()
    std_ret = ct_returns.std()
    n = len(ct_returns)
    if std_ret > 0 and n > 1:
        t_stat = (mean_ret / std_ret) * np.sqrt(n)
    else:
        t_stat = 0.0
        
    return mean_ret * 10000, t_stat, len(df_sig) # bps

def execute():
    datasets = load_and_resample()
    
    dev_results = []
    oos_results = []
    
    cutoff = pd.to_datetime('2023-06-30')
    
    # Process features
    data_feat = {}
    for W in ['5min', '15min']:
        df_feat = generate_features(datasets[W], W)
        data_feat[W] = df_feat
    
    print("Running DEV Selection...")
    best_config = None
    best_score = -9999
    
    flow_thresholds = [2.0, 2.5]
    resp_thresholds = [0.25, 0.50]
    horizons = ['15m', '30m', '1h']
    
    for W in ['5min', '15min']:
        df_feat = data_feat[W]
        dev_df = df_feat[df_feat['timestamp'] <= cutoff].copy()
        
        for t_flow in flow_thresholds:
            for t_resp in resp_thresholds:
                # S4.1 Combined
                bull = (dev_df['z_flow'] < -t_flow) & (dev_df['r_norm'] > -t_resp)
                bear = (dev_df['z_flow'] > t_flow) & (dev_df['r_norm'] < t_resp)
                dev_df['sig_comb'] = bull.astype(int) - bear.astype(int)
                
                # Flow Only (Baseline C)
                dev_df['sig_flow'] = (dev_df['z_flow'] < -t_flow).astype(int) - (dev_df['z_flow'] > t_flow).astype(int)
                
                for H in horizons:
                    target_col = f'label_{H}'
                    g_comb, t_comb, n_comb = calendar_time_portfolio(dev_df, 'sig_comb', target_col)
                    g_flow, t_flow_b, n_flow = calendar_time_portfolio(dev_df, 'sig_flow', target_col)
                    
                    # Cost-aware expectancy: assuming 12 bps cost. 
                    net_comb = g_comb - 12.0
                    inc_val = g_comb - g_flow
                    
                    # Selection criterion: Maximize net_comb, strictly requiring inc_val > 0 and N >= 30
                    if n_comb >= 30 and inc_val > 0:
                        score = net_comb
                        if score > best_score:
                            best_score = score
                            best_config = (W, t_flow, t_resp, H)
                            
                    #print(f"DEV {W}, TF={t_flow}, TR={t_resp}, H={H} -> Gross: {g_comb:.2f}, FlowOnly: {g_flow:.2f}, Inc: {inc_val:.2f}, Net: {net_comb:.2f}")

    print(f"Selected DEV Config: {best_config} with DEV Score (Net Bps): {best_score:.2f}")
    
    if not best_config:
        print("No viable DEV config found. Generating INCONCLUSIVE report.")
        W_opt, t_flow_opt, t_resp_opt, H_opt = ('15min', 2.0, 0.50, '30m')
        s41_gross, s41_t, s41_count = 0, 0, 0
        base_c_gross, base_c_t, base_c_count = 0, 0, 0
        base_b_gross, base_b_t, base_b_count = 0, 0, 0
        base_a_gross, base_a_t, base_a_count = 0, 0, 0
        s41_net = 0
        inc_pass = False
        median_sym, top1, top3, top5, pct_pos = 0, 0, 0, 0, 0
        high_vol, low_vol = 0, 0
        final_status = "INCONCLUSIVE / INSUFFICIENT DATA"
        num_tests = 24
        oos_pass = False
        cost_pass = False
    else:
        W_opt, t_flow_opt, t_resp_opt, H_opt = best_config
        oos_df = data_feat[W_opt][data_feat[W_opt]['timestamp'] > cutoff].copy()
        target_col = f'label_{H_opt}'
        
        # S4.1
        bull = (oos_df['z_flow'] < -t_flow_opt) & (oos_df['r_norm'] > -t_resp_opt)
        bear = (oos_df['z_flow'] > t_flow_opt) & (oos_df['r_norm'] < t_resp_opt)
        oos_df['s41_sig'] = bull.astype(int) - bear.astype(int)
        
        # Baseline C: Flow Only
        oos_df['base_c_sig'] = (oos_df['z_flow'] < -t_flow_opt).astype(int) - (oos_df['z_flow'] > t_flow_opt).astype(int)
        
        # Baseline B: Price Only (Reversal of extreme R_Norm)
        # Using t_flow_opt as magnitude equivalent for extreme price
        oos_df['base_b_sig'] = (oos_df['r_norm'] < -t_flow_opt).astype(int) - (oos_df['r_norm'] > t_flow_opt).astype(int)
        
        # Baseline A: Drift
        oos_df['base_a_sig'] = 1
        
        s41_gross, s41_t, s41_count = calendar_time_portfolio(oos_df, 's41_sig', target_col)
        base_c_gross, base_c_t, base_c_count = calendar_time_portfolio(oos_df, 'base_c_sig', target_col)
        base_b_gross, base_b_t, base_b_count = calendar_time_portfolio(oos_df, 'base_b_sig', target_col)
        base_a_gross, base_a_t, base_a_count = calendar_time_portfolio(oos_df, 'base_a_sig', target_col)
        
        # Costs
        fee_in, fee_out = -5.0, -5.0
        slip_in, slip_out = -1.0, -1.0
        funding = 0.0
        total_costs = fee_in + fee_out + slip_in + slip_out + funding
        s41_net = s41_gross + total_costs
        
        # Cross Sectional
        oos_sig = oos_df[oos_df['s41_sig'] != 0].copy()
        if not oos_sig.empty:
            oos_sig['trade_ret_bps'] = oos_sig['s41_sig'] * (np.exp(oos_sig[target_col]) - 1) * 10000
            sym_returns = oos_sig.groupby('symbol')['trade_ret_bps'].mean().sort_values(ascending=False)
            median_sym = sym_returns.median() if not sym_returns.empty else 0
            top1 = sym_returns.iloc[0] if len(sym_returns) > 0 else 0
            top3 = sym_returns.iloc[:3].mean() if len(sym_returns) >= 3 else 0
            top5 = sym_returns.iloc[:5].mean() if len(sym_returns) >= 5 else 0
            pct_pos = (sym_returns > 0).mean() * 100 if not sym_returns.empty else 0
            
            high_vol = oos_sig[oos_sig['atr_vol'] > oos_sig['atr_vol'].median()]['trade_ret_bps'].mean()
            low_vol = oos_sig[oos_sig['atr_vol'] <= oos_sig['atr_vol'].median()]['trade_ret_bps'].mean()
            high_vol = high_vol if pd.notna(high_vol) else 0
            low_vol = low_vol if pd.notna(low_vol) else 0
        else:
            median_sym, top1, top3, top5, pct_pos = 0, 0, 0, 0, 0
            high_vol, low_vol = 0, 0
            
        num_tests = 24
        fdr_thresh = 2.5 # Approximate strict boundary
        
        oos_pass = s41_gross > 0 and s41_t > fdr_thresh
        cost_pass = s41_net > 0
        inc_pass = (s41_gross > base_c_gross) and (s41_gross > base_b_gross)
        
        if s41_count < 30:
            final_status = "INCONCLUSIVE / INSUFFICIENT DATA"
        elif not oos_pass or not inc_pass:
            final_status = "REJECTED"
        elif not cost_pass:
            final_status = "REJECTED (FAILED COST_PASS)"
        else:
            final_status = "VALIDATED_ALPHA_CANDIDATE"

    report = f"""# PHASE 7.6.12 S4.1: FLOW/PRICE DISLOCATION (PROXY) REPORT

## Executive Summary
This report evaluates EXP-S4.1: **Flow-Price Dislocation Proxy**. 
Hypothesis: A short-horizon shock in aggressive taker flow (Z_Flow) coupled with an unusually muted price response (R_Norm) proxy for liquidity absorption and signal reversals.
*Note: This is a FLOW-PRICE DISLOCATION PROXY. True canonical L2 absorption is unavailable in Binance historical OHLCV.*

**Final Promotion Status:** `{final_status}`

---

## 1. Is short-horizon flow information predictive?
**Yes/No:** 
- Flow-Only (Baseline C) Gross Return: {base_c_gross:.2f} bps (t={base_c_t:.2f}, N={base_c_count})
- Short-horizon taker flow imbalances exhibit predictive power if the t-stat is significant.

## 2. Does price-response conditioning add information?
**Yes/No:** 
- S4.1 (Flow + Price) Gross Return: {s41_gross:.2f} bps (t={s41_t:.2f}, N={s41_count})
- This demonstrates whether conditioning on a small price response yields a cleaner signal subset.

## 3. Does the combined signal beat flow-only?
**Incremental Value vs Baseline C:** {s41_gross - base_c_gross:.2f} bps.

## 4. Does it beat price-only?
**Incremental Value vs Baseline B:** {s41_gross - base_b_gross:.2f} bps.
- Price-Only Reversal (Baseline B) Gross: {base_b_gross:.2f} bps (t={base_b_t:.2f})

## 5. Does it survive costs?
**Decomposed Costs:**
- **Gross Return:** {s41_gross:.2f} bps
- **Fees (Entry + Exit):** -10.0 bps
- **Slippage (Entry + Exit):** -2.0 bps
- **Funding:** ~0.0 bps
- **Net Expectancy:** {s41_net:.2f} bps

## 6. Does it survive global FDR?
With {num_tests} total pre-registered DEV tests, we apply a stricter critical threshold (approx t>2.5).
- S4.1 t-statistic: {s41_t:.2f}
- Survives FDR? {"Yes" if s41_t > 2.5 else "No"}

## 7. Is it cross-sectional?
- **Median Symbol Return:** {median_sym:.2f} bps
- **% Positive Symbols:** {pct_pos:.1f}%

## 8. Is it stable?
The use of the Calendar-Time Portfolio approach heavily penalizes clustered / single-regime bursts. A t-stat of {s41_t:.2f} indicates {"high" if s41_t > 2.0 else "low"} temporal stability.
- **Top 1 Symbol Contribution:** {top1:.2f} bps
- **Top 3 Symbol Contribution:** {top3:.2f} bps

## 9. Is it genuinely distinct from S3?
S3 exploited extreme 14-day aggregated OI positioning (crowding). S4.1 exploits ephemeral {W_opt} flow shock/price disconnects. They are fundamentally orthogonal causal drivers (Macro positioning vs Micro-structure absorption proxy).

## 10. Final Promotion Status
**{final_status}**
"""
    
    report_path = REPORT_DIR / "PHASE7_6_12_S4_1_FLOW_PRICE_DISLOCATION_REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)
        
    print(f"Report written to {report_path}")
    
    # Update Feature Registry
    registry_path = REPORT_DIR / "PHASE7_FINAL_FEATURE_REGISTRY.md"
    
    if registry_path.exists():
        with open(registry_path, "r") as f:
            content = f.read()
    else:
        content = "# PHASE 7 FINAL FEATURE REGISTRY\n\n| FEATURE_ID | HYPOTHESIS | STATUS | DATA_SOURCE | OOS_RESULT (Gross) | NET_EXPECTANCY | INCREMENTAL_VALUE | LIVE_STATUS |\n|------------|------------|--------|-------------|--------------------|----------------|-------------------|-------------|"
        
    # Append S4.1
    inc_str = "YES" if inc_pass else "NO"
    s41_row = f"\n| **S4.1** | Flow/Price Dislocation Proxy | {final_status} | Binance UM | {s41_gross:.2f} bps | {s41_net:.2f} bps | {inc_str} | N/A |"
    
    if "**S4.1**" not in content:
        content += s41_row
        with open(registry_path, "w") as f:
            f.write(content)
        print("Updated Feature Registry.")
        
if __name__ == "__main__":
    execute()
