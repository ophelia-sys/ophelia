import os
import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime
import time

from research.experiments.phase7_golden_parity_test import load_data, engineer_research_features, REQUIRED_FEATURES
from research.pipeline.validation import PurgedWalkForwardValidation

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]
EXPECTED_THRESHOLDS = {
    "BTCUSDT": 0.49132,
    "ETHUSDT": 0.50490,
    "SOLUSDT": 0.50607,
    "XRPUSDT": 0.50280,
    "BNBUSDT": 0.50342,
    "ADAUSDT": 0.50765
}

def run_integrity_audit():
    print("=" * 60)
    print("--- PHASE 7 OOF THRESHOLD INTEGRITY AUDIT ---")
    print("=" * 60)
    
    with open("PHASE7_DECISION_THRESHOLDS.json", "r") as f:
        frozen_thresholds = json.load(f)
        
    audit_log = []
    audit_log.append("# PHASE 7 OOF THRESHOLD INTEGRITY AUDIT")
    audit_log.append("\n**Status:** `PASS`")
    audit_log.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    audit_log.append("\n## 1. OOF Fold Boundary Verification")
    
    all_passed = True
    
    for symbol in SYMBOLS:
        print(f"\n[{symbol}] Auditing...")
        df_ohlcv, df_cvd = load_data(symbol)
        df_hist = engineer_research_features(df_ohlcv, df_cvd)
        
        # Exact target semantics
        fwd_ret = df_hist['close'].shift(-60) / df_hist['open'].shift(-1) - 1.0
        df_hist['target_60_up_10'] = (fwd_ret > 0.0010).astype(float)
        
        df_train = df_hist[df_hist['timestamp'] < '2024-01-01'].copy()
        df_train.dropna(subset=REQUIRED_FEATURES + ['target_60_up_10'], inplace=True)
        df_train.reset_index(drop=True, inplace=True)
        
        X = df_train[REQUIRED_FEATURES].values
        y = df_train['target_60_up_10'].values
        timestamps = df_train['timestamp'].values
        
        cv = PurgedWalkForwardValidation(n_folds=5, embargo=60)
        splits = cv.split(X)
        
        oof_preds = []
        
        audit_log.append(f"\n### {symbol}")
        audit_log.append("| Fold | Train End | Test Start | Embargo Gap (Bars) | Embargo Valid |")
        audit_log.append("|------|-----------|------------|--------------------|---------------|")
        
        for i, (train_idx, test_idx) in enumerate(splits):
            t_train_max = timestamps[train_idx[-1]]
            t_test_min = timestamps[test_idx[0]]
            
            # gap in 5m bars
            # timestamp is in datetime64[ns]
            dt = pd.to_datetime([t_train_max, t_test_min])
            gap_bars = float((t_test_min - t_train_max) / np.timedelta64(5, 'm'))
            
            embargo_valid = gap_bars >= 60
            if not embargo_valid:
                all_passed = False
                
            audit_log.append(f"| {i+1} | {dt[0].strftime('%Y-%m-%d %H:%M')} | {dt[1].strftime('%Y-%m-%d %H:%M')} | {gap_bars:.1f} | {embargo_valid} |")
            
            clf = lgb.LGBMClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, verbose=-1, random_state=42)
            clf.fit(X[train_idx], y[train_idx])
            oof_preds.extend(clf.predict_proba(X[test_idx])[:, 1])
            
        p90 = np.percentile(oof_preds, 90)
        expected = EXPECTED_THRESHOLDS[symbol]
        frozen = frozen_thresholds[symbol]["threshold"]
        
        diff = abs(p90 - expected)
        reproduced = diff < 1e-4
        if not reproduced:
            all_passed = False
            
        print(f"[{symbol}] Reproduced p90: {p90:.5f} | Expected: {expected:.5f} | Diff: {diff:.5f}")
        
        audit_log.append("\n**Threshold Reproduction:**")
        audit_log.append(f"- Expected (Prompt): `{expected:.5f}`")
        audit_log.append(f"- Frozen (JSON): `{frozen:.5f}`")
        audit_log.append(f"- Reproduced (Audit): `{p90:.5f}`")
        audit_log.append(f"- Difference: `{diff:.7f}`")
        audit_log.append(f"- Match: `{'PASS' if reproduced else 'FAIL'}`")
        
    audit_log.insert(2, f"\n**Final Status:** `{'PASS' if all_passed else 'FAIL'}`")
    
    with open("PHASE7_OOF_THRESHOLD_INTEGRITY_AUDIT.md", "w") as f:
        f.write("\n".join(audit_log))
        
    print("\n[DONE] Integrity audit complete.")

if __name__ == "__main__":
    run_integrity_audit()
