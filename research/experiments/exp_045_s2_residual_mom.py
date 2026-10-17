import pandas as pd
import numpy as np
from pathlib import Path
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_data():
    path = Path("data/processed/binance_um_universe_1m_v2.parquet")
    logging.info(f"Loading data from {path}")
    df = pd.read_parquet(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Calculate 1m returns
    df['ret_1m'] = df.groupby('symbol')['close'].pct_change()
    return df

def generate_features(df):
    logging.info("Generating Beta and Residuals")
    
    # Extract BTC returns for Beta calculation
    btc_ret = df[df['symbol'] == 'BTCUSDT'].set_index('timestamp')['ret_1m'].rename('btc_ret_1m')
    df = df.merge(btc_ret, on='timestamp', how='left')
    
    # Pre-registered Beta Window: 24h (1440m)
    beta_window = 1440
    
    # Beta = Cov(R_i, R_BTC) / Var(R_BTC)
    # Using rolling cov and var on 1m returns
    cov = df.groupby('symbol').apply(
        lambda x: x['ret_1m'].rolling(beta_window).cov(x['btc_ret_1m'])
    ).reset_index(0, drop=True)
    
    var_btc = df.groupby('symbol').apply(
        lambda x: x['btc_ret_1m'].rolling(beta_window).var()
    ).reset_index(0, drop=True)
    
    df['beta_24h'] = cov / var_btc
    # Epsilon = R_i - beta * R_BTC (Residual 1m return)
    df['eps_1m'] = df['ret_1m'] - df['beta_24h'] * df['btc_ret_1m']
    
    # Residual Momentum over 1h, 4h, 24h
    # We define residual momentum as the sum of 1m residuals over the lookback
    lookbacks = {'1h': 60, '4h': 240, '24h': 1440}
    
    for label, periods in lookbacks.items():
        # Raw TSMOM Baseline
        df[f'raw_ret_{label}'] = df.groupby('symbol')['close'].pct_change(periods)
        df[f'raw_mom_{label}'] = np.sign(df[f'raw_ret_{label}'])
        
        # Residual Momentum (S2)
        df[f'eps_{label}'] = df.groupby('symbol')['eps_1m'].rolling(periods).sum().reset_index(0, drop=True)
        df[f'res_mom_{label}'] = np.sign(df[f'eps_{label}'])
        
        df[f'vol_{label}'] = df.groupby('symbol')['ret_1m'].rolling(periods).std().reset_index(0, drop=True) * np.sqrt(525600)
    
    # 24h vol for label adjustment
    df['vol_24h'] = df.groupby('symbol')['ret_1m'].rolling(1440).std().reset_index(0, drop=True) * np.sqrt(525600)
    
    return df

def generate_labels(df):
    logging.info("Generating forward labels (1h, 4h)")
    horizons = {'1h': 60, '4h': 240}
    
    for label, periods in horizons.items():
        df[f'fwd_ret_{label}'] = df.groupby('symbol')['close'].pct_change(periods).shift(-periods)
        df[f'label_vol_adj_{label}'] = df[f'fwd_ret_{label}'] / df['vol_24h'].replace(0, np.nan)
        
    return df

def run_dev_selection(df):
    logging.info("Running DEV label and lookback selection...")
    dev_cutoff = df['timestamp'].quantile(0.60)
    
    # We use DEV to select the best parameter combo based on Residual Momentum IC
    dev_cols = ['timestamp', 'symbol', 'res_mom_1h', 'res_mom_4h', 'res_mom_24h', 
                'label_vol_adj_1h', 'label_vol_adj_4h']
    dev_df = df[(df['timestamp'] <= dev_cutoff) & (df['symbol'] != 'BTCUSDT')][dev_cols].dropna()
    
    lookbacks = ['1h', '4h', '24h']
    horizons = ['1h', '4h']
    
    results = []
    
    for L in lookbacks:
        feature = f'res_mom_{L}'
        for H in horizons:
            label = f'label_vol_adj_{H}'
            
            ic_vals = []
            for ts, grp in dev_df.groupby('timestamp'):
                if len(grp) > 2:  # Need at least 3 points for meaningful Spearman, although we only have 5 altcoins
                    c = grp[feature].corr(grp[label], method='spearman')
                    if pd.notna(c):
                        ic_vals.append(c)
            ic = pd.Series(ic_vals).mean() if len(ic_vals) > 0 else 0
            results.append({'lookback': L, 'horizon': H, 'IC': ic})
            
    res_df = pd.DataFrame(results)
    print("DEV Selection Results (Residual Momentum IC):")
    print(res_df.sort_values('IC', ascending=False))
    
    best = res_df.loc[res_df['IC'].idxmax()]
    return best['lookback'], best['horizon'], dev_cutoff

def evaluate_single_leg(df, dev_cutoff, lookback, horizon):
    logging.info(f"Evaluating Single-Leg OOS for {lookback} predicting forward {horizon} returns")
    feature_raw = f'raw_mom_{lookback}'
    feature_res = f'res_mom_{lookback}'
    fwd_ret_col = f'fwd_ret_{horizon}'
    
    oos_cols = ['timestamp', 'symbol', feature_raw, feature_res, fwd_ret_col, 'vol_24h', 'btc_ret_1m']
    
    # Execution Universe: Exclude ADA. Also exclude BTC since BTC residual vs BTC is 0.
    exec_symbols = ['ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']
    oos_df = df[(df['timestamp'] > dev_cutoff) & (df['symbol'].isin(exec_symbols))][oos_cols].dropna()
    
    # Baseline A: Raw Momentum
    oos_df['trade_raw'] = oos_df[feature_raw] * oos_df[fwd_ret_col]
    
    # Baseline B: Market Return (Long Only)
    oos_df['trade_mkt'] = 1 * oos_df[fwd_ret_col]
    
    # S2: Residual Momentum
    oos_df['trade_res'] = oos_df[feature_res] * oos_df[fwd_ret_col]
    
    # Aggregate Calendar Time
    H_periods = int(horizon.replace('h', '')) * 60
    port_raw = oos_df.groupby('timestamp')['trade_raw'].mean().iloc[::H_periods]
    port_mkt = oos_df.groupby('timestamp')['trade_mkt'].mean().iloc[::H_periods]
    port_res = oos_df.groupby('timestamp')['trade_res'].mean().iloc[::H_periods]
    
    def get_stats(port):
        mean_bps = port.mean() * 10000
        std_bps = port.std() * 10000
        n = len(port)
        t_stat = (mean_bps / std_bps) * np.sqrt(n) if std_bps > 0 else 0
        return mean_bps, t_stat, n
        
    mkt_bps, mkt_t, n = get_stats(port_mkt)
    raw_bps, raw_t, _ = get_stats(port_raw)
    res_bps, res_t, _ = get_stats(port_res)
    
    print("\n--- OOS SINGLE LEG (NON-OVERLAPPING) ---")
    print(f"N: {n}")
    print(f"Baseline B (Market Drift) Gross Expectancy: {mkt_bps:.2f} bps (t={mkt_t:.2f})")
    print(f"Baseline A (Raw Momentum) Gross Expectancy: {raw_bps:.2f} bps (t={raw_t:.2f})")
    print(f"Model S2 (Residual Mom) Gross Expectancy: {res_bps:.2f} bps (t={res_t:.2f})")
    
    # Costs
    print(f"\nModel S2 Net Expectancy (after 12bps): {res_bps - 12.0:.2f} bps")
    
    # Regimes
    vol_24h_med = oos_df['vol_24h'].median()
    high_vol = oos_df[oos_df['vol_24h'] > vol_24h_med].groupby('timestamp')['trade_res'].mean().iloc[::H_periods].mean() * 10000
    low_vol = oos_df[oos_df['vol_24h'] <= vol_24h_med].groupby('timestamp')['trade_res'].mean().iloc[::H_periods].mean() * 10000
    
    btc_trend = oos_df.groupby('timestamp')['btc_ret_1m'].sum().rolling(240).mean() # 4h trend
    # Need alignment
    
    print(f"Regime High Vol Expectancy: {high_vol:.2f} bps")
    print(f"Regime Low Vol Expectancy: {low_vol:.2f} bps")

def main():
    df = load_data()
    df = generate_features(df)
    df = generate_labels(df)
    
    best_L, best_H, dev_cutoff = run_dev_selection(df)
    print(f"\nSelected Lookback: {best_L}, Selected Horizon: {best_H}")
    
    evaluate_single_leg(df, dev_cutoff, best_L, best_H)
    
    print("\n--- MARKET NEUTRAL L/S ---")
    print("INCONCLUSIVE: Total Research Universe is 6 symbols, Execution Universe is 5 symbols.")
    print("Subtracting BTC leaves 4 or 5 altcoins. Cross-sectional ranking for market-neutral portfolios")
    print("requires significant breadth (N >= 30) to properly extract purely idiosyncratic returns.")
    print("A L/S portfolio built on 5 coins is heavily exposed to individual coin idiosyncratic risk")
    print("and cannot be treated as a true market-neutral alpha factor. Will mark inconclusive.")

if __name__ == "__main__":
    main()
