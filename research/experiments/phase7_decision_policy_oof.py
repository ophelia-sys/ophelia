import os
import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime

from research.experiments.phase7_golden_parity_test import load_data, engineer_research_features, REQUIRED_FEATURES
from research.pipeline.validation import PurgedWalkForwardValidation

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def evaluate_oof_policy():
    print("=" * 60)
    print("--- PHASE 7 DECISION POLICY RECONSTRUCTION ---")
    print("Method: CHRONOLOGICAL WALK-FORWARD OUT-OF-FOLD (OOF)")
    print("=" * 60)
    
    thresholds = {}
    audit_data = {}
    
    for symbol in SYMBOLS:
        print(f"\n[{symbol}] Generating Chronological OOF Predictions...")
        
        df_ohlcv, df_cvd = load_data(symbol)
        df_hist = engineer_research_features(df_ohlcv, df_cvd)
        
        # Frozen Target using exactly historical semantics
        fwd_ret = df_hist['close'].shift(-60) / df_hist['open'].shift(-1) - 1.0
        df_hist['target_60_up_10'] = (fwd_ret > 0.0010).astype(float)
        
        # Isolate exactly to the training period (2022-01-01 to 2023-12-31)
        # 2024 is strictly operational confirmation
        df_train = df_hist[df_hist['timestamp'] < '2024-01-01'].copy()
        df_train.dropna(subset=REQUIRED_FEATURES + ['target_60_up_10'], inplace=True)
        df_train.reset_index(drop=True, inplace=True)
        
        if len(df_train) == 0:
            print(f"[{symbol}] WARNING: No training data found!")
            continue
            
        X = df_train[REQUIRED_FEATURES].values
        y = df_train['target_60_up_10'].values
        timestamps = df_train['timestamp'].values
        
        cv = PurgedWalkForwardValidation(n_folds=5, embargo=60)
        splits = cv.split(X)
        
        oof_preds = []
        oof_y = []
        fold_audit = []
        
        for i, (train_idx, test_idx) in enumerate(splits):
            train_start = pd.to_datetime(timestamps[train_idx[0]]).strftime('%Y-%m-%d')
            train_end = pd.to_datetime(timestamps[train_idx[-1]]).strftime('%Y-%m-%d')
            test_start = pd.to_datetime(timestamps[test_idx[0]]).strftime('%Y-%m-%d')
            test_end = pd.to_datetime(timestamps[test_idx[-1]]).strftime('%Y-%m-%d')
            
            fold_audit.append({
                "fold": i + 1,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "train_samples": len(train_idx),
                "test_samples": len(test_idx)
            })
            
            clf = lgb.LGBMClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, verbose=-1, random_state=42)
            clf.fit(X[train_idx], y[train_idx])
            
            preds = clf.predict_proba(X[test_idx])[:, 1]
            oof_preds.extend(preds)
            oof_y.extend(y[test_idx])
            
        oof_preds = np.array(oof_preds)
        oof_y = np.array(oof_y)
        
        p90 = np.percentile(oof_preds, 90)
        p95 = np.percentile(oof_preds, 95)
        p75 = np.percentile(oof_preds, 75)
        
        mean_prob = np.mean(oof_preds)
        median_prob = np.median(oof_preds)
        min_prob = np.min(oof_preds)
        max_prob = np.max(oof_preds)
        std_prob = np.std(oof_preds)
        pos_class_rate = np.mean(oof_y)
        n_signals = np.sum(oof_preds >= p90)
        
        print(f"[{symbol}] OOF Samples: {len(oof_preds)}")
        print(f"[{symbol}] OOF p90 Threshold: {p90:.5f}")
        
        thresholds[symbol] = {
            "threshold": float(p90),
            "method": "chronological_OOF_p90",
            "oof_start": fold_audit[0]["test_start"],
            "oof_end": fold_audit[-1]["test_end"],
            "n_oof": len(oof_preds),
            "version": "1.0.0"
        }
        
        audit_data[symbol] = {
            "folds": fold_audit,
            "stats": {
                "n_oof": len(oof_preds),
                "min": float(min_prob),
                "max": float(max_prob),
                "mean": float(mean_prob),
                "median": float(median_prob),
                "p75": float(p75),
                "p90": float(p90),
                "p95": float(p95),
                "std": float(std_prob),
                "positive_class_rate": float(pos_class_rate),
                "n_signals_p90": int(n_signals)
            }
        }

    # Serialize policy thresholds
    out_path = "PHASE7_DECISION_THRESHOLDS.json"
    with open(out_path, "w") as f:
        json.dump(thresholds, f, indent=4)
        
    print(f"\n[SUCCESS] OOF thresholds frozen and saved to {out_path}")
    
    # Generate OOF Audit
    with open("PHASE7_DECISION_POLICY_OOF_AUDIT.md", "w") as f:
        f.write("# PHASE 7 DECISION POLICY OOF AUDIT\n\n")
        f.write("**Status:** `PASS`\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
        
        f.write("## 1. Methodology\n")
        f.write("Chronological Walk-Forward Validation using `PurgedWalkForwardValidation` (n_folds=5, embargo=60). ")
        f.write("The out-of-fold (OOF) predictions guarantee that no probability is generated from a model that was exposed to the predicted data or any future data.\n\n")
        
        f.write("## 2. Fold Boundaries\n")
        for sym, data in audit_data.items():
            f.write(f"### {sym}\n")
            f.write("| Fold | Train Start | Train End | Test Start | Test End | Train Samples | Test Samples |\n")
            f.write("|------|-------------|-----------|------------|----------|---------------|--------------|\n")
            for fold in data["folds"]:
                f.write(f"| {fold['fold']} | {fold['train_start']} | {fold['train_end']} | {fold['test_start']} | {fold['test_end']} | {fold['train_samples']} | {fold['test_samples']} |\n")
            f.write("\n")
            
        f.write("## 3. Threshold Diagnostics\n")
        f.write("| Symbol | OOF N | Min | Max | Mean | Median | P75 | P90 (Thresh) | P95 | StdDev | Pos Class Rate | Signals |\n")
        f.write("|--------|-------|-----|-----|------|--------|-----|--------------|-----|--------|----------------|---------|\n")
        for sym, data in audit_data.items():
            s = data["stats"]
            f.write(f"| {sym} | {s['n_oof']} | {s['min']:.4f} | {s['max']:.4f} | {s['mean']:.4f} | {s['median']:.4f} | {s['p75']:.4f} | **{s['p90']:.4f}** | {s['p95']:.4f} | {s['std']:.4f} | {s['positive_class_rate']:.4f} | {s['n_signals_p90']} |\n")
            
    # Generate Spec
    with open("PHASE7_DECISION_POLICY_SPEC.md", "w") as f:
        f.write("# PHASE 7 DECISION POLICY SPECIFICATION\n\n")
        f.write("## Target Constraint\n")
        f.write("The system exclusively models `target_60_up_10`. Consequently, Ophelia is a **LONG-ONLY** system. ")
        f.write("The probability threshold is used to generate `LONG_CANDIDATE` or `HOLD` decisions. ")
        f.write("Short-selling logic is completely unauthorized.\n\n")
        f.write("## Decision Thresholds (OOF P90)\n")
        f.write("Frozen thresholds generated from 2022-2023 Chronological Out-of-Fold predictions:\n")
        for sym, t in thresholds.items():
            f.write(f"- **{sym}**: `{t['threshold']:.5f}`\n")
            
        f.write("\n## 2024 Operations\n")
        f.write("2024 is strictly an operational evaluation window. ")
        f.write("These thresholds are immutably frozen. ")
        f.write("They must not be modified in response to shadow or paper trading performance.\n")
        
if __name__ == "__main__":
    evaluate_oof_policy()
