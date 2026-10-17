import os
import json
import numpy as np
import pandas as pd
import pickle
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.pipeline.models import LightGBMWrapper
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.experiments.exp_phase5_3_ml_ablation import load_cvd_symbol, engineer_cvd_features
from research.experiments.exp_phase5_3_ml_stats import dm_test, block_bootstrap, block_permutation, calculate_logloss
from research.ml4t_benchmark.features.kalman import apply_kalman_local_linear, select_fold_local_qr
from sklearn.metrics import log_loss, brier_score_loss

# Frozen configuration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

BASE_FEATS = ['ret_1', 'ret_3', 'ret_5', 'realized_vol_20', 'atr_pct_14', 'mom_10', 'vol_ratio']
CVD_FEATS_G = ['cvd_delta_5m', 'cvd_delta_15m', 'cvd_delta_1h', 
               'cvd_imbalance_5m', 'cvd_imbalance_15m', 'cvd_imbalance_1h',
               'cvd_zscore_5m', 'cvd_zscore_15m', 'cvd_zscore_1h',
               'cvd_acceleration_15m', 'cvd_acceleration_1h']

def get_enr(preds, r_val, cost):
    p90 = np.percentile(preds, 90)
    mask = preds >= p90
    gr = np.mean(r_val[mask]) if np.sum(mask) > 0 else 0
    return (gr - (cost / 10000.0)) * 10000.0

def main():
    print("--- PHASE 6.1 STAGE C KALMAN ML EXPERIMENT ---")
    
    loader = ResearchDataLoader()
    baseline_exp = Phase5BaselineExperiment()
    
    # Pre-registered compact Q/R grid
    # Fast, Medium, Slow adaptability
    qr_grid = [
        {"observation_noise": 1.0, "level_noise": 0.1, "slope_noise": 0.01},   # Fast
        {"observation_noise": 1.0, "level_noise": 0.01, "slope_noise": 0.001},  # Medium
        {"observation_noise": 1.0, "level_noise": 0.001, "slope_noise": 0.0001} # Slow
    ]
    
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    kalman_diagnostics = []
    
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        df_ohlcv = baseline_exp.load_data(symbol)
        df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
        
        # Frozen Target: target_60_up_10
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv['R_60'] = df_ohlcv['gross_ret']
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        df['log_close'] = np.log(df['close'].astype(float))
        df['orig_idx'] = np.arange(len(df))
        
        full_prices = df['log_close'].values
        
        # Date filter strictly 2022-2023 for validation loop
        valid_df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')].copy()
        valid_df = valid_df.dropna(subset=BASE_FEATS + CVD_FEATS_G + ['target_60_up_10', 'R_60'])
        valid_df = valid_df.reset_index(drop=True)
        
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + ['kalman_slope', 'kalman_innovation', 'kalman_uncertainty']
        
        X_base = valid_df[features_base].values
        # X_test will be built dynamically because kalman features depend on the fold Q/R
        X_test_folds = np.full((len(valid_df), len(features_test)), np.nan, dtype=np.float64)
        X_test_folds[:, :len(features_base)] = X_base
        
        kalman_slope_col = len(features_base)
        kalman_inn_col = len(features_base) + 1
        kalman_unc_col = len(features_base) + 2
        
        y = valid_df['target_60_up_10'].values
        R = valid_df['R_60'].values
        timestamps = valid_df['timestamp'].values
        
        cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
        splits = list(cv.split(valid_df))
        
        oof_preds_base = np.zeros(len(valid_df))
        oof_preds_test = np.zeros(len(valid_df))
        oof_mask = np.zeros(len(valid_df), dtype=bool)
        
        fold_boundaries = []
        
        for f_idx, (train_idx, test_idx) in enumerate(splits):
            train_end_orig_idx = valid_df['orig_idx'].iloc[train_idx[-1]]
            test_end_orig_idx = valid_df['orig_idx'].iloc[test_idx[-1]]
            
            prices_train_full = full_prices[:train_end_orig_idx + 1]
            best_config = select_fold_local_qr(prices_train_full, qr_grid, validation_fraction=0.2)
            print(f"  {symbol} Fold {f_idx} Selected Q/R: {best_config}")
            
            prices_test_full = full_prices[:test_end_orig_idx + 1]
            slopes, innovations, uncertainties = apply_kalman_local_linear(
                prices_test_full,
                best_config['observation_noise'],
                best_config['level_noise'],
                best_config['slope_noise']
            )
            
            # Map features back to valid_df for the train and test indices of this fold
            fold_orig_indices = valid_df['orig_idx'].values
            
            X_test_folds[train_idx, kalman_slope_col] = slopes[fold_orig_indices[train_idx]]
            X_test_folds[train_idx, kalman_inn_col] = innovations[fold_orig_indices[train_idx]]
            X_test_folds[train_idx, kalman_unc_col] = uncertainties[fold_orig_indices[train_idx]]
            
            X_test_folds[test_idx, kalman_slope_col] = slopes[fold_orig_indices[test_idx]]
            X_test_folds[test_idx, kalman_inn_col] = innovations[fold_orig_indices[test_idx]]
            X_test_folds[test_idx, kalman_unc_col] = uncertainties[fold_orig_indices[test_idx]]
            
            fold_boundaries.append({
                'fold': f_idx,
                'train_start': str(timestamps[train_idx[0]]),
                'train_end': str(timestamps[train_idx[-1]]),
                'test_start': str(timestamps[test_idx[0]]),
                'test_end': str(timestamps[test_idx[-1]]),
                'train_samples': len(train_idx),
                'test_samples': len(test_idx),
                'selected_qr': best_config
            })
            
            # Extract current fold's matrices
            X_train_base = X_base[train_idx]
            X_train_test = X_test_folds[train_idx]
            
            # Base Model (LightGBM)
            clf_base = LightGBMWrapper()
            clf_base.fit(X_train_base, y[train_idx])
            oof_preds_base[test_idx] = clf_base.predict_proba(X_base[test_idx])[:, 1]
            
            # Test Model (LightGBM + Kalman)
            clf_test = LightGBMWrapper()
            clf_test.fit(X_train_test, y[train_idx])
            oof_preds_test[test_idx] = clf_test.predict_proba(X_test_folds[test_idx])[:, 1]
            
            oof_mask[test_idx] = True
            
        y_val = y[oof_mask]
        p_base = oof_preds_base[oof_mask]
        p_test = oof_preds_test[oof_mask]
        R_val = R[oof_mask]
        ts_val = timestamps[oof_mask]
        
        assert len(y_val) == len(p_base) == len(p_test)
        print(f"SUCCESS: {symbol} Test arrays matched exactly: N = {len(y_val)}")
        
        pooled_y.extend(y_val)
        pooled_p_base.extend(p_base)
        pooled_p_test.extend(p_test)
        pooled_r.extend(R_val)
        
        ll_base = log_loss(y_val, p_base)
        ll_test = log_loss(y_val, p_test)
        
        br_base = brier_score_loss(y_val, p_base)
        br_test = brier_score_loss(y_val, p_test)
        
        dm_t, dm_p = dm_test(y_val, p_base, p_test, max_lag=59)
        perm_pval = block_permutation(y_val, p_base, p_test)
        
        loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_val, p_base)])
        loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y_val, p_test)])
        boot_mean, (boot_lo, boot_hi) = block_bootstrap(loss1, loss2)
        
        mask_2022 = (ts_val >= np.datetime64('2022-01-01')) & (ts_val < np.datetime64('2023-01-01'))
        mask_2023 = (ts_val >= np.datetime64('2023-01-01')) & (ts_val < np.datetime64('2024-01-01'))
        
        ll_base_22 = log_loss(y_val[mask_2022], p_base[mask_2022]) if sum(mask_2022) > 0 else np.nan
        ll_test_22 = log_loss(y_val[mask_2022], p_test[mask_2022]) if sum(mask_2022) > 0 else np.nan
        ll_base_23 = log_loss(y_val[mask_2023], p_base[mask_2023]) if sum(mask_2023) > 0 else np.nan
        ll_test_23 = log_loss(y_val[mask_2023], p_test[mask_2023]) if sum(mask_2023) > 0 else np.nan
        
        enr_base = {c: get_enr(p_base, R_val, c) for c in [0, 5, 10, 15, 20, 25]}
        enr_test = {c: get_enr(p_test, R_val, c) for c in [0, 5, 10, 15, 20, 25]}
        
        # Calculate calibration slope/intercept
        from sklearn.linear_model import LogisticRegression
        def get_calibration(y_true, p_pred):
            try:
                lr = LogisticRegression()
                # Logit transform to compute slope and intercept properly
                p_pred = np.clip(p_pred, 1e-7, 1-1e-7)
                logit_p = np.log(p_pred / (1 - p_pred))
                lr.fit(logit_p.reshape(-1, 1), y_true)
                return lr.coef_[0][0], lr.intercept_[0]
            except Exception:
                return np.nan, np.nan
                
        cal_slope_base, cal_int_base = get_calibration(y_val, p_base)
        cal_slope_test, cal_int_test = get_calibration(y_val, p_test)
        
        all_results.append({
            'symbol': symbol,
            'logloss_base': ll_base,
            'logloss_test': ll_test,
            'brier_base': br_base,
            'brier_test': br_test,
            'cal_slope_base': cal_slope_base,
            'cal_int_base': cal_int_base,
            'cal_slope_test': cal_slope_test,
            'cal_int_test': cal_int_test,
            'dm_tstat': dm_t,
            'dm_pval': dm_p,
            'perm_pval': perm_pval,
            'boot_mean': boot_mean,
            'boot_lo': boot_lo,
            'boot_hi': boot_hi,
            'enr_base': enr_base,
            'enr_test': enr_test,
            'll_base_2022': ll_base_22,
            'll_test_2022': ll_test_22,
            'll_base_2023': ll_base_23,
            'll_test_2023': ll_test_23,
            'samples': len(y_val)
        })
        
        # Diagnostics
        diag_sl = X_test_folds[oof_mask, kalman_slope_col]
        diag_in = X_test_folds[oof_mask, kalman_inn_col]
        diag_un = X_test_folds[oof_mask, kalman_unc_col]
        
        kalman_diagnostics.append({
            'symbol': symbol,
            'slope_mean': np.nanmean(diag_sl),
            'slope_std': np.nanstd(diag_sl),
            'slope_min': np.nanmin(diag_sl),
            'slope_max': np.nanmax(diag_sl),
            'slope_nan': int(np.sum(np.isnan(diag_sl))),
            'slope_inf': int(np.sum(np.isinf(diag_sl))),
            'slope_zero_var': bool(np.nanstd(diag_sl) == 0),
            
            'inn_mean': np.nanmean(diag_in),
            'inn_std': np.nanstd(diag_in),
            'inn_min': np.nanmin(diag_in),
            'inn_max': np.nanmax(diag_in),
            'inn_nan': int(np.sum(np.isnan(diag_in))),
            'inn_inf': int(np.sum(np.isinf(diag_in))),
            'inn_zero_var': bool(np.nanstd(diag_in) == 0),
            
            'unc_mean': np.nanmean(diag_un),
            'unc_std': np.nanstd(diag_un),
            'unc_min': np.nanmin(diag_un),
            'unc_max': np.nanmax(diag_un),
            'unc_nan': int(np.sum(np.isnan(diag_un))),
            'unc_inf': int(np.sum(np.isinf(diag_un))),
            'unc_zero_var': bool(np.nanstd(diag_un) == 0),
            'fold_boundaries': fold_boundaries
        })
        
        oos_store[symbol] = {
            'ts': ts_val,
            'y': y_val,
            'p_base': p_base,
            'p_test': p_test,
            'R_val': R_val
        }

    df_res = pd.DataFrame(all_results)
    
    from statsmodels.stats.multitest import multipletests
    _, bh_pvals, _, _ = multipletests(df_res['dm_pval'], alpha=0.05, method='fdr_bh')
    df_res['bh_qval'] = bh_pvals
    
    pool_y = np.array(pooled_y)
    pool_pb = np.array(pooled_p_base)
    pool_pt = np.array(pooled_p_test)
    pool_r = np.array(pooled_r)
    
    pool_ll_base = calculate_logloss(pool_y, pool_pb)
    pool_ll_test = calculate_logloss(pool_y, pool_pt)
    pool_br_base = brier_score_loss(pool_y, pool_pb)
    pool_br_test = brier_score_loss(pool_y, pool_pt)
    pool_dm_t, pool_dm_p = dm_test(pool_y, pool_pb, pool_pt, max_lag=59)
    
    pool_enr_base = {c: get_enr(pool_pb, pool_r, c) for c in [0, 5, 10, 15, 20, 25]}
    pool_enr_test = {c: get_enr(pool_pt, pool_r, c) for c in [0, 5, 10, 15, 20, 25]}
    
    cal_slope_pool_base, cal_int_pool_base = get_calibration(pool_y, pool_pb)
    cal_slope_pool_test, cal_int_pool_test = get_calibration(pool_y, pool_pt)
    
    final_json = {
        'pooled': {
            'logloss_base': pool_ll_base,
            'logloss_test': pool_ll_test,
            'brier_base': pool_br_base,
            'brier_test': pool_br_test,
            'cal_slope_base': cal_slope_pool_base,
            'cal_int_base': cal_int_pool_base,
            'cal_slope_test': cal_slope_pool_test,
            'cal_int_test': cal_int_pool_test,
            'dm_tstat': pool_dm_t,
            'dm_pval': pool_dm_p,
            'enr_base': pool_enr_base,
            'enr_test': pool_enr_test,
            'samples': len(pool_y)
        },
        'per_symbol': df_res.to_dict(orient="records"),
        'diagnostics': kalman_diagnostics
    }
    
    res_dir = os.path.join(BASE_DIR, 'research/results')
    os.makedirs(res_dir, exist_ok=True)
    with open(os.path.join(res_dir, 'phase6_1_stage_c_kalman_results.json'), 'w') as f:
        json.dump(final_json, f, indent=2)
        
    with open(os.path.join(res_dir, 'phase6_1_stage_c_kalman_oos_preds.pkl'), 'wb') as f:
        pickle.dump(oos_store, f)
        
    print("\nBenchmark Execution Complete. Metrics and OOS predictions saved.")
    
if __name__ == "__main__":
    main()
