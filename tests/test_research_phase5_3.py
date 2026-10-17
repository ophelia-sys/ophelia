import pytest
import pandas as pd
import numpy as np
import os
import sys

# Ensure imports work without installing as package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research.pipeline.labels import LabelGenerator, OUTCOME_TIMEOUT, OUTCOME_TARGET, OUTCOME_STOP, OUTCOME_AMBIGUOUS

def test_generate_barrier_labels_basic():
    # Construct a simple dataframe
    # Entry at 100
    df = pd.DataFrame({
        'close': [100, 101, 102, 103, 104],
        'high':  [100, 101, 103, 103, 104],
        'low':   [100, 100, 101, 101, 103]
    })
    
    # Target 2% (200 bps), stop 1% (100 bps)
    df = LabelGenerator.generate_barrier_labels(df, target_bps=200, stop_bps=100, timeout_candles=4, is_long=True)
    
    # At index 0, entry is 100. Target is 102.
    # index 1: high=101, low=100 -> neither
    # index 2: high=103, low=101 -> TARGET_HIT (high >= 102, low > 99)
    assert df['barrier_outcome'].iloc[0] == OUTCOME_TARGET
    assert df['barrier_exit_offset'].iloc[0] == 2
    
def test_generate_barrier_labels_stop():
    df = pd.DataFrame({
        'close': [100, 99, 98, 97],
        'high':  [100, 100, 99, 98],
        'low':   [100, 99, 98, 97]
    })
    
    # Target 2% (200 bps), stop 1% (100 bps)
    df = LabelGenerator.generate_barrier_labels(df, target_bps=200, stop_bps=100, timeout_candles=3, is_long=True)
    
    # index 1: high=100, low=99 -> STOP_HIT (low <= 99)
    assert df['barrier_outcome'].iloc[0] == OUTCOME_STOP
    assert df['barrier_exit_offset'].iloc[0] == 1
    
def test_generate_barrier_labels_timeout():
    df = pd.DataFrame({
        'close': [100, 100, 100, 100],
        'high':  [100, 100, 100, 100],
        'low':   [100, 100, 100, 100]
    })
    
    df = LabelGenerator.generate_barrier_labels(df, target_bps=200, stop_bps=100, timeout_candles=2, is_long=True)
    
    assert df['barrier_outcome'].iloc[0] == OUTCOME_TIMEOUT
    assert df['barrier_exit_offset'].iloc[0] == 2
    
def test_generate_barrier_labels_ambiguous():
    df = pd.DataFrame({
        'close': [100, 100],
        'high':  [100, 102], # Hits target
        'low':   [100, 99]   # Hits stop
    })
    
    df = LabelGenerator.generate_barrier_labels(df, target_bps=200, stop_bps=100, timeout_candles=1, is_long=True)
    
    assert df['barrier_outcome'].iloc[0] == OUTCOME_AMBIGUOUS
    assert df['barrier_exit_offset'].iloc[0] == 1
