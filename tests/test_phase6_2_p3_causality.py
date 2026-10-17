import pytest
import pandas as pd
import numpy as np
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
from research.ml4t_benchmark.features.spot_perp import compute_p3_spot_perp_features

def test_p3_strict_causality():
    """
    Proves that injecting a massive perturbation into a future spot or futures price
    has exactly zero effect on any feature value at or before the current timestamp.
    """
    np.random.seed(42)
    n = 1000
    idx = pd.date_range('2022-01-01', periods=n, freq='5min')
    
    fut_close_base = np.random.lognormal(mean=0, sigma=0.01, size=n).cumprod() * 10000
    spot_close_base = fut_close_base + np.random.normal(0, 10, size=n)
    
    df_fut = pd.DataFrame({'close': fut_close_base}, index=idx)
    df_spot = pd.DataFrame({'close': spot_close_base}, index=idx)
    
    # Baseline features
    base_features = compute_p3_spot_perp_features(df_fut, df_spot)
    
    # Perturb the future at index 500
    perturb_idx = 500
    
    fut_close_perturbed = fut_close_base.copy()
    spot_close_perturbed = spot_close_base.copy()
    
    # Massive future shock
    fut_close_perturbed[perturb_idx:] *= 2.0
    spot_close_perturbed[perturb_idx:] *= 0.5
    
    df_fut_pert = pd.DataFrame({'close': fut_close_perturbed}, index=idx)
    df_spot_pert = pd.DataFrame({'close': spot_close_perturbed}, index=idx)
    
    # Perturbed features
    pert_features = compute_p3_spot_perp_features(df_fut_pert, df_spot_pert)
    
    # CAUSALITY ASSERTION:
    # Everything strictly before the perturbation index MUST be identically equal.
    # We use index 499 as the boundary.
    boundary_idx = perturb_idx - 1
    
    # Compare slice 0:boundary_idx (inclusive)
    base_slice = base_features.iloc[:boundary_idx+1]
    pert_slice = pert_features.iloc[:boundary_idx+1]
    
    # fillna because nan != nan in pandas equality check
    pd.testing.assert_frame_equal(base_slice.fillna(0), pert_slice.fillna(0))
    
    # At the perturbation index, they must diverge
    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(
            base_features.iloc[[perturb_idx]].fillna(0), 
            pert_features.iloc[[perturb_idx]].fillna(0)
        )
