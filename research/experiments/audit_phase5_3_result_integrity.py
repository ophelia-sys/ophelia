import os
import json
import pickle
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import log_loss, brier_score_loss
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.pipeline.labels import LabelGenerator
from research.experiments.exp_phase5_3_ml_ablation import load_cvd_symbol, engineer_cvd_features, MODELS_CONFIG
from research.pipeline.validation import PurgedWalkForwardValidation

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def main():
    print("--- PHASE 5.3.1 CVD RESULT INTEGRITY AUDIT ---")
    
    with open(os.path.join(BASE_DIR, "PHASE5_3_OOS_PREDS.pkl"), "rb") as f:
        oos_store = pickle.load(f)
        
    df_raw = pd.read_json(os.path.join(BASE_DIR, "PHASE5_3_FINAL_RESULTS_RAW.json"))
    
    audit_results = {}
    
    # ----------------------------------------------------
    # 9. RESULT REPRODUCTION
    # ----------------------------------------------------
    print("Executing 9. Result Reproduction...")
    pooled_y = []
    pooled_p_aug = []
    pooled_p_base = []
    
    repro = {}
    for s in SYMBOLS:
        key = f"{s}_G"
        data = oos_store[key]
        y = data['y']
        p_aug = data['preds_aug']
        p_base = data['preds_base']
        
        ll_aug = log_loss(y, p_aug)
        ll_base = log_loss(y, p_base)
        br_aug = brier_score_loss(y, p_aug)
        br_base = brier_score_loss(y, p_base)
        
        repro[s] = {
            'll_base': ll_base, 'll_aug': ll_aug,
            'br_base': br_base, 'br_aug': br_aug
        }
        
        pooled_y.extend(y)
        pooled_p_aug.extend(p_aug)
        pooled_p_base.extend(p_base)
        
    p_y = np.array(pooled_y)
    p_p_aug = np.array(pooled_p_aug)
    p_p_base = np.array(pooled_p_base)
    
    repro['POOLED'] = {
        'll_base': log_loss(p_y, p_p_base),
        'll_aug': log_loss(p_y, p_p_aug),
        'br_base': brier_score_loss(p_y, p_p_base),
        'br_aug': brier_score_loss(p_y, p_p_aug)
    }
    
    def indep_dm_test(y, p1, p2, max_lag=59):
        loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p1)])
        loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p2)])
        d = loss1 - loss2
        if np.all(d == 0): return 0.0, 1.0
        model = sm.OLS(d, np.ones_like(d))
        res = model.fit(cov_type='HAC', cov_kwds={'maxlags': max_lag})
        return res.tvalues[0], res.pvalues[0]
        
    t, p = indep_dm_test(p_y, p_p_base, p_p_aug)
    repro['POOLED']['dm_tstat'] = t
    repro['POOLED']['dm_pval'] = p
    audit_results['REPRO'] = repro
    
    # ----------------------------------------------------
    # 7. ECONOMIC AUDIT
    # ----------------------------------------------------
    print("Executing 7. Economic Audit...")
    costs = [0, 5, 10, 15, 20, 25]
    eco = {}
    pool_R = []
    for s in SYMBOLS:
        pool_R.extend(oos_store[f"{s}_G"]['R_val'])
    pool_R = np.array(pool_R)
    
    def calc_eco(preds, r_val, cost):
        p90 = np.percentile(preds, 90)
        mask = preds >= p90
        trade_count = np.sum(mask)
        if trade_count == 0: return 0, 0, 0, 0
        gross_ret = np.mean(r_val[mask])
        net_ret = gross_ret - (cost / 10000.0)
        turnover = trade_count / len(preds)
        return gross_ret*10000, net_ret*10000, trade_count, turnover
        
    for c in costs:
        gb, nb, tcb, tb = calc_eco(p_p_base, pool_R, c)
        ga, na, tca, ta = calc_eco(p_p_aug, pool_R, c)
        eco[c] = {
            'BASE': {'gross': gb, 'net': nb, 'trades': int(tcb), 'turnover': tb},
            'MODEL_G': {'gross': ga, 'net': na, 'trades': int(tca), 'turnover': ta},
            'DELTA': {'gross': ga - gb, 'net': na - nb}
        }
    audit_results['ECONOMIC'] = eco

    # ----------------------------------------------------
    # 6. ABLATION RESULT AUDIT
    # ----------------------------------------------------
    print("Executing 6. Ablation Result Audit...")
    ablation = {}
    for mod in ["B", "C", "D", "E", "F", "G"]:
        df_mod = df_raw[df_raw['model'] == f"MODEL_{mod}"]
        df_base = df_raw[df_raw['model'] == f"BASE_MATCHED_{mod}"]
        if len(df_mod) > 0 and len(df_base) > 0:
            ll_mod = df_mod['log_loss'].mean()
            ll_base = df_base['log_loss'].mean()
            ablation[mod] = ll_base - ll_mod
    audit_results['ABLATION'] = ablation
    
    # ----------------------------------------------------
    # 5. CVD FEATURE IMPORTANCE
    # ----------------------------------------------------
    print("Executing 5. CVD Feature Importance...")
    loader = ResearchDataLoader()
    df_ohlcv = loader.load_symbol('BTCUSDT')
    baseline_exp = Phase5BaselineExperiment()
    df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
    df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
    df_ohlcv['R_60'] = df_ohlcv['gross_ret']
    df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
    df_cvd = load_cvd_symbol('BTCUSDT')
    df = engineer_cvd_features(df_ohlcv, df_cvd)
    
    base_f, cvd_f = MODELS_CONFIG['G']
    features_aug = base_f + cvd_f
    df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')]
    valid_df = df.dropna(subset=features_aug + ['target_60_up_10', 'R_60'])
    
    X = valid_df[features_aug].values
    y = valid_df['target_60_up_10'].values
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(valid_df)
    train_idx, test_idx = splits[0]
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X[train_idx])
    clf = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, penalty='l2')
    clf.fit(X_train, y[train_idx])
    
    coefs = {feat: float(coef) for feat, coef in zip(features_aug, clf.coef_[0])}
    audit_results['FEATURE_IMPORTANCE'] = coefs
    
    with open(os.path.join(BASE_DIR, 'research/experiments/audit_results.json'), 'w') as f:
        json.dump(audit_results, f, indent=2)
        
    print("Audit calculations complete.")

if __name__ == "__main__":
    main()
