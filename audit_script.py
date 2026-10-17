import sys
import os
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from research.backtest.engine import OpheliaBacktest
from research.phase6.pipeline import ResearchPipeline

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(period).mean()

def run_audit():
    dataset_id = "binance_um_btcusdt_1m_v1"
    engine = OpheliaBacktest(dataset_id)
    iterator = engine.loader.get_chronological_iterator(dataset_id)
    df = iterator.fetchdf()
    atr_series = calculate_atr(df)
    
    pipeline = ResearchPipeline(n_folds=5)
    # Get events (since pipeline logic creates features inside event_gen)
    # The actual pipeline calls:
    # df_regime = pipeline.regimes.classify_regimes(df)
    # df_labeled = pipeline.label_gen.generate_labels(df_regime)
    events = pipeline.event_gen.generate_events(df, atr_series)
    df_regime = pipeline.regimes.classify_regimes(df)
    df_labeled = pipeline.label_gen.generate_labels(df_regime)
    enriched_events = pipeline.label_gen.attach_labels_to_events(events, df_labeled)
    
    # Clustering gap
    timestamps = [e['confirmation_timestamp'] for e in events]
    timestamps.sort()
    diffs = np.diff(timestamps)
    
    print("CLUSTERING FORENSICS:")
    if len(diffs) > 0:
        print(f"Minimum gap: {np.min(diffs)} ms")
        print(f"Median gap: {np.median(diffs)} ms")
        print(f"25th percentile gap: {np.percentile(diffs, 25)} ms")
        print(f"75th percentile gap: {np.percentile(diffs, 75)} ms")
        print(f"Maximum gap: {np.max(diffs)} ms")
        print(f"Gaps <= 300,000 ms: {np.sum(diffs <= 300000)}")
    else:
        print("No multiple events.")

    # Purge / Embargo Fold overlap
    folds = pipeline.validator.generate_folds(df_labeled, n_folds=5, max_horizon_seconds=3600)
    print("\nPURGE / EMBARGO FORENSICS:")
    for i, fold in enumerate(folds):
        # We need to find the latest training observation's maximum label end
        # The max horizon is 60m = 3,600,000 ms.
        # Latest training timestamp: fold['train_end']
        latest_train_label_end = fold['train_end'] + 3600000
        test_start = fold['test_start']
        
        separation = test_start - latest_train_label_end
        print(f"Fold {i+1}:")
        print(f"Train End: {fold['train_end']}")
        print(f"Latest Train Label End: {latest_train_label_end}")
        print(f"Test Start: {test_start}")
        print(f"Latest Train Label End < Test Start: {latest_train_label_end < test_start}")
        print(f"Separation: {separation} ms ({separation / 60000} minutes)")
        
        purge_duration = fold['purge_end'] - fold['train_end']
        embargo_duration = fold['embargo_end'] - fold['purge_end']
        print(f"Purge Duration: {purge_duration} ms")
        print(f"Embargo Duration: {embargo_duration} ms")

if __name__ == '__main__':
    run_audit()
