import pytest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.ml4t_benchmark.features.p7_volume_acceptance import engineer_p7_volume_acceptance_features

def test_p7_causality_perturbation():
    dates = pd.date_range("2023-01-01 00:00:00", periods=500, freq="5min")
    df_ohlcv = pd.DataFrame({
        'timestamp': dates,
        'close': np.linspace(20000, 21000, 500),
        'volume': np.ones(500) * 50
    })
    
    df_feat_orig = engineer_p7_volume_acceptance_features(df_ohlcv)
    
    # Perturb the future (index 400)
    df_ohlcv_pert = df_ohlcv.copy()
    df_ohlcv_pert.loc[400, 'close'] = 99999
    df_ohlcv_pert.loc[400, 'volume'] = 99999
    
    df_feat_pert = engineer_p7_volume_acceptance_features(df_ohlcv_pert)
    
    # Verify exact equality before the perturbation
    pd.testing.assert_frame_equal(df_feat_orig.iloc[:400], df_feat_pert.iloc[:400])
    
    # Verify inequality at the perturbation point
    assert df_feat_orig.loc[400, 'price_to_vwap_1d'] != df_feat_pert.loc[400, 'price_to_vwap_1d']
