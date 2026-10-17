import pytest
import numpy as np
import pandas as pd
import time
import os

from research.phase6.registry import FeatureRegistry, PromotionState
from research.phase6.experiment import ExperimentRunner
from research.phase6.statistics import CalendarTimePortfolio, calendar_block_bootstrap

@pytest.fixture
def temp_registry():
    path = "research/phase6/tests/temp_registry.json"
    if os.path.exists(path):
        os.remove(path)
    reg = FeatureRegistry(path)
    yield reg
    if os.path.exists(path):
        os.remove(path)

def test_experiment_runner_oos_integrity(temp_registry):
    runner = ExperimentRunner(temp_registry, "TEST_EXP_01", "hash123")
    folds = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}]
    
    # Must fail to get OOS before DEV
    with pytest.raises(RuntimeError, match="Must access DEV data"):
        runner.get_oos_data(folds)
        
    dev = runner.get_dev_data(folds)
    assert len(dev) == 3
    
    # Must fail to get OOS before locking family
    with pytest.raises(RuntimeError, match="Must lock a HypothesisFamily"):
        runner.get_oos_data(folds)
        
    # Lock family
    runner.start_hypothesis_family("feat_test", 10, [{"idx": i} for i in range(10)])
    
    oos = runner.get_oos_data(folds)
    assert len(oos) == 2
    
    # Must fail to get DEV after OOS
    with pytest.raises(RuntimeError, match="CRITICAL LEAKAGE"):
        runner.get_dev_data(folds)

def test_multiple_testing_fdr(temp_registry):
    runner = ExperimentRunner(temp_registry, "TEST_EXP_02", "hash123")
    runner.get_dev_data([{}, {}, {}, {}, {}])
    
    # Family size = 10, but we only evaluate 2 hypotheses on OOS (mimicking winning threshold selection)
    runner.start_hypothesis_family("feat_test2", 10, [{"idx": i} for i in range(10)])
    runner.get_oos_data([{}, {}, {}, {}, {}])
    
    # Record two very significant raw p-values
    runner.record_oos_result(0, 0.001, 1.5, {})
    runner.record_oos_result(1, 0.005, 1.2, {})
    
    results = runner.finalize_family()
    
    # The FDR must penalize assuming the other 8 hypotheses failed (p=1.0)
    # p=0.001 rank 1 out of 10 -> adj_p = 0.001 * 10 / 1 = 0.01
    # p=0.005 rank 2 out of 10 -> adj_p = 0.005 * 10 / 2 = 0.025
    assert results[0]["fdr_p_value"] == pytest.approx(0.01)
    assert results[1]["fdr_p_value"] == pytest.approx(0.025)
    
def test_calendar_time_portfolio_aggregation():
    base_time = 1700000000000 # ~Nov 2023
    hour_ms = 3600 * 1000
    
    events = [
        # Hour 0
        {"timestamp": base_time, "symbol": "BTC", "R_60": 0.01},
        {"timestamp": base_time + 1000, "symbol": "ETH", "R_60": 0.03},
        # Hour 1 (No events)
        # Hour 2
        {"timestamp": base_time + 2 * hour_ms, "symbol": "BTC", "R_60": 0.02},
        {"timestamp": base_time + 2 * hour_ms + 100, "symbol": "BTC", "R_60": 0.04},
    ]
    
    ctp = CalendarTimePortfolio(events, horizon=60, bin_freq='1h', weighting='equal_symbol')
    
    # Hour 0: BTC (0.01), ETH (0.03). Equal symbol avg = 0.02
    # Hour 1: 0.0
    # Hour 2: BTC has two events (0.02, 0.04). BTC avg = 0.03. Equal symbol avg = 0.03.
    
    y = ctp.portfolio_series.values
    assert len(y) == 3 # Hour 0, 1, 2
    assert y[0] == pytest.approx(0.02)
    assert y[1] == pytest.approx(0.0)
    assert y[2] == pytest.approx(0.03)
    
    se = ctp.calendar_newey_west_se()
    assert not np.isnan(se)
    
    bs = calendar_block_bootstrap(ctp, block_size_bins=1, num_bootstraps=10)
    assert len(bs) == 10
