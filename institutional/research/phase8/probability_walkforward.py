import os
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, log_loss
import json

# Paths
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
RESULTS_DIR = Path(__file__).resolve().parent

def load_canonical_data():
    print("Loading canonical data...")
    df = pd.read_parquet(DATA_DIR / "binance_um_universe_1m_v2.parquet")
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    funding = pd.read_parquet(DATA_DIR / "research_funding.parquet")
    funding['timestamp'] = pd.to_datetime(funding['timestamp'], unit='ms')
    
    df.set_index('timestamp', inplace=True)
    df = df.groupby('symbol').resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'quote_volume': 'sum',
        'taker_buy_volume': 'sum',
        'taker_buy_quote_volume': 'sum',
        'sum_open_interest': 'last'
    }).reset_index()
    
    return df, funding

def calculate_s3_features(df, funding):
    print("Calculating S3 features...")
    funding_ffill = funding.set_index(['timestamp', 'symbol']).unstack(level=1).ffill().stack().reset_index()
    if 'funding_rate' not in funding_ffill.columns:
        funding_ffill.rename(columns={0: 'funding_rate'}, inplace=True)
        
    df = pd.merge(df, funding_ffill[['timestamp', 'symbol', 'funding_rate']], on=['timestamp', 'symbol'], how='left')
    df['funding_rate'] = df.groupby('symbol')['funding_rate'].ffill()
    
    df.set_index('timestamp', inplace=True)
    df['close_4h_ago'] = df.groupby('symbol')['close'].shift(48)
    df['R_4h'] = np.log(df['close'] / df['close_4h_ago'])
    
    window_7d = 12 * 24 * 7 
    df['F_mean_7d'] = df.groupby('symbol')['funding_rate'].transform(lambda x: x.rolling(window_7d, min_periods=100).mean())
    df['F_std_7d'] = df.groupby('symbol')['funding_rate'].transform(lambda x: x.rolling(window_7d, min_periods=100).std())
    df['Z_F'] = (df['funding_rate'] - df['F_mean_7d']) / df['F_std_7d'].replace(0, np.nan)
    
    df['oi_4h_ago'] = df.groupby('symbol')['sum_open_interest'].shift(48)
    df['delta_OI_4h'] = (df['sum_open_interest'] - df['oi_4h_ago']) / df['oi_4h_ago'].replace(0, np.nan)
    
    window_14d = 12 * 24 * 14
    df['theta_OI'] = df.groupby('symbol')['delta_OI_4h'].transform(
        lambda x: x.rolling(window_14d, min_periods=100).quantile(0.90)
    )
    
    cond_long = (df['R_4h'] < 0) & (df['Z_F'] < -1.5) & (df['delta_OI_4h'] > df['theta_OI'])
    cond_short = (df['R_4h'] > 0) & (df['Z_F'] > 1.5) & (df['delta_OI_4h'] > df['theta_OI'])
    
    df['S3_Signal'] = 0
    df.loc[cond_long, 'S3_Signal'] = 1
    df.loc[cond_short, 'S3_Signal'] = -1
    
    # Context features
    df['R_5m'] = np.log(df['close'] / df['close'].shift(1))
    df['volatility_14d'] = df.groupby('symbol')['R_5m'].transform(lambda x: x.rolling(window_14d).std())
    
    # Regime diagnostics (expanding median)
    df['regime_vol_median'] = df['volatility_14d'].expanding().median()
    df['regime_oi_median'] = df['delta_OI_4h'].expanding().median()
    df['is_high_vol'] = df['volatility_14d'] > df['regime_vol_median']
    df['is_high_oi'] = df['delta_OI_4h'] > df['regime_oi_median']
    
    # Targets
    df['close_1h_fwd'] = df.groupby('symbol')['close'].shift(-12)
    df['R_1h_fwd'] = np.log(df['close_1h_fwd'] / df['close'])
    df['Target_R_1h_gt_0'] = (df['R_1h_fwd'] > 0).astype(int)
    
    return df.reset_index()

def generate_expanding_folds(events_df, n_folds=5, min_train=200, block_size=50):
    folds = []
    if len(events_df) < min_train + (3 * block_size):
        return folds # INSUFFICIENT DATA
        
    for i in range(n_folds):
        train_end_idx = min_train + (i * block_size)
        calib_end_idx = train_end_idx + block_size
        thresh_end_idx = calib_end_idx + block_size
        test_end_idx = thresh_end_idx + block_size
        
        if test_end_idx > len(events_df):
            break
            
        train = events_df.iloc[:train_end_idx].copy()
        calib = events_df.iloc[train_end_idx:calib_end_idx].copy()
        thresh = events_df.iloc[calib_end_idx:thresh_end_idx].copy()
        test = events_df.iloc[thresh_end_idx:test_end_idx].copy()
        
        # Purge overlaps
        purge_gap = pd.Timedelta(hours=1)
        
        calib = calib[calib['timestamp'] >= train['timestamp'].iloc[-1] + purge_gap]
        thresh = thresh[thresh['timestamp'] >= calib['timestamp'].iloc[-1] + purge_gap]
        test = test[test['timestamp'] >= thresh['timestamp'].iloc[-1] + purge_gap]
        train = train[train['timestamp'] + purge_gap <= calib['timestamp'].min()]
        
        folds.append({
            'fold_id': i + 1,
            'train': train,
            'calib': calib,
            'thresh': thresh,
            'test': test,
            'meta': {
                'train_start': str(train['timestamp'].min()),
                'train_end': str(train['timestamp'].max()),
                'calib_start': str(calib['timestamp'].min()),
                'calib_end': str(calib['timestamp'].max()),
                'thresh_start': str(thresh['timestamp'].min()),
                'thresh_end': str(thresh['timestamp'].max()),
                'test_start': str(test['timestamp'].min()),
                'test_end': str(test['timestamp'].max()),
                'N_train': len(train),
                'N_calib': len(calib),
                'N_thresh': len(thresh),
                'N_test': len(test)
            }
        })
        
    return folds

def execute_engine():
    df, funding = load_canonical_data()
    df = calculate_s3_features(df, funding)
    
    s3_events = df[df['S3_Signal'] != 0].copy()
    s3_events.dropna(subset=['Target_R_1h_gt_0', 'volatility_14d', 'R_1h_fwd', 'Z_F', 'delta_OI_4h'], inplace=True)
    s3_events.sort_values('timestamp', inplace=True)
    
    if len(s3_events) == 0:
        print("No S3 events found. Check feature definitions.")
        return
        
    print(f"Total S3 Events: {len(s3_events)}")
    
    # We will aim for min_train=200, block_size=75. So 200 + 3*75 = 425 minimum
    folds = generate_expanding_folds(s3_events, n_folds=5, min_train=200, block_size=75)
    
    if len(folds) == 0:
        print("STATUS: INCONCLUSIVE / INSUFFICIENT DATA")
        return
        
    # Print fold table
    print("\n--- FOLD TABLE ---")
    for f in folds:
        print(f"Fold {f['fold_id']}: Train: {f['meta']['N_train']} ({f['meta']['train_start'][:10]} - {f['meta']['train_end'][:10]}), Calib: {f['meta']['N_calib']}, Thresh: {f['meta']['N_thresh']}, Test: {f['meta']['N_test']}")
        
    # Execute Model Pipeline
    results_by_fold = []
    
    for fold in folds:
        fid = fold['fold_id']
        print(f"--- Running Fold {fid} ---")
        
        train_df = fold['train']
        calib_df = fold['calib']
        thresh_df = fold['thresh']
        test_df = fold['test']
        
        # MODEL 0: Base Rate
        # Empirical win rate on training
        p_base = train_df['Target_R_1h_gt_0'].mean()
        
        # Features for models
        f_A = ['S3_Signal']
        f_C = ['S3_Signal', 'volatility_14d', 'delta_OI_4h', 'Z_F']
        
        def fit_and_predict(features, model_type="Logistic", use_calib=True):
            X_train = train_df[features]
            y_train = train_df['Target_R_1h_gt_0']
            X_calib = calib_df[features]
            y_calib = calib_df['Target_R_1h_gt_0']
            
            if model_type == "Logistic":
                clf = LogisticRegression(C=1.0)
            elif model_type == "Tree":
                clf = HistGradientBoostingClassifier(max_depth=3, max_iter=50)
                
            clf.fit(X_train, y_train)
            
            if use_calib:
                calib_preds = clf.decision_function(X_calib).reshape(-1, 1)
                calibrator = LogisticRegression()
                calibrator.fit(calib_preds, y_calib)
                
                def predict_fn(df):
                    X = df[features]
                    raw = clf.decision_function(X).reshape(-1, 1)
                    return calibrator.predict_proba(raw)[:, 1]
            else:
                def predict_fn(df):
                    X = df[features]
                    return clf.predict_proba(X)[:, 1]
                    
            return predict_fn
            
        pred_fns = {
            'M0_BaseRate': lambda df: np.full(len(df), p_base),
            'M1_Deterministic': lambda df: np.where(df['S3_Signal'] != 0, 1.0, 0.0), # Baseline S3
            'M2_Logis_S3': fit_and_predict(f_A, "Logistic", True),
            'M3_Logis_All': fit_and_predict(f_C, "Logistic", True),
            'M4_Tree_All': fit_and_predict(f_C, "Tree", True)
        }
        
        fold_res = {'fold_id': fid, 'meta': fold['meta'], 'models': {}}
        
        for m_name, pred_fn in pred_fns.items():
            # 1. Optimize Threshold on thresh_df
            p_thresh_preds = pred_fn(thresh_df)
            best_thresh = 0.5
            best_net = -np.inf
            
            # Grid search threshold from 0.01 to 0.99
            for t_cand in np.arange(0.01, 1.0, 0.01):
                trades = p_thresh_preds > t_cand
                if trades.sum() == 0:
                    net = 0
                else:
                    gross = (thresh_df.loc[trades, 'R_1h_fwd'] * thresh_df.loc[trades, 'S3_Signal']).sum()
                    net = gross - (trades.sum() * 0.0012) # 12 bps fixed for threshold selection
                
                if net > best_net:
                    best_net = net
                    best_thresh = t_cand
                    
            # If no threshold makes money, set to 1.1 (never trade)
            if best_net <= 0 and m_name not in ['M1_Deterministic']:
                best_thresh = 1.1 
                
            if m_name == 'M1_Deterministic':
                best_thresh = 0.5 # Always take all trades
                
            # 2. Evaluate on test_df
            p_test = pred_fn(test_df)
            y_test = test_df['Target_R_1h_gt_0']
            
            brier = brier_score_loss(y_test, p_test)
            ll = log_loss(y_test, p_test) if len(np.unique(y_test)) > 1 else np.nan
            
            trades = p_test > best_thresh
            n_ops = len(test_df)
            n_acc = trades.sum()
            coverage = n_acc / n_ops if n_ops > 0 else 0
            
            if n_acc > 0:
                trade_returns = test_df.loc[trades, 'R_1h_fwd'] * test_df.loc[trades, 'S3_Signal']
                mean_gross = trade_returns.mean()
                win_rate = (trade_returns > 0).mean()
                worst_trade = trade_returns.min()
                mean_net_12 = mean_gross - 0.0012
                median_net_12 = trade_returns.median() - 0.0012
                
                sensitivities = {}
                for cost_bps in [10, 12, 14, 16, 18]:
                    c = cost_bps / 10000.0
                    sensitivities[str(cost_bps)] = float((mean_gross - c) * 10000)
            else:
                mean_gross = 0
                mean_net_12 = 0
                median_net_12 = 0
                win_rate = 0
                worst_trade = 0
                sensitivities = {str(c): 0.0 for c in [10, 12, 14, 16, 18]}
                
            fold_res['models'][m_name] = {
                'Threshold': float(best_thresh),
                'Brier': float(brier),
                'LogLoss': float(ll),
                'Coverage': float(coverage),
                'N_Accepted': int(n_acc),
                'N_Opportunities': int(n_ops),
                'WinRate': float(win_rate),
                'Mean_Gross_bps': float(mean_gross * 10000),
                'Mean_Net_12bps': float(mean_net_12 * 10000),
                'Median_Net_12bps': float(median_net_12 * 10000),
                'Worst_Trade_bps': float(worst_trade * 10000),
                'Cost_Sensitivity_bps': sensitivities
            }
            
        results_by_fold.append(fold_res)
        
    with open(RESULTS_DIR / "walkforward_results.json", "w") as f:
        json.dump({'Folds': results_by_fold}, f, indent=4)
        
    print("Walk-forward evaluation complete. Results saved to walkforward_results.json.")

if __name__ == "__main__":
    execute_engine()
