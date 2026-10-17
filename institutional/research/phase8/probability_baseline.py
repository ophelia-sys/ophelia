import os
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, log_loss
import json

# Paths
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
BINGX_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "archive"
RESULTS_DIR = Path(__file__).resolve().parent

def load_canonical_data():
    """Loads the canonical historical dataset and funding data."""
    print("Loading canonical data...")
    df = pd.read_parquet(DATA_DIR / "binance_um_universe_1m_v2.parquet")
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    funding = pd.read_parquet(DATA_DIR / "research_funding.parquet")
    funding['timestamp'] = pd.to_datetime(funding['timestamp'], unit='ms')
    
    # Resample to 5m to speed up feature generation while keeping precision
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
    # Merge funding
    # Since funding is every 8 hours, we forward fill it
    funding_ffill = funding.set_index(['timestamp', 'symbol']).unstack(level=1).ffill().stack().reset_index()
    if 'funding_rate' not in funding_ffill.columns:
        funding_ffill.rename(columns={0: 'funding_rate'}, inplace=True)
        
    df = pd.merge(df, funding_ffill[['timestamp', 'symbol', 'funding_rate']], on=['timestamp', 'symbol'], how='left')
    df['funding_rate'] = df.groupby('symbol')['funding_rate'].ffill()
    
    # R_4h
    df.set_index('timestamp', inplace=True)
    df['close_4h_ago'] = df.groupby('symbol')['close'].shift(48) # 48 * 5m = 4h
    df['R_4h'] = np.log(df['close'] / df['close_4h_ago'])
    
    # Z_F (7d window)
    window_7d = 12 * 24 * 7 # 2016 5m intervals
    df['F_mean_7d'] = df.groupby('symbol')['funding_rate'].transform(lambda x: x.rolling(window_7d, min_periods=100).mean())
    df['F_std_7d'] = df.groupby('symbol')['funding_rate'].transform(lambda x: x.rolling(window_7d, min_periods=100).std())
    df['Z_F'] = (df['funding_rate'] - df['F_mean_7d']) / df['F_std_7d'].replace(0, np.nan)
    
    print("Z_F Null count:", df['Z_F'].isnull().sum(), "/", len(df))
    
    # Delta OI 4h
    df['oi_4h_ago'] = df.groupby('symbol')['sum_open_interest'].shift(48)
    df['delta_OI_4h'] = (df['sum_open_interest'] - df['oi_4h_ago']) / df['oi_4h_ago'].replace(0, np.nan)
    
    # 14d 90th percentile of Delta OI
    window_14d = 12 * 24 * 14
    df['theta_OI'] = df.groupby('symbol')['delta_OI_4h'].transform(
        lambda x: x.rolling(window_14d, min_periods=100).quantile(0.90)
    )
    
    print("delta_OI_4h Null count:", df['delta_OI_4h'].isnull().sum(), "/", len(df))
    print("theta_OI Null count:", df['theta_OI'].isnull().sum(), "/", len(df))
    print("R_4h Null count:", df['R_4h'].isnull().sum(), "/", len(df))
    
    # S3 Signal logic
    # Long: R < 0, Z_F < -1.5, Delta OI > theta_OI
    # Short: R > 0, Z_F > 1.5, Delta OI > theta_OI
    cond_long = (df['R_4h'] < 0) & (df['Z_F'] < -1.5) & (df['delta_OI_4h'] > df['theta_OI'])
    cond_short = (df['R_4h'] > 0) & (df['Z_F'] > 1.5) & (df['delta_OI_4h'] > df['theta_OI'])
    
    df['S3_Signal'] = 0
    df.loc[cond_long, 'S3_Signal'] = 1
    df.loc[cond_short, 'S3_Signal'] = -1
    
    # Context features
    # Volatility (ATR 14d proxy using std dev of returns)
    df['R_5m'] = np.log(df['close'] / df['close'].shift(1))
    df['volatility_14d'] = df.groupby('symbol')['R_5m'].transform(lambda x: x.rolling(window_14d).std())
    
    # Targets
    df['close_1h_fwd'] = df.groupby('symbol')['close'].shift(-12) # 12 * 5m = 1h
    df['R_1h_fwd'] = np.log(df['close_1h_fwd'] / df['close'])
    df['Target_R_1h_gt_0'] = (df['R_1h_fwd'] > 0).astype(int)
    
    return df.reset_index()

def execute_engine():
    df, funding = load_canonical_data()
    df = calculate_s3_features(df, funding)
    
    # Filter to only S3 signal events
    s3_events = df[df['S3_Signal'] != 0].copy()
    s3_events.dropna(subset=['Target_R_1h_gt_0', 'volatility_14d', 'R_1h_fwd'], inplace=True)
    s3_events.sort_values('timestamp', inplace=True)
    
    if len(s3_events) == 0:
        print("No S3 events found. Check feature definitions.")
        return
        
    print(f"Total S3 Events: {len(s3_events)}")
    
    # Temporal Split: 50% TRAIN, 25% CALIBRATION, 25% VALIDATION
    n = len(s3_events)
    train_idx = int(n * 0.5)
    calib_idx = int(n * 0.75)
    
    train_df = s3_events.iloc[:train_idx]
    calib_df = s3_events.iloc[train_idx:calib_idx]
    val_df = s3_events.iloc[calib_idx:]
    
    # Features for Ablation
    # A. S3 ONLY (we encode S3 signal as the only feature)
    features_A = ['S3_Signal']
    # B. S3 + VOL
    features_B = ['S3_Signal', 'volatility_14d']
    # C. S3 + VOL + OI/Funding
    features_C = ['S3_Signal', 'volatility_14d', 'delta_OI_4h', 'Z_F']
    
    def train_and_eval(features, name):
        X_train = train_df[features]
        y_train = train_df['Target_R_1h_gt_0']
        
        X_calib = calib_df[features]
        y_calib = calib_df['Target_R_1h_gt_0']
        
        X_val = val_df[features]
        y_val = val_df['Target_R_1h_gt_0']
        
        # 1. Base Logistic
        clf = LogisticRegression(C=1.0)
        clf.fit(X_train, y_train)
        
        # 2. Calibrated Logistic (Manual Platt Scaling)
        calib_preds_log = clf.decision_function(X_calib).reshape(-1, 1)
        calibrator_log = LogisticRegression()
        calibrator_log.fit(calib_preds_log, y_calib)
        
        # 3. Tree
        tree = HistGradientBoostingClassifier(max_depth=3, max_iter=50)
        tree.fit(X_train, y_train)
        
        # Calibrated Tree (Manual Platt Scaling)
        calib_preds_tree = tree.decision_function(X_calib).reshape(-1, 1)
        calibrator_tree = LogisticRegression()
        calibrator_tree.fit(calib_preds_tree, y_calib)
        
        def predict_calibrated(model, calibrator, X):
            raw_preds = model.decision_function(X).reshape(-1, 1)
            return calibrator.predict_proba(raw_preds)[:, 1]
            
        models = {
            'Logistic': lambda X: clf.predict_proba(X)[:, 1],
            'Calibrated_Logistic': lambda X: predict_calibrated(clf, calibrator_log, X),
            'Calibrated_Tree': lambda X: predict_calibrated(tree, calibrator_tree, X)
        }
        
        results = {}
        for m_name, pred_func in models.items():
            preds = pred_func(X_val)
            brier = brier_score_loss(y_val, preds)
            ll = log_loss(y_val, preds)
            
            # Expected Net Return Logic
            # E[R] approx = P(Up)*Avg_Up + P(Down)*Avg_Down
            # We use a simple expectation proxy
            win_prob = np.where(val_df['S3_Signal'] == 1, preds, 1 - preds)
            
            # Gross Expected = Win_Prob * mean(|R|) - Loss_Prob * mean(|R|)
            # For simplicity, let's use the actual mean magnitudes from training
            mean_up = train_df[train_df['R_1h_fwd'] > 0]['R_1h_fwd'].mean()
            mean_down = train_df[train_df['R_1h_fwd'] < 0]['R_1h_fwd'].mean()
            
            E_gross = np.where(val_df['S3_Signal'] == 1, 
                              preds * mean_up + (1-preds) * mean_down,
                              (1-preds) * np.abs(mean_down) - preds * mean_up)
                              
            E_net = E_gross - 0.0012 # 12 bps execution cost
            
            # Strategy: take trade only if E_net > 0
            trades_taken = E_net > 0
            if trades_taken.sum() > 0:
                realized_gross = (val_df.loc[trades_taken, 'R_1h_fwd'] * val_df.loc[trades_taken, 'S3_Signal']).mean()
                realized_net = realized_gross - 0.0012
            else:
                realized_net = 0
                
            results[m_name] = {
                'Brier': float(brier),
                'LogLoss': float(ll),
                'Trades_Taken': int(trades_taken.sum()),
                'Realized_Net_bps': float(realized_net * 10000)
            }
            
        return results

    ablation_results = {}
    print("Training A: S3 ONLY")
    ablation_results['A_S3_Only'] = train_and_eval(features_A, 'A')
    print("Training B: S3 + VOL")
    ablation_results['B_S3_Vol'] = train_and_eval(features_B, 'B')
    print("Training C: S3 + ALL")
    ablation_results['C_S3_All'] = train_and_eval(features_C, 'C')
    
    # Deterministic S3 Baseline
    baseline_gross = (val_df['R_1h_fwd'] * val_df['S3_Signal']).mean()
    baseline_net = baseline_gross - 0.0012
    
    final_output = {
        'Deterministic_S3_Net_bps': float(baseline_net * 10000),
        'Total_Validation_Events': len(val_df),
        'Ablation': ablation_results
    }
    
    with open(RESULTS_DIR / "probability_baseline_results.json", "w") as f:
        json.dump(final_output, f, indent=4)
        
    print("Complete. Results saved.")

if __name__ == "__main__":
    execute_engine()
