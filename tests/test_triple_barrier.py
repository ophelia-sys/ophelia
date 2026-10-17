import pytest
import pandas as pd
import numpy as np
from research.pipeline.triple_barrier import label_triple_barrier

def test_triple_barrier_ambiguity():
    """
    Tests CASE D: Both upper and lower barriers are touched within the same 1m candle.
    Must return np.nan (AMBIGUOUS).
    """
    df = pd.DataFrame({
        'close': [100.0, 100.0, 100.0],
        'high':  [100.0, 150.0, 100.0], # massive wick in index 1
        'low':   [100.0, 50.0,  100.0],  # massive wick in index 1
        'atr':   [10.0,  10.0,  10.0]
    })
    
    # Upper = 100 + 20 = 120
    # Lower = 100 - 10 = 90
    labeled = label_triple_barrier(df, horizons=['15min'], atr_multiplier_sl=1.0, atr_multiplier_tp=2.0)
    
    # Index 0 evaluates forward window starting at Index 1.
    # Index 1 has high 150 (hits upper 120) and low 50 (hits lower 90)
    label = labeled['label_long_15min'].iloc[0]
    assert np.isnan(label), "Ambiguous intrabar touch must yield np.nan"

def test_triple_barrier_case_a():
    """
    Tests CASE A: Upper barrier touched, lower not touched.
    """
    df = pd.DataFrame({
        'close': [100.0, 100.0],
        'high':  [100.0, 125.0],
        'low':   [100.0, 95.0], 
        'atr':   [10.0,  10.0]
    })
    
    labeled = label_triple_barrier(df, horizons=['15min'], atr_multiplier_sl=1.0, atr_multiplier_tp=2.0)
    label = labeled['label_long_15min'].iloc[0]
    assert label == 1.0

def test_triple_barrier_case_b():
    """
    Tests CASE B: Lower barrier touched, upper not touched.
    """
    df = pd.DataFrame({
        'close': [100.0, 100.0],
        'high':  [100.0, 105.0],
        'low':   [100.0, 85.0], 
        'atr':   [10.0,  10.0]
    })
    
    labeled = label_triple_barrier(df, horizons=['15min'], atr_multiplier_sl=1.0, atr_multiplier_tp=2.0)
    label = labeled['label_long_15min'].iloc[0]
    assert label == -1.0

def test_triple_barrier_case_c():
    """
    Tests CASE C: Neither barrier touched (time exit).
    """
    df = pd.DataFrame({
        'close': [100.0, 100.0],
        'high':  [100.0, 105.0],
        'low':   [100.0, 95.0], 
        'atr':   [10.0,  10.0]
    })
    
    labeled = label_triple_barrier(df, horizons=['15min'], atr_multiplier_sl=1.0, atr_multiplier_tp=2.0)
    label = labeled['label_long_15min'].iloc[0]
    assert label == 0.0
