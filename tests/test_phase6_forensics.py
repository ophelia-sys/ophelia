import pytest
import numpy as np
import pandas as pd
from research.phase6.power import PowerAnalysis
from research.phase6.events import EventGenerator
from research.phase6.validation import WalkForwardValidator

def test_mde_calculation():
    """Test that MDE is correctly calculated for a standard distribution"""
    power = PowerAnalysis(desired_power=0.8, alpha=0.05)
    baseline_std = 0.006282
    n_eff = 1946
    
    report = power.analyze_power(baseline_std, n_eff, assumed_effects=[0.05])
    # Z_alpha = 1.96, Z_beta = 0.84 -> (1.96+0.84) * (0.006282 / sqrt(1946)) = 0.000399
    assert report["mde"] is not None
    assert np.isclose(report["mde"], 0.000399, atol=1e-5)

def test_power_monotonicity_and_conversion():
    """Test that power increases monotonically with effect size and handles Cohen's d scaling"""
    power = PowerAnalysis(desired_power=0.8, alpha=0.05)
    baseline_std = 0.006282
    n_eff = 1946
    
    effects = [0.05, 0.10, 0.15, 0.20, 0.25]
    report = power.analyze_power(baseline_std, n_eff, assumed_effects=effects)
    
    powers = [report["power_by_effect"][e] for e in effects]
    
    # Check monotonicity
    for i in range(1, len(powers)):
        assert powers[i] >= powers[i-1]
        
    # Check specific conversion points
    # d=0.05 should be around 59.7% power for N=1946
    assert np.isclose(powers[0], 0.5968, atol=0.01)
    
    # d=0.10 should be near 99.3%
    assert np.isclose(powers[1], 0.9929, atol=0.01)

def test_clustering_millisecond_handling():
    """Test that event generator correctly clusters events within 300,000 ms"""
    generator = EventGenerator()
    
    # Create artificial events separated by 100 seconds (100,000 ms) - should cluster
    events = [
        {"timestamp": 1000000, "confirmation_timestamp": 1000000, "event_type": "TEST", "side": "LONG"},
        {"timestamp": 1100000, "confirmation_timestamp": 1100000, "event_type": "TEST", "side": "LONG"},
        {"timestamp": 1200000, "confirmation_timestamp": 1200000, "event_type": "TEST", "side": "LONG"}
    ]
    
    generator.events = events
    generator._cluster_events()
    clustered = generator.events
    # They should all fall into 1 cluster
    assert len(clustered) == 3
    # The first event is primary, the others are not
    assert clustered[0]["primary_event"] is True
    assert clustered[1]["primary_event"] is False
    assert clustered[2]["primary_event"] is False

    # Create artificial events separated by 6 minutes (360,000 ms) - should NOT cluster
    events_distant = [
        {"timestamp": 1000000, "confirmation_timestamp": 1000000, "event_type": "TEST", "side": "LONG"},
        {"timestamp": 1360000, "confirmation_timestamp": 1360000, "event_type": "TEST", "side": "LONG"},
        {"timestamp": 1720000, "confirmation_timestamp": 1720000, "event_type": "TEST", "side": "LONG"}
    ]
    
    generator.events = events_distant
    generator._cluster_events()
    clustered_distant = generator.events
    assert len(clustered_distant) == 3
    # All are primary since they are separated by > 300,000 ms
    assert clustered_distant[0]["primary_event"] is True
    assert clustered_distant[1]["primary_event"] is True
    assert clustered_distant[2]["primary_event"] is True

def test_purge_embargo_isolation():
    """Test that fold generation mathematically enforces absolute isolation"""
    validator = WalkForwardValidator(embargo_seconds=86400)
    
    # Create dummy DataFrame bridging exactly 10 days
    start_time = 1600000000000
    end_time = start_time + (10 * 86400000)
    
    df = pd.DataFrame({
        "timestamp": np.linspace(start_time, end_time, 1000)
    })
    
    # No events needed to just check fold timing logic
    folds = validator.generate_folds(df, n_folds=2, max_horizon_seconds=3600)
    
    for fold in folds:
        # Check purge duration is >= 3,600,000 ms
        purge_duration = fold["purge_end"] - fold["train_end"]
        assert purge_duration >= 3600000
        
        # Check embargo duration is exactly 86,400,000 ms
        embargo_duration = fold["embargo_end"] - fold["purge_end"]
        assert embargo_duration == 86400000
        
        # Check Test Start strictly follows Embargo End
        assert fold["test_start"] > fold["embargo_end"]
        
        # Verify overlap prevention: Maximum label reach of last train observation MUST NOT hit test data
        latest_train_label_end = fold["train_end"] + 3600000
        assert latest_train_label_end < fold["test_start"]
        
        # Exact gap should be > 25 hours
        gap = fold["test_start"] - latest_train_label_end
        assert gap >= 86400000
