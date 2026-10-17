import pytest
import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.validation import DataSplitter
from research.pipeline.labels import LabelGenerator
from research.experiments.exp_004_interactions import generate_interaction_features

def test_data_splitter():
    # Create dummy df spanning 2 years using exact ms timestamps
    start_ms = 1640995200000 # 2022-01-01
    end_ms = 1704067200000 # 2024-01-01
    timestamps = np.arange(start_ms, end_ms, 86400000)
    df = pd.DataFrame({'timestamp': timestamps})
    
    discovery, oos = DataSplitter.split_discovery_oos(df, split_date_str="2023-09-01")
    
    # Verify split logic
    assert len(discovery) > 0
    assert len(oos) > 0
    
    max_disc_dt = pd.to_datetime(discovery['timestamp'].max(), unit='ms')
    min_oos_dt = pd.to_datetime(oos['timestamp'].min(), unit='ms')
    
    assert max_disc_dt < pd.to_datetime("2023-09-01")
    assert min_oos_dt >= pd.to_datetime("2023-09-01")
    
    # Assert no overlap
    assert set(discovery['timestamp']).isdisjoint(set(oos['timestamp']))

def test_threshold_labels():
    df = pd.DataFrame({'close': [100, 101, 102, 100, 99]})
    
    labeled = LabelGenerator.generate_labels(df, horizons=[1], thresholds_bps=[50, 150])
    
    # 100 -> 101 is +1%, or 100 bps. 
    # This is > 50 bps, but < 150 bps
    # np.log(101/100) = 0.00995 = 99.5 bps
    assert labeled['target_1_up_50'].iloc[0] == 1.0
    assert labeled['target_1_up_150'].iloc[0] == 0.0
    
    # 102 -> 100 is approx -2%, or -200 bps
    assert labeled['target_1_dn_150'].iloc[2] == 1.0
    assert labeled['target_1_dn_50'].iloc[2] == 1.0
    assert labeled['target_1_up_50'].iloc[2] == 0.0
    
def test_interaction_features():
    df = pd.DataFrame({
        'ker_60': [0.5, 0.8],
        'vol_60': [0.01, 0.02],
        'mom_60': [10, -5],
        'vol_z': [1.5, -0.5]
    })
    
    interacted = generate_interaction_features(df)
    
    assert 'interact_trend_vol' in interacted.columns
    assert 'interact_mom_vol' in interacted.columns
    assert 'interact_volume_vol' in interacted.columns
    
    assert np.isclose(interacted['interact_trend_vol'].iloc[0], 0.5 * 0.01)
    assert np.isclose(interacted['interact_mom_vol'].iloc[1], -5 * 0.02)
    assert np.isclose(interacted['interact_volume_vol'].iloc[0], 1.5 * 0.01)
