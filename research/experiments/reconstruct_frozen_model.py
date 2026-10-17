import os
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
import lightgbm as lgb
import hashlib
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.experiments.exp_phase5_3_ml_ablation import engineer_cvd_features
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.pipeline.models import LightGBMWrapper
from research.pipeline.labels import LabelGenerator

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
V2_DIR = os.path.join(BASE_DIR, 'data/normalized/v2')
RESULTS_DIR = os.path.join(BASE_DIR, 'research/results')

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
CVD_FEATS_G = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h',
               'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
               'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
               'cvd_acceleration_15m', 'cvd_acceleration_1h']

P4_FEATS = ['large_trade_imbalance', 'large_trade_share', 'trade_size_zscore', 'trade_size_concentration']
P4_DIR = os.path.join(BASE_DIR, 'research/data/normalized/p4')

REQUIRED_FEATURES = BASE_FEATS + CVD_FEATS_G

def load_cvd_symbol(symbol):
    dfs = []
    cvd_dir = os.path.join(BASE_DIR, 'research/data/normalized/cvd/5m')
    for year in [2022, 2023, 2024]:
        for month in range(1, 13):
            path = os.path.join(cvd_dir, f"{symbol}-{year}-{month:02d}.parquet")
            if os.path.exists(path):
                dfs.append(pd.read_parquet(path))
    if len(dfs) == 0:
        return pd.DataFrame(columns=['minute', 'delta_volume', 'buy_volume', 'sell_volume'])
    df = pd.concat(dfs, ignore_index=True)
    df.sort_values('minute', inplace=True)
    return df

def generate_frozen_target(df):
    """
    Frozen target semantics:
    ForwardReturn_t = Close[t+60] / Open[t+1] - 1
    y_t = 1 if ForwardReturn_t > 0.0010 else 0
    """
    df = df.copy()
    fwd_ret = df['close'].shift(-60) / df['open'].shift(-1) - 1.0
    df['target_60_up_10'] = (fwd_ret > 0.0010).astype(float)
    return df

def reconstruct_and_verify():
    print(f"=======================================================")
    print(f"--- RECONSTRUCTING PHASE 6.5 FROZEN MODELS ---")
    print(f"=======================================================\n")
    
    baseline_exp = Phase5BaselineExperiment()
    
    # Load historical OOS predictions
    oos_preds_path = os.path.join(RESULTS_DIR, 'phase6_5_p4_2024_oos_preds.pkl')
    if os.path.exists(oos_preds_path):
        with open(oos_preds_path, 'rb') as f:
            historical_preds = pickle.load(f)
    else:
        historical_preds = {}
        
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        
        v2_path_old = os.path.join(V2_DIR, f"binance_um_{symbol.lower()}_5m_v2.parquet")
        v2_path_2024 = os.path.join(V2_DIR, f"binance_um_{symbol.lower()}_5m_2024.parquet")
        
        df_old = pd.read_parquet(v2_path_old) if os.path.exists(v2_path_old) else pd.DataFrame()
        df_2024 = pd.read_parquet(v2_path_2024) if os.path.exists(v2_path_2024) else pd.DataFrame()
        
        if df_old.empty and df_2024.empty:
            print(f"  [SKIP] No data found for {symbol}.")
            continue
            
        df_sym = pd.concat([df_old, df_2024], ignore_index=True)
        df_sym = df_sym.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
        
        if not pd.api.types.is_datetime64_any_dtype(df_sym['timestamp']):
            df_sym['timestamp'] = pd.to_datetime(df_sym['timestamp'], unit='ms')
            
        # BASE features
        df_sym = baseline_exp.engineer_features(df_sym)
        
        # Frozen Target using historical functions to ensure exact matching
        df_sym = baseline_exp.apply_labels(df_sym, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_sym['R_60'] = df_sym['gross_ret']
        df_sym = LabelGenerator.generate_labels(df_sym, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df_main = engineer_cvd_features(df_sym, df_cvd)
        
        # Merge P4 to match exactly the historical `dropna`
        p4_path = os.path.join(P4_DIR, f"{symbol}_p4_features.parquet")
        if os.path.exists(p4_path):
            df_p4 = pd.read_parquet(p4_path)
            if not pd.api.types.is_datetime64_any_dtype(df_p4['timestamp']):
                df_p4['timestamp'] = pd.to_datetime(df_p4['timestamp'], unit='ms')
            df_p4 = df_p4[['timestamp'] + P4_FEATS]
            df_main = pd.merge(df_main, df_p4, on='timestamp', how='left')
            features_test = REQUIRED_FEATURES + P4_FEATS
        else:
            features_test = REQUIRED_FEATURES
        
        # Train / Test split
        train_df = df_main[(df_main['timestamp'] >= '2022-01-01') & (df_main['timestamp'] < '2024-01-01')].copy()
        test_df = df_main[(df_main['timestamp'] >= '2024-01-01') & (df_main['timestamp'] < '2025-01-01')].copy()
        
        # Dropna based on exactly the historical feature set + target
        all_required = features_test + ['target_60_up_10', 'R_60']
        
        train_df = train_df.dropna(subset=all_required).reset_index(drop=True)
        test_df = test_df.dropna(subset=all_required).reset_index(drop=True)
        
        if len(train_df) == 0:
            print(f"  [SKIP] 0 valid samples in Train for {symbol}")
            continue
            
        X_train = train_df[REQUIRED_FEATURES].values
        y_train = train_df['target_60_up_10'].values
        
        X_test = test_df[REQUIRED_FEATURES].values
        ts_test = test_df['timestamp'].values
        
        # Train model exactly as in history
        clf = lgb.LGBMClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, verbose=-1, random_state=42)
        clf.fit(X_train, y_train)
        
        # Predict on OOS
        if len(X_test) > 0:
            p_test = clf.predict_proba(X_test)[:, 1]
        else:
            p_test = np.array([])
            
        # Validation Oracle
        if symbol in historical_preds:
            hist_p = historical_preds[symbol]['p_base']
            hist_y = historical_preds[symbol]['y']
            hist_ts = historical_preds[symbol].get('ts', None)
            
            print(f"  --- PARITY VERIFICATION ({symbol}) ---")
            print(f"  Sample Count: Reconstructed = {len(p_test)}, Historical = {len(hist_p)}")
            
            if len(p_test) != len(hist_p):
                print("  [FAIL] Sample count mismatch.")
                # We won't exit yet to see other symbols, but we will not serialize
                parity_pass = False
            else:
                diffs = np.abs(p_test - hist_p)
                max_abs_error = np.max(diffs)
                mean_abs_error = np.mean(diffs)
                median_abs_error = np.median(diffs)
                p99_abs_error = np.percentile(diffs, 99)
                mismatches = np.sum(~np.isclose(p_test, hist_p, rtol=1e-7, atol=1e-8))
                corr = np.corrcoef(p_test, hist_p)[0, 1]
                
                print(f"  Max Abs Error: {max_abs_error:.4e}")
                print(f"  Mean Abs Error: {mean_abs_error:.4e}")
                print(f"  Median Abs Error: {median_abs_error:.4e}")
                print(f"  P99 Abs Error: {p99_abs_error:.4e}")
                print(f"  Correlation: {corr:.6f}")
                print(f"  Mismatch Count (atol=1e-8, rtol=1e-7): {mismatches}")
                
                parity_pass = (mismatches == 0 and mean_abs_error <= 1e-7)
                
                if hist_ts is not None:
                    # check timestamp equality
                    ts_match = np.array_equal(ts_test, hist_ts)
                    print(f"  Timestamp Equality: {ts_match}")
                    if not ts_match:
                        parity_pass = False
                
                if not parity_pass:
                    print(f"  [FATAL] Parity check failed for {symbol}.")
                    sys.exit(1)
                else:
                    print(f"  [PASS] Numerical parity achieved for {symbol}.")
        else:
            print(f"  No historical oracle found for {symbol}. (Expected for {symbol})")
            parity_pass = True
            
        if parity_pass:
            # Serialize Model
            model_hash = hashlib.sha256(pickle.dumps(clf)).hexdigest()
            artifact = {
                "symbol": symbol,
                "model_version": "1.0.0",
                "artifact_hash": model_hash,
                "creation_timestamp": datetime.utcnow().isoformat() + "Z",
                "lineage": {
                    "source_experiment": "exp_phase6_5_2024_confirmation.py",
                    "training_window": ["2022-01-01", "2023-12-31"],
                    "lightgbm_version": lgb.__version__,
                    "random_seed": 42
                },
                "feature_contract": {
                    "features": REQUIRED_FEATURES,
                    "preprocessing": "None",
                    "missing_value_policy": "dropna"
                },
                "model_object": clf
            }
            
            out_path = os.path.join(BASE_DIR, f"PHASE7_MODEL_FROZEN_{symbol}.pkl")
            with open(out_path, 'wb') as f:
                pickle.dump(artifact, f)
            print(f"  [SUCCESS] Serialized {symbol} artifact to {out_path}")

if __name__ == "__main__":
    reconstruct_and_verify()
