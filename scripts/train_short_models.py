import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.experiments.exp_008_short_feature_discovery import build_phase7_features

def train_short_model_for_symbol(symbol: str, thresholds_dict: dict):
    print(f"\n{'='*50}\nTraining Short Model for {symbol}\n{'='*50}")
    
    loader = ResearchDataLoader()
    try:
        df_1m = loader.load_symbol(symbol.replace("-", ""))
    except FileNotFoundError:
        print(f"Skipping {symbol}, parquet not found.")
        return
        
    # Generate mathematically symmetric target using LabelGenerator
    df_5m = build_phase7_features(df_1m)
    df_5m = LabelGenerator.generate_labels(df_5m, horizons=[60], thresholds_bps=[10])
    
    base_features = [
        "ret_1", "ret_3", "ret_5", "realized_vol_20", "atr_pct_14", "mom_10", "vol_ratio",
        "cvd_delta_5m", "cvd_delta_15m", "cvd_delta_1h",
        "cvd_imbalance_5m", "cvd_imbalance_15m", "cvd_imbalance_1h",
        "cvd_zscore_5m", "cvd_zscore_15m", "cvd_zscore_1h",
        "cvd_acceleration_15m", "cvd_acceleration_1h"
    ]
    
    df_5m.dropna(subset=base_features + ['target_60_dn_10'], inplace=True)
    
    X = df_5m[base_features]
    y = df_5m['target_60_dn_10']
    
    print(f"Total samples: {len(X)}")
    
    # 1. Cross Validation for Threshold Generation
    cv = PurgedWalkForwardValidation(n_folds=3, embargo=60)
    splits = cv.split(X)
    
    oof_preds = []
    
    clf_cv = lgb.LGBMClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=42)
    
    for fold, (train_idx, test_idx) in enumerate(splits):
        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_te, y_te = X.iloc[test_idx], y.iloc[test_idx]
        
        clf_cv.fit(X_tr, y_tr)
        preds = clf_cv.predict_proba(X_te)[:, 1]
        oof_preds.extend(preds)
        
    if oof_preds:
        short_threshold = float(np.percentile(oof_preds, 90))
        print(f"OOF p90 Threshold for SHORT: {short_threshold:.4f}")
    else:
        short_threshold = 0.5
        print("WARNING: No OOF predictions generated. Defaulting threshold to 0.5")

    # 2. Train Final Frozen Model
    clf_final = lgb.LGBMClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=42)
    clf_final.fit(X, y)
    
    artifact = {
        "model_object": clf_final,
        "symbol": symbol,
        "model_version": "1.0",
        "feature_contract": {
            "features": base_features
        },
        "lineage": {
            "lightgbm_version": lgb.__version__,
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
            "training_date": datetime.utcnow().isoformat(),
            "target": "target_60_down_10"
        }
    }
    
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"PHASE7_SHORT_MODEL_FROZEN_{symbol.replace('-', '')}.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(artifact, f)
        
    print(f"Saved frozen model to {model_path}")
    
    # 3. Update Thresholds Dict
    symbol_no_hyphen = symbol.replace("-", "")
    if symbol_no_hyphen not in thresholds_dict:
        thresholds_dict[symbol_no_hyphen] = {}
        
    thresholds_dict[symbol_no_hyphen]["short_threshold"] = short_threshold
    thresholds_dict[symbol_no_hyphen]["oof_short_n"] = len(oof_preds)

def main():
    target_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT"]
    
    thresholds_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PHASE7_DECISION_THRESHOLDS.json")
    
    with open(thresholds_path, "r") as f:
        thresholds_dict = json.load(f)
        
    for sym in target_symbols:
        train_short_model_for_symbol(sym, thresholds_dict)
        
    with open(thresholds_path, "w") as f:
        json.dump(thresholds_dict, f, indent=4)
        
    print(f"\nUpdated {thresholds_path}")

if __name__ == "__main__":
    main()
