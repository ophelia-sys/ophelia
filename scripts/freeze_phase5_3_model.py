import os
import pickle
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from research.pipeline.data_loader import ResearchDataLoader
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from research.pipeline.labels import LabelGenerator
from research.experiments.exp_phase5_3_ml_ablation import load_cvd_symbol, engineer_cvd_features, MODELS_CONFIG

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT"]

def freeze_models():
    print("--- FREEZING PHASE 5.3 MODEL G ---")
    loader = ResearchDataLoader()
    baseline_exp = Phase5BaselineExperiment()
    
    frozen_artifact = {
        'version': '1.0',
        'protocol': 'PHASE5_3_CVD_ML_EXPERIMENT_PROTOCOL.md',
        'models': {}
    }
    
    base_f, cvd_f = MODELS_CONFIG['G']
    expected_features = base_f + cvd_f

    for symbol in SYMBOLS:
        print(f"Fitting complete-case Model G for {symbol}...")
        df_ohlcv = loader.load_symbol(symbol)
        df_ohlcv = baseline_exp.engineer_features(df_ohlcv)
        df_ohlcv = baseline_exp.apply_labels(df_ohlcv, tp_atr_mult=2.0, sl_atr_mult=1.0, horizon=60)
        df_ohlcv = LabelGenerator.generate_labels(df_ohlcv, horizons=[60], thresholds_bps=[10])
        
        df_cvd = load_cvd_symbol(symbol)
        df = engineer_cvd_features(df_ohlcv, df_cvd)
        
        # 2022-2023 complete case
        df = df[(df['timestamp'] >= '2022-01-01') & (df['timestamp'] < '2024-01-01')]
        valid_df = df.dropna(subset=expected_features + ['target_60_up_10']).copy()
        
        X = valid_df[expected_features].values
        y = valid_df['target_60_up_10'].values
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        clf = LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, penalty='l2')
        clf.fit(X_scaled, y)
        
        frozen_artifact['models'][symbol] = {
            'scaler': scaler,
            'model': clf,
            'features': expected_features
        }
        
    out_path = os.path.join(BASE_DIR, "PHASE5_3_MODEL_G_FROZEN.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(frozen_artifact, f)
        
    print(f"Successfully saved frozen models for {len(SYMBOLS)} symbols to {out_path}.")

if __name__ == "__main__":
    freeze_models()
