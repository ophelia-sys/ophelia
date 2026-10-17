import pytest
import pandas as pd
import numpy as np
from research.phase6.events import EventGenerator
from research.phase6.data_quality import DataQualityAuditor
from research.phase6.validation import WalkForwardValidator

def test_event_timestamp_causality():
    df = pd.DataFrame({
        'timestamp': [1000, 1060, 1120, 1180, 1240, 1300, 1360],
        'open': [10, 10, 10, 10, 10, 10, 10],
        'high': [15, 12, 11, 10, 10, 10, 10],
        'low': [5, 8, 9, 10, 10, 10, 10],
        'close': [12, 11, 10, 10, 10, 10, 10]
    })
    atr_series = pd.Series([1, 1, 1, 1, 1, 1, 1])
    
    gen = EventGenerator(w=2)
    events = gen.generate_events(df, atr_series)
    
    # Check that any generated event has confirmation_timestamp <= the latest timestamp
    for ev in events:
        assert ev["confirmation_timestamp"] <= 1360
        assert ev["timestamp"] == ev["confirmation_timestamp"]

def test_data_gap_invalidation():
    auditor = DataQualityAuditor(max_data_gap_seconds=300)
    
    df_good = pd.DataFrame({
        'timestamp': [0, 60, 120, 180],
        'open': [1,1,1,1], 'high': [2,2,2,2], 'low': [0,0,0,0], 'close': [1,1,1,1]
    })
    assert auditor.audit_dataset(df_good)["status"] == "PASS"
    
    df_gap = pd.DataFrame({
        'timestamp': [0, 60, 1000, 1060],
        'open': [1,1,1,1], 'high': [2,2,2,2], 'low': [0,0,0,0], 'close': [1,1,1,1]
    })
    assert auditor.get_gap_indices(df_gap) == [2]

def test_walk_forward_purging():
    validator = WalkForwardValidator(embargo_seconds=100)
    df = pd.DataFrame({
        'timestamp': np.arange(0, 10000, 60)
    })
    folds = validator.generate_folds(df, n_folds=2, max_horizon_seconds=300)
    
    for fold in folds:
        test = fold["test_df"]
        train = fold["train_df"]
        assert test['timestamp'].iloc[0] > train['timestamp'].iloc[-1] + 300 + 100
