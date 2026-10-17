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
from research.ml4t_benchmark.features.hmm import FoldLocalHMM
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
    print("--- PHASE 6.1 STAGE D HMM ML EXPERIMENT ---")
    
    # GAP POLICY DOCUMENTATION:
    # Rule B: NaN for that timestamp. 
    # If the HMM inputs (ret_1, realized_vol_20) are NaN, the HMM output probabilities will be NaN.
    # The LightGBM model naturally handles NaNs during training and prediction.
    
    loader = ResearchDataLoader()
    baseline_exp = Phase5BaselineExperiment()
    
    all_results = []
    oos_store = {}
    
    pooled_y = []
    pooled_p_base = []
    pooled_p_test = []
    pooled_r = []
    
    hmm_diagnostics = []
    
    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")
        df_ohlcv = baseline_exp.load_data(symbol)
        df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
        
        # Frozen Target
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv['R_60'] = df_ohlcv['gross_ret']
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        # CVD Features
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        df['orig_idx'] = np.arange(len(df))
        
        # Date filter strictly 2022-2023 for validation loop
        valid_df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')].copy()
        valid_df = valid_df.dropna(subset=BASE_FEATS + CVD_FEATS_G + ['target_60_up_10', 'R_60'])
        valid_df = valid_df.reset_index(drop=True)
        
        features_base = BASE_FEATS + CVD_FEATS_G
        features_test = BASE_FEATS + CVD_FEATS_G + ['hmm_prob_low_vol', 'hmm_prob_high_vol']
        
        X_base = valid_df[features_base].values
        X_test_folds = np.full((len(valid_df), len(features_test)), np.nan, dtype=np.float64)
        X_test_folds[:, :len(features_base)] = X_base
        
        hmm_low_col = len(features_base)
        hmm_high_col = len(features_base) + 1
        
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
            ret_1_idx = features_base.index('ret_1')
            rv_20_idx = features_base.index('realized_vol_20')
            
            X_hmm_train = X_base[train_idx][:, [ret_1_idx, rv_20_idx]]
            
            hmm = FoldLocalHMM(n_states=2, random_state=42)
            hmm.fit(X_hmm_train)
            
            X_hmm_full = X_base[:test_idx[-1] + 1][:, [ret_1_idx, rv_20_idx]]
            full_probs = hmm.filter_probabilities(X_hmm_full)
            
            probs_train = full_probs[train_idx]
            probs_test = full_probs[test_idx]
            
            X_test_folds[train_idx, hmm_low_col] = probs_train[:, 0]
            X_test_folds[train_idx, hmm_high_col] = probs_train[:, 1]
            
            X_test_folds[test_idx, hmm_low_col] = probs_test[:, 0]
            X_test_folds[test_idx, hmm_high_col] = probs_test[:, 1]
            
            fold_boundaries.append({
                'fold': f_idx,
                'train_start': str(timestamps[train_idx[0]]),
                'train_end': str(timestamps[train_idx[-1]]),
                'test_start': str(timestamps[test_idx[0]]),
                'test_end': str(timestamps[test_idx[-1]]),
                'train_samples': len(train_idx),
                'test_samples': len(test_idx),
                'hmm_covar_0': np.trace(hmm.model.covars_[0]),
                'hmm_covar_1': np.trace(hmm.model.covars_[1])
            })
            
            # Base Model (LightGBM)
            clf_base = LightGBMWrapper()
            clf_base.fit(X_base[train_idx], y[train_idx])
            oof_preds_base[test_idx] = clf_base.predict_proba(X_base[test_idx])[:, 1]
            
            # Test Model (LightGBM + HMM)
            clf_test = LightGBMWrapper()
            clf_test.fit(X_test_folds[train_idx], y[train_idx])
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
        
        from sklearn.linear_model import LogisticRegression
        def get_calibration(y_true, p_pred):
            try:
                lr = LogisticRegression()
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
        diag_low = X_test_folds[oof_mask, hmm_low_col]
        diag_high = X_test_folds[oof_mask, hmm_high_col]
        
        hmm_diagnostics.append({
            'symbol': symbol,
            'low_mean': float(np.nanmean(diag_low)),
            'low_std': float(np.nanstd(diag_low)),
            'low_min': float(np.nanmin(diag_low)),
            'low_max': float(np.nanmax(diag_low)),
            'low_nan': int(np.sum(np.isnan(diag_low))),
            'low_inf': int(np.sum(np.isinf(diag_low))),
            'low_zero_var': bool(np.nanstd(diag_low) == 0),
            
            'high_mean': float(np.nanmean(diag_high)),
            'high_std': float(np.nanstd(diag_high)),
            'high_min': float(np.nanmin(diag_high)),
            'high_max': float(np.nanmax(diag_high)),
            'high_nan': int(np.sum(np.isnan(diag_high))),
            'high_inf': int(np.sum(np.isinf(diag_high))),
            'high_zero_var': bool(np.nanstd(diag_high) == 0),
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
        'diagnostics': hmm_diagnostics
    }
    
    res_dir = os.path.join(BASE_DIR, 'research/results')
    os.makedirs(res_dir, exist_ok=True)
    with open(os.path.join(res_dir, 'phase6_1_stage_d_hmm_results.json'), 'w') as f:
        json.dump(final_json, f, indent=2)
        
    with open(os.path.join(res_dir, 'phase6_1_stage_d_hmm_oos_preds.pkl'), 'wb') as f:
        pickle.dump(oos_store, f)
        
    print("\nHMM Benchmark Execution Complete. Metrics and OOS predictions saved.")
    
if __name__ == "__main__":
    main()
