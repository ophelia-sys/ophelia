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
    
    # Convert numerical columns from str if necessary
    cols_to_convert = ['close', 'open', 'high', 'low', 'volume', 'quote_volume']
    for c in cols_to_convert:
        if df[c].dtype == object or df[c].dtype == str:
            df[c] = pd.to_numeric(df[c])
            
    # Calculate 1m returns
    df['ret_1m'] = df.groupby('symbol')['close'].pct_change()
    return df

def generate_features(df):
    logging.info("Generating features for S1 TSMOM (1h, 4h, 24h)")
    lookbacks = {'1h': 60, '4h': 240, '24h': 1440}
    
    for label, periods in lookbacks.items():
        # Rolling return over L
        df[f'ret_{label}'] = df.groupby('symbol')['close'].pct_change(periods)
        
        # Rolling std of 1m returns annualized (sqrt(525600)) over L
        # Actually just scale by sqrt(periods) or use raw std since scaling is monotonic, 
        # but let's use annualized volatility.
        df[f'vol_{label}'] = df.groupby('symbol')['ret_1m'].rolling(periods).std().reset_index(0,drop=True) * np.sqrt(525600)
        
        # S_t = sign(R_L) / sigma_L
        df[f'S1_{label}'] = np.sign(df[f'ret_{label}']) / df[f'vol_{label}'].replace(0, np.nan)
        
        # Clip extreme outliers
        df[f'S1_{label}'] = df[f'S1_{label}'].clip(lower=df[f'S1_{label}'].quantile(0.01), upper=df[f'S1_{label}'].quantile(0.99))
        
    return df

def generate_labels(df):
    logging.info("Generating forward labels (1h, 4h)")
    horizons = {'1h': 60, '4h': 240}
    
    for label, periods in horizons.items():
        df[f'fwd_ret_{label}'] = df.groupby('symbol')['close'].pct_change(periods).shift(-periods)
        # Volatility adjusted using a 24h trailing vol
        vol_24h = df.groupby('symbol')['ret_1m'].rolling(1440).std().reset_index(0,drop=True) * np.sqrt(525600)
        df[f'label_vol_adj_{label}'] = df[f'fwd_ret_{label}'] / vol_24h.replace(0, np.nan)
        
    return df

def run_dev_selection(df):
    logging.info("Running DEV label and lookback selection...")
    dev_cutoff = df['timestamp'].quantile(0.60)
    dev_cols = ['timestamp', 'symbol', 'S1_1h', 'S1_4h', 'S1_24h', 'label_vol_adj_1h', 'label_vol_adj_4h']
    dev_df = df[df['timestamp'] <= dev_cutoff][dev_cols].dropna()
    print(f"dev_df size after dropna: {len(dev_df)}")
    
    lookbacks = ['1h', '4h', '24h']
    horizons = ['1h', '4h']
    
    results = []
    
    for L in lookbacks:
        feature = f'S1_{L}'
        for H in horizons:
            label = f'label_vol_adj_{H}'
            ic_vals = []
            for ts, grp in dev_df.groupby('timestamp'):
                if len(grp) > 2:
                    c = grp[feature].corr(grp[label], method='spearman')
                    if pd.notna(c):
                        ic_vals.append(c)
            ic = pd.Series(ic_vals).mean() if len(ic_vals) > 0 else 0
            results.append({'lookback': L, 'horizon': H, 'IC': ic})
            
    res_df = pd.DataFrame(results)
    print("NA counts in DEV:")
    print(dev_df[['S1_1h', 'S1_4h', 'S1_24h', 'label_vol_adj_1h', 'label_vol_adj_4h']].isna().sum())
    print("DEV Selection Results:")
    print(res_df.sort_values('IC', ascending=False))
    
    best = res_df.loc[res_df['IC'].idxmax()]
    return best['lookback'], best['horizon'], dev_cutoff

def evaluate_oos(df, dev_cutoff, lookback, horizon):
    logging.info(f"Evaluating OOS for S1_{lookback} predicting forward {horizon} returns")
    feature = f'S1_{lookback}'
    fwd_ret_col = f'fwd_ret_{horizon}'
    oos_cols = ['timestamp', 'symbol', feature, fwd_ret_col, 'vol_24h']
    oos_df = df[df['timestamp'] > dev_cutoff][oos_cols].dropna()
    
    # Cross-sectional Z-score for ranking
    oos_df['z_feature'] = oos_df.groupby('timestamp')[feature].transform(lambda x: (x - x.mean()) / x.std())
    
    # Enter long if Top Quintile, Short if Bottom Quintile
    oos_df['position'] = 0
    oos_df.loc[oos_df['z_feature'] > 0.84, 'position'] = 1 # approx top 20%
    oos_df.loc[oos_df['z_feature'] < -0.84, 'position'] = -1
    
    # Calculate returns
    oos_df['trade_ret'] = oos_df['position'] * oos_df[fwd_ret_col]
    
    # Calendar-Time Portfolio Aggregation
    port_ret = oos_df.groupby('timestamp')['trade_ret'].mean()
    
    # Annualized mean and t-stat (using Non-overlapping assumption, dividing by periods)
    # Since we are using 1m bars but holding for H minutes, standard errors need Newey-West or we subsample.
    # We will subsample to non-overlapping periods for conservative t-stat.
    H_periods = int(horizon.replace('h', '')) * 60
    sampled_port = port_ret.iloc[::H_periods]
    
    cal_mean = sampled_port.mean() * 10000 # in bps
    cal_std = sampled_port.std() * 10000
    n = len(sampled_port)
    t_stat = (cal_mean / cal_std) * np.sqrt(n) if cal_std > 0 else 0
    
    gross_exp = cal_mean
    # 12 bps total cost (entry + exit)
    net_exp = gross_exp - 12.0
    
    print(f"OOS Gross Expectancy (bps): {gross_exp:.2f}")
    print(f"OOS Net Expectancy (bps): {net_exp:.2f}")
    print(f"OOS t-stat (non-overlapping): {t_stat:.2f}")
    print(f"OOS Non-Overlapping N: {n}")
    
    # Per-symbol stats
    sym_stats = oos_df.groupby('symbol')['trade_ret'].mean() * 10000
    print("\nPer-Symbol Gross Expectancy (bps):")
    print(sym_stats)
    
    # Regime (High Vol vs Low Vol)
    vol_24h_med = oos_df['vol_24h'].median()
    high_vol = oos_df[oos_df['vol_24h'] > vol_24h_med].groupby('timestamp')['trade_ret'].mean().iloc[::H_periods].mean() * 10000
    low_vol = oos_df[oos_df['vol_24h'] <= vol_24h_med].groupby('timestamp')['trade_ret'].mean().iloc[::H_periods].mean() * 10000
    print(f"\nRegime High Vol Expectancy: {high_vol:.2f} bps")
    print(f"Regime Low Vol Expectancy: {low_vol:.2f} bps")
    
    return {
        'gross_exp_bps': gross_exp,
        'net_exp_bps': net_exp,
        't_stat': t_stat,
        'n': n,
        'sym_stats': sym_stats.to_dict(),
        'high_vol_bps': high_vol,
        'low_vol_bps': low_vol
    }

def main():
    df = load_data()
    df = generate_features(df)
    df = generate_labels(df)
    
    best_L, best_H, dev_cutoff = run_dev_selection(df)
    print(f"\nSelected Lookback: {best_L}, Selected Horizon: {best_H}")
    
    results = evaluate_oos(df, dev_cutoff, best_L, best_H)

if __name__ == "__main__":
    main()
