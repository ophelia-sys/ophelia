import pytest
import pandas as pd
import numpy as np
from institutional.normalization import calculate_robust_z_score
from research.data.normalize_parquet import ParquetNormalizer

def test_zero_mad_unavailable_policy():
    """
    Ensures that when MAD is exactly 0.0, the calculation does not manufacture extreme Z-scores.
    If the current observation matches the constant median, Z=0.0.
    If it deviates, Z=NaN.
    """
    # Create a series with a perfectly flat history (MAD=0) followed by a deviation
    # Window = 5
    data = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 105.0]
    series = pd.Series(data)
    
    # Calculate Z-scores with legacy policy (should blow up)
    legacy_z = calculate_robust_z_score(series, window=5, zero_dispersion_policy="legacy")
    # For index 5 (val=100.0): median=100.0, mad=0 -> max(0, 1e-6)=1e-6 -> Z = 0 / 1e-6 = 0.0
    # For index 6 (val=105.0): median=100.0, mad=0 -> max(0, 1e-6)=1e-6 -> Z = 5 / 1e-6 = 5000000.0
    assert legacy_z.iloc[5] == 0.0
    assert legacy_z.iloc[6] == 5000000.0

    # Calculate Z-scores with 'unavailable' policy (Phase 6 Definition A)
    unavail_z = calculate_robust_z_score(series, window=5, zero_dispersion_policy="unavailable")
    
    # For index 5 (val=100.0): median=100.0, mad=0 -> matches median -> Z = 0.0
    assert unavail_z.iloc[5] == 0.0
    
    # For index 6 (val=105.0): median=100.0, mad=0 -> deviates from median -> Z = NaN
    assert np.isnan(unavail_z.iloc[6])

def test_definition_a_causal_mapping():
    """
    Tests that native 5m DeltaOI and Z_DeltaOI are mapped perfectly to the 1m grid
    without future leakage.
    """
    normalizer = ParquetNormalizer()
    
    # 1m K-lines
    klines = pd.DataFrame({
        'timestamp': [100, 160, 220, 280, 340, 400]
    })
    
    # 5m Native OI Event Grid (e.g. 100, 400)
    oi_df = pd.DataFrame({
        'timestamp': [100, 400],
        'sum_open_interest': [10.0, 15.0],
        'sum_open_interest_value': [100.0, 150.0],
        'delta_oi': [0.0, 5.0],
        'Z_DeltaOI': [np.nan, 2.5]  # Pretend we calculated a Z-score
    })
    
    joined = normalizer.join_open_interest(klines, oi_df)
    
    # At T=160, the latest OI is from T=100
    assert joined.loc[1, 'oi_timestamp'] == 100
    assert joined.loc[1, 'sum_open_interest'] == 10.0
    assert joined.loc[1, 'delta_oi'] == 0.0
    assert np.isnan(joined.loc[1, 'Z_DeltaOI'])
    
    # At T=400, the latest OI is from T=400
    assert joined.loc[5, 'oi_timestamp'] == 400
    assert joined.loc[5, 'delta_oi'] == 5.0
    assert joined.loc[5, 'Z_DeltaOI'] == 2.5
    
    # Verify causality universally
    valid = joined.dropna(subset=['oi_timestamp'])
    assert (valid['oi_timestamp'] <= valid['timestamp']).all()
