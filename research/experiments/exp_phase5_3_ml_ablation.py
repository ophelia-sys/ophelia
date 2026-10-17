import os
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from numba import njit
from joblib import Parallel, delayed

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from sklearn.metrics import log_loss, brier_score_loss

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
YEARS = [2022, 2023]
MONTHS = list(range(1, 13))

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
CVD_DIR = os.path.join(BASE_DIR, 'research/data/normalized/cvd/5m')

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']

CVD_FEATS_B = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h']
CVD_FEATS_C = ['cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h']
CVD_FEATS_D = ['cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h']
CVD_FEATS_E = ['cvd_acceleration_15m', 'cvd_acceleration_1h']
CVD_FEATS_F = CVD_FEATS_C + CVD_FEATS_D + CVD_FEATS_E
CVD_FEATS_G = CVD_FEATS_B + CVD_FEATS_C + CVD_FEATS_D + CVD_FEATS_E

MODELS_CONFIG = {
    "A": (BASE_FEATS, []),
    "B": (BASE_FEATS, CVD_FEATS_B),
    "C": (BASE_FEATS, CVD_FEATS_C),
    "D": (BASE_FEATS, CVD_FEATS_D),
    "E": (BASE_FEATS, CVD_FEATS_E),
    "F": (BASE_FEATS, CVD_FEATS_F),
    "G": (BASE_FEATS, CVD_FEATS_G)
}

def load_cvd_symbol(symbol):
    dfs = []
    for year in YEARS:
        for month in MONTHS:
            path = os.path.join(CVD_DIR, f"{symbol}-{year}-{month:02d}.parquet")
            if os.path.exists(path):
                dfs.append(pd.read_parquet(path))
    if len(dfs) == 0:
        return pd.DataFrame(columns=['minute', 'delta_volume', 'buy_volume', 'sell_volume'])
    df = pd.concat(dfs, ignore_index=True)
    df.sort_values('minute', inplace=True)
    return df

def engineer_cvd_features(df_ohlcv, df_cvd):
    df_cvd = df_cvd.copy()
    
    df_cvd['cvd_delta_5m'] = df_cvd['delta_volume']
    df_cvd['cvd_delta_15m'] = df_cvd['cvd_delta_5m'].rolling(3).sum()
    df_cvd['cvd_delta_1h'] = df_cvd['cvd_delta_5m'].rolling(12).sum()
    
    buy_5m = df_cvd['buy_volume']
    sell_5m = df_cvd['sell_volume']
    buy_15m = buy_5m.rolling(3).sum()
    sell_15m = sell_5m.rolling(3).sum()
    buy_1h = buy_5m.rolling(12).sum()
    sell_1h = sell_5m.rolling(12).sum()
    
    df_cvd['cvd_imbalance_5m'] = df_cvd['cvd_delta_5m'] / (buy_5m + sell_5m + 1e-8)
    df_cvd['cvd_imbalance_15m'] = df_cvd['cvd_delta_15m'] / (buy_15m + sell_15m + 1e-8)
    df_cvd['cvd_imbalance_1h'] = df_cvd['cvd_delta_1h'] / (buy_1h + sell_1h + 1e-8)
    
    df_cvd['std_5m_raw'] = df_cvd['cvd_delta_5m'].rolling(288).std()
    df_cvd['std_15m_raw'] = df_cvd['cvd_delta_15m'].rolling(288).std()
    df_cvd['std_1h_raw'] = df_cvd['cvd_delta_1h'].rolling(288).std()
    
    mean_5m = df_cvd['cvd_delta_5m'].rolling(288).mean()
    mean_15m = df_cvd['cvd_delta_15m'].rolling(288).mean()
    mean_1h = df_cvd['cvd_delta_1h'].rolling(288).mean()
    
    df_cvd['cvd_zscore_5m'] = (df_cvd['cvd_delta_5m'] - mean_5m) / df_cvd['std_5m_raw']
    df_cvd['cvd_zscore_15m'] = (df_cvd['cvd_delta_15m'] - mean_15m) / df_cvd['std_15m_raw']
    df_cvd['cvd_zscore_1h'] = (df_cvd['cvd_delta_1h'] - mean_1h) / df_cvd['std_1h_raw']
    
    df_cvd['cvd_zscore_5m'] = np.where(df_cvd['std_5m_raw'] == 0.0, np.nan, df_cvd['cvd_zscore_5m'])
    df_cvd['cvd_zscore_15m'] = np.where(df_cvd['std_15m_raw'] == 0.0, np.nan, df_cvd['cvd_zscore_15m'])
    df_cvd['cvd_zscore_1h'] = np.where(df_cvd['std_1h_raw'] == 0.0, np.nan, df_cvd['cvd_zscore_1h'])
    
    df_cvd['cvd_acceleration_15m'] = df_cvd['cvd_delta_15m'] - df_cvd['cvd_delta_15m'].shift(3)
    df_cvd['cvd_acceleration_1h'] = df_cvd['cvd_delta_1h'] - df_cvd['cvd_delta_1h'].shift(12)
    
    # Now merge
    df_ohlcv = df_ohlcv.copy()
    if not np.issubdtype(df_ohlcv['timestamp'].dtype, np.datetime64):
        df_ohlcv['timestamp'] = pd.to_datetime(df_ohlcv['timestamp'], unit='ms')
        
    df = pd.merge(df_ohlcv, df_cvd, left_on='timestamp', right_on='minute', how='left')
    return df

def run_ml_pipeline(df, features_list, model_name, symbol):
    # Ensure no NaNs in requested features + target
    valid_df = df.dropna(subset=features_list + ['target_60_up_10', 'R_60'])
    
    X = valid_df[features_list].values
    y = valid_df['target_60_up_10'].values
    R = valid_df['R_60'].values
    timestamps = valid_df['timestamp'].values
    
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(valid_df)
    
    oof_preds = np.zeros(len(valid_df))
    oof_mask = np.zeros(len(valid_df), dtype=bool)
    
    clf = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, penalty='l2')
    
    for train_idx, test_idx in splits:
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X[train_idx])
        X_test = scaler.transform(X[test_idx])
        
        clf.fit(X_train, y[train_idx])
        oof_preds[test_idx] = clf.predict_proba(X_test)[:, 1]
        oof_mask[test_idx] = True
        
    y_val = y[oof_mask]
    preds = oof_preds[oof_mask]
    R_val = R[oof_mask]
    ts_val = timestamps[oof_mask]
    
    ll = log_loss(y_val, preds) if len(y_val) > 0 else np.nan
    brier = brier_score_loss(y_val, preds) if len(y_val) > 0 else np.nan
    
    # Cost Sweep ENR
    enr = {}
    if len(y_val) > 0:
        # Expected Net Return logic: Take top decile
        # Calculate gross return for trades in top decile of predicted probabilities
        p90 = np.percentile(preds, 90)
        trade_mask = preds >= p90
        gross_ret = np.mean(R_val[trade_mask]) if np.sum(trade_mask) > 0 else 0
        for cost in [0, 5, 10, 15, 20, 25]:
            enr[f'{cost}_bps'] = (gross_ret - (cost / 10000.0)) * 10000.0 # stored in bps
    
    res = {
        'symbol': symbol,
        'model': model_name,
        'log_loss': ll,
        'brier': brier,
        'enr': enr,
        'valid_samples': len(valid_df),
        'oos_samples': len(y_val),
        'y_val': y_val,
        'preds': preds,
        'ts_val': ts_val,
        'R_val': R_val
    }
    return res

def main():
    print("--- PHASE 5.3 CVD ML EXPERIMENT EXECUTION ---")
    
    loader = ResearchDataLoader()
    
    all_results = []
    oos_store = {}
    
    baseline_exp = Phase5BaselineExperiment()
    
    for symbol in SYMBOLS:
        print(f"Processing {symbol}...")
        df_ohlcv = loader.load_symbol(symbol)
        
        # Base features
        df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
        # Apply labels which creates 'gross_ret' which we use as R_60
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv['R_60'] = df_ohlcv['gross_ret']
        # The LabelGenerator target logic was 'target_60_up_10'
        # We need to make sure 'target_60_up_10' exists. Let's use LabelGenerator for the target.
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        # Filter strictly 2022-2023
        df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')]
        
        for mod_key, (base_f, cvd_f) in MODELS_CONFIG.items():
            print(f"  Running Model {mod_key}")
            features_aug = base_f + cvd_f
            res_aug = run_ml_pipeline(df, features_aug, f"MODEL_{mod_key}", symbol)
            
            valid_df = df.dropna(subset=features_aug + ['target_60_up_10', 'R_60'])
            
            X_base = valid_df[base_f].values
            y = valid_df['target_60_up_10'].values
            R = valid_df['R_60'].values
            timestamps = valid_df['timestamp'].values
            
            cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
            splits = cv.split(valid_df)
            
            fold_boundaries = []
            oof_preds = np.zeros(len(valid_df))
            oof_mask = np.zeros(len(valid_df), dtype=bool)
            clf = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, penalty='l2')
            
            for f_idx, (train_idx, test_idx) in enumerate(splits):
                fold_boundaries.append({
                    'fold': f_idx,
                    'train_start': str(timestamps[train_idx[0]]),
                    'train_end': str(timestamps[train_idx[-1]]),
                    'test_start': str(timestamps[test_idx[0]]),
                    'test_end': str(timestamps[test_idx[-1]]),
                    'train_samples': len(train_idx),
                    'test_samples': len(test_idx)
                })
                
                scaler = StandardScaler()
                X_train = scaler.fit_transform(X_base[train_idx])
                X_test = scaler.transform(X_base[test_idx])
                
                clf.fit(X_train, y[train_idx])
                oof_preds[test_idx] = clf.predict_proba(X_test)[:, 1]
                oof_mask[test_idx] = True
            
            y_val = y[oof_mask]
            preds_base = oof_preds[oof_mask]
            R_val = R[oof_mask]
            ts_val = timestamps[oof_mask]
            
            ll_base = log_loss(y_val, preds_base) if len(y_val) > 0 else np.nan
            brier_base = brier_score_loss(y_val, preds_base) if len(y_val) > 0 else np.nan
            
            enr_base = {}
            if len(y_val) > 0:
                p90 = np.percentile(preds_base, 90)
                trade_mask = preds_base >= p90
                gross_ret = np.mean(R_val[trade_mask]) if np.sum(trade_mask) > 0 else 0
                for cost in [0, 5, 10, 15, 20, 25]:
                    enr_base[f'{cost}_bps'] = (gross_ret - (cost / 10000.0)) * 10000.0
                    
            res_base = {
                'symbol': symbol,
                'model': f"BASE_MATCHED_{mod_key}",
                'log_loss': ll_base,
                'brier': brier_base,
                'enr': enr_base,
                'valid_samples': len(valid_df),
                'oos_samples': len(y_val),
                'fold_boundaries': fold_boundaries
            }
            
            # Regime calculation for Base and Aug
            # 2022
            mask_2022 = (ts_val >= np.datetime64('2022-01-01')) & (ts_val < np.datetime64('2023-01-01'))
            res_base['ll_2022'] = log_loss(y_val[mask_2022], preds_base[mask_2022]) if sum(mask_2022) > 0 else np.nan
            res_aug['ll_2022'] = log_loss(y_val[mask_2022], res_aug['preds'][mask_2022]) if sum(mask_2022) > 0 else np.nan
            
            # 2023
            mask_2023 = (ts_val >= np.datetime64('2023-01-01')) & (ts_val < np.datetime64('2024-01-01'))
            res_base['ll_2023'] = log_loss(y_val[mask_2023], preds_base[mask_2023]) if sum(mask_2023) > 0 else np.nan
            res_aug['ll_2023'] = log_loss(y_val[mask_2023], res_aug['preds'][mask_2023]) if sum(mask_2023) > 0 else np.nan
            
            res_aug['fold_boundaries'] = fold_boundaries
            all_results.append(res_base)
            
            oos_key = f"{symbol}_{mod_key}"
            oos_store[oos_key] = {
                'ts': ts_val,
                'y': y_val,
                'preds_aug': res_aug['preds'],
                'preds_base': preds_base,
                'R_val': R_val
            }
            
            del res_aug['y_val'], res_aug['preds'], res_aug['ts_val'], res_aug['R_val']
            all_results.append(res_aug)

    # Convert to dataframe
    df_res = pd.DataFrame(all_results)
    df_res.to_json(os.path.join(BASE_DIR, "PHASE5_3_FINAL_RESULTS_RAW.json"), orient="records", indent=2)
    print("Raw metrics generated and saved.")
    
    # Save OOS predictions to pickle for later analysis or debugging
    import pickle
    with open(os.path.join(BASE_DIR, "PHASE5_3_OOS_PREDS.pkl"), "wb") as f:
        pickle.dump(oos_store, f)

if __name__ == "__main__":
    main()
