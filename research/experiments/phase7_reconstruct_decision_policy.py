import os
import json
import pandas as pd
import numpy as np
import pickle
from datetime import datetime

# We will reuse the same feature engineering logic from the parity test script
from phase7_golden_parity_test import load_data, engineer_research_features, REQUIRED_FEATURES

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def reconstruct_policy():
    print("=" * 60)
    print("--- PHASE 7 DECISION POLICY RECONSTRUCTION ---")
    print("Method A: TRAIN-ONLY FIXED QUANTILE")
    print("=" * 60)
    
    thresholds = {}
    
    for symbol in SYMBOLS:
        print(f"\n[{symbol}] Processing training distribution...")
        
        # Load all available data
        df_ohlcv, df_cvd = load_data(symbol)
        
        # Engineer features
        df_hist = engineer_research_features(df_ohlcv, df_cvd)
        
        # Isolate exactly to the training period (2022-01-01 to 2023-12-31)
        # Note: 2024 is STRICTLY OOS and must not be used for threshold selection
        df_train = df_hist[df_hist['timestamp'] < '2024-01-01'].copy()
        
        if len(df_train) == 0:
            print(f"[{symbol}] WARNING: No training data found!")
            continue
            
        print(f"[{symbol}] Training samples available: {len(df_train)}")
        
        # Load frozen model artifact
        model_path = f"PHASE7_MODEL_FROZEN_{symbol}.pkl"
        if not os.path.exists(model_path):
            print(f"[{symbol}] ERROR: Model {model_path} not found.")
            continue
            
        with open(model_path, "rb") as f:
            artifact = pickle.load(f)
            
        clf = artifact["model_object"]
        
        # Generate predictions on the training set
        X_train = df_train[REQUIRED_FEATURES].values
        probs_train = clf.predict_proba(X_train)[:, 1]
        
        # Calculate 90th percentile of TRAINING distribution
        p90_train = np.percentile(probs_train, 90)
        
        # Verify basic distribution stats
        mean_prob = np.mean(probs_train)
        median_prob = np.median(probs_train)
        
        print(f"[{symbol}] Train Mean Prob:   {mean_prob:.5f}")
        print(f"[{symbol}] Train Median Prob: {median_prob:.5f}")
        print(f"[{symbol}] Train p90 Thresh:  {p90_train:.5f}")
        
        thresholds[symbol] = {
            "p90_threshold": float(p90_train),
            "train_samples": len(df_train),
            "train_mean_prob": float(mean_prob),
            "calculated_at": datetime.utcnow().isoformat()
        }

    # Serialize policy thresholds
    out_path = "PHASE7_DECISION_THRESHOLDS.json"
    with open(out_path, "w") as f:
        json.dump(thresholds, f, indent=4)
        
    print(f"\n[SUCCESS] Causal thresholds frozen and saved to {out_path}")
    
    # Generate the Markdown Report
    with open("PHASE7_CAUSAL_DECISION_POLICY_RECONSTRUCTION.md", "w") as f:
        f.write("# PHASE 7 CAUSAL DECISION POLICY RECONSTRUCTION\n\n")
        f.write("**Status:** `RECONSTRUCTED`\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
        
        f.write("## 1. The Look-Ahead Bias Problem\n")
        f.write("Historically, the research evaluation scripts (`exp_phase5_3_ml_ablation.py`, etc.) calculated a decision threshold dynamically using `p90 = np.percentile(preds, 90)` **directly on the out-of-sample prediction array**. ")
        f.write("This constitutes future look-ahead bias if deployed in a live, causal system, as the 90th percentile of 2024 predictions cannot be known on January 1st, 2024.\n\n")
        
        f.write("## 2. Methodology A: Train-Only Fixed Quantile\n")
        f.write("To reconstruct a strictly causal policy that perfectly aligns with the historical intent (trading the top 10% highest-confidence signals), we calculate the 90th percentile of the prediction distribution over the **strictly frozen training set (2022-2023)**. ")
        f.write("These static thresholds are then frozen for 2024 out-of-sample forward execution.\n\n")
        
        f.write("## 3. Reconstructed Thresholds\n")
        f.write("| Symbol | Train Samples | Mean Train Prob | Reconstructed p90 Threshold |\n")
        f.write("|--------|---------------|-----------------|-----------------------------|\n")
        for sym, d in thresholds.items():
            f.write(f"| {sym} | {d['train_samples']} | {d['train_mean_prob']:.4f} | **{d['p90_threshold']:.4f}** |\n")
            
        f.write("\n## 4. Architectural Directive\n")
        f.write("These static thresholds are saved to `PHASE7_DECISION_THRESHOLDS.json`. ")
        f.write("The production `DecisionEngine` must load this file and apply a strict `probability >= p90_threshold` causal rule for signal generation.\n")
        f.write("Short logic remains strictly unauthorized (Ophelia remains LONG only).\n")

if __name__ == "__main__":
    reconstruct_policy()
