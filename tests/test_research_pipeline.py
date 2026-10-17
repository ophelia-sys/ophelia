import pytest
import pandas as pd
import numpy as np
import os
import sys

# Ensure imports work without installing as package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.features import FeatureGenerator
from research.pipeline.labels import LabelGenerator
from research.pipeline.validation import PurgedWalkForwardValidation
from research.pipeline.metrics import MetricsEvaluator

def test_no_execution_imports():
    """Ensure research pipeline does not import core execution logic."""
    import research.pipeline
    import sys
    assert 'core.TradingEngine' not in sys.modules
    assert 'exchange.BingXClient' not in sys.modules

def test_label_generation():
    df = pd.DataFrame({'close': [100, 101, 102, 101, 90]})
    # Test horizon = 2
    labeled = LabelGenerator.generate_labels(df, horizons=[2])
    
    # R_2 for index 0 (100 -> 102) is ln(102/100)
    assert np.isclose(labeled['R_2'].iloc[0], np.log(102/100))
    assert labeled['target_2'].iloc[0] == 1.0
    
    # R_2 for index 2 (102 -> 90) is ln(90/102)
    assert np.isclose(labeled['R_2'].iloc[2], np.log(90/102))
    assert labeled['target_2'].iloc[2] == 0.0

def test_purged_walk_forward_leakage():
    # 100 samples
    X = np.arange(100)
    val = PurgedWalkForwardValidation(n_folds=3, embargo=5)
    splits = val.split(X)
    
    for train_idx, test_idx in splits:
        # Check embargo
        assert max(train_idx) <= min(test_idx) - 5
        # Check chronological
        assert list(train_idx) == sorted(list(train_idx))
        assert list(test_idx) == sorted(list(test_idx))

def test_metrics_cost_calculation():
    y_true = np.array([1, 0, 1, 0])
    y_pred = np.array([0.9, 0.1, 0.8, 0.2])
    fwd_ret = np.array([0.0050, -0.0050, 0.0040, -0.0040]) # +50bps, -50bps, +40bps, -40bps
    
    # Costs 12 bps = 0.0012
    deciles = MetricsEvaluator.economic_deciles(y_true, y_pred, fwd_ret, costs_bps=12)
    # The highest prediction decile (top) should have gross +45 bps (avg of 50 and 40? No, wait)
    # They will be bucketed.
    # We just ensure the net return subtraction is exactly 12 bps
    for d in deciles:
        assert np.isclose(d['net_ret_bps'], d['gross_ret_bps'] - 12.0)
