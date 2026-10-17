import os
import sys
import pandas as pd
import numpy as np

# Ensure we can import existing modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from research.phase6.pipeline import ResearchPipeline

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATASET_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'binance_um_universe_1m_v2.parquet')
MANIFEST_PATH = os.path.join(BASE_DIR, 'research', 'phase6', 'CANONICAL_DATASET_MANIFEST.json')

def reproduce_baseline():
    print("==================================================")
    print("PHASE 6.1: BASELINE REPRODUCTION")
    print("==================================================")
    
    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError("CANONICAL_DATASET_MANIFEST.json not found. Gate 0 incomplete.")
        
    print(f"Loading canonical dataset: {DATASET_PATH}")
    df = pd.read_parquet(DATASET_PATH)
    
    # We need ATR for event generation in Phase 5/6 baseline
    # Create a dummy ATR series since we don't have the full model here,
    # or compute a basic ATR for testing.
    # Actually, pipeline.py expects atr_series aligned with df.
    # Let's compute a quick ATR(14)
    df['tr'] = np.maximum(df['high'] - df['low'], 
               np.maximum(abs(df['high'] - df['close'].shift()), 
                          abs(df['low'] - df['close'].shift())))
    atr_series = df.groupby('symbol')['tr'].transform(lambda x: x.rolling(14).mean())
    
    print("Running ResearchPipeline.run_pipeline()...")
    pipeline = ResearchPipeline(n_folds=5)
    
    # Run only on a subset or full? 
    # Full dataset is 6.2M rows, might take a few minutes. 
    # Let's run it.
    res = pipeline.run_pipeline(df, atr_series)
    
    print("\n--- BASELINE RESULTS ---")
    for h, b in res["baselines"].items():
        print(f"Horizon {h}m: N={b['N']}, Mean={b['mean']:.6f}, Std={b['std']:.6f}")
        
    print("\n--- FEATURE STATISTICAL RESULTS ---")
    for r in res["statistical_results"]:
        print(r)
        
    print("\n--- ECONOMIC RESULTS (Horizon 60) ---")
    for scenario, cost in res["cost_results"].items():
        print(f"Scenario: {scenario}")
        print(cost)

if __name__ == "__main__":
    reproduce_baseline()
