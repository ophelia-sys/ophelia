import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from research.experiments.PHASE2_EDGE_DISCOVERY_V1.phase2_pipeline import run_experiment
from research.experiments.PHASE2_EDGE_DISCOVERY_V1.features import (
    build_base_features,
    add_adv_orderflow_features,
    add_regime_features,
    add_volatility_features,
    BASELINE_FEATURES,
    ADV_OF_FEATURES,
    REGIME_FEATURES,
    VOL_FEATURES
)

def build_base(df):
    return build_base_features(df)

def build_base_plus_of(df):
    df = build_base_features(df)
    df = add_adv_orderflow_features(df)
    return df

def build_base_plus_regime(df):
    df = build_base_features(df)
    df = add_regime_features(df)
    return df

def build_base_plus_vol(df):
    df = build_base_features(df)
    df = add_volatility_features(df)
    return df

def build_all_features(df):
    df = build_base_features(df)
    df = add_adv_orderflow_features(df)
    df = add_regime_features(df)
    df = add_volatility_features(df)
    return df

def run():
    print("Running B. BASE + ORDER FLOW...")
    run_experiment("EXP_001_ADV_OF", build_base_plus_of, BASELINE_FEATURES + ADV_OF_FEATURES)
    
    print("Running C. BASE + REGIME...")
    run_experiment("EXP_002_REGIME", build_base_plus_regime, BASELINE_FEATURES + REGIME_FEATURES)
    
    print("Running D. BASE + VOLATILITY...")
    run_experiment("EXP_003_VOLATILITY", build_base_plus_vol, BASELINE_FEATURES + VOL_FEATURES)
    
    print("Running E. BASE + ALL FEATURES...")
    run_experiment("EXP_004_ALL_FEATURES", build_all_features, BASELINE_FEATURES + ADV_OF_FEATURES + REGIME_FEATURES + VOL_FEATURES)
    
    print("Running F. MODEL CAPACITY RESEARCH (Depth 4)...")
    run_experiment("EXP_005_MODEL_DEPTH4", build_base, BASELINE_FEATURES, model_params={'n_estimators': 100, 'learning_rate': 0.05, 'max_depth': 4, 'num_leaves': 15, 'random_state': 42})
    
    print("Running G. MODEL CAPACITY RESEARCH (Depth 5)...")
    run_experiment("EXP_006_MODEL_DEPTH5", build_base, BASELINE_FEATURES, model_params={'n_estimators': 100, 'learning_rate': 0.05, 'max_depth': 5, 'num_leaves': 31, 'random_state': 42})

if __name__ == "__main__":
    run()
