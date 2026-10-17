import numpy as np
import pandas as pd
import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.ml4t_benchmark.features.positioning import engineer_positioning_features

def test_p1_positioning_causality_exact_join():
    """
    Tests exact timestamp join in engineer_positioning_features to ensure strict causal boundary.
    """
    # 1. Create a fake OHLCV dataset on a continuous 5m grid
    timestamps = pd.date_range("2023-01-01 00:00:00", periods=10, freq="5min", tz="UTC")
    
    df_ohlcv = pd.DataFrame({
        'timestamp': timestamps,
        'close': np.linspace(100, 110, 10),
        'cvd_delta_1h': np.random.randn(10)
    })
    
    # 2. Create OI dataset with various gaps and edge cases
    # Target decision times for OHLCV rows:
    # row 0: 00:05:00
    # row 1: 00:10:00
    # row 2: 00:15:00
    # row 3: 00:20:00
    # row 4: 00:25:00
    # row 5: 00:30:00
    # row 6: 00:35:00
    # row 7: 00:40:00
    # row 8: 00:45:00
    # row 9: 00:50:00

    oi_records = [
        {'timestamp': pd.Timestamp("2023-01-01 00:00:00", tz="UTC"), 'sum_open_interest': 999},  # Before first decision
        {'timestamp': pd.Timestamp("2023-01-01 00:05:00", tz="UTC"), 'sum_open_interest': 1000}, # A. Continuous (Row 0 target)
        {'timestamp': pd.Timestamp("2023-01-01 00:10:00", tz="UTC"), 'sum_open_interest': 1010}, # A. Continuous (Row 1 target)
        # B. One missing timestamp at 00:15:00
        {'timestamp': pd.Timestamp("2023-01-01 00:16:00", tz="UTC"), 'sum_open_interest': 1016}, # G. Later than 00:15:00 (Should NOT be used for Row 2)
        # C. Multiple consecutive missing timestamps: 00:20:00, 00:25:00 missing
        {'timestamp': pd.Timestamp("2023-01-01 00:24:59", tz="UTC"), 'sum_open_interest': 1024}, # H. Earlier than 00:25:00 (Should NOT be used for Row 4)
        {'timestamp': pd.Timestamp("2023-01-01 00:30:00", tz="UTC"), 'sum_open_interest': 1030}, # Matches Row 5
        {'timestamp': pd.Timestamp("2023-01-01 00:35:00", tz="UTC"), 'sum_open_interest': 1035}, # Matches Row 6
        {'timestamp': pd.Timestamp("2023-01-01 00:40:00", tz="UTC"), 'sum_open_interest': 1040}, # Matches Row 7
        {'timestamp': pd.Timestamp("2023-01-01 00:45:00", tz="UTC"), 'sum_open_interest': 1045}, # Matches Row 8
        {'timestamp': pd.Timestamp("2023-01-01 00:50:00", tz="UTC"), 'sum_open_interest': 1050}, # E. Last timestamp (Matches Row 9)
    ]
    
    df_oi = pd.DataFrame(oi_records)
    
    # 3. Engineer features
    df_res = engineer_positioning_features(df_ohlcv, df_oi)
    
    # 4. Assertions
    
    # F. Exact decision boundary matching
    # row 0 decision = 00:05:00 -> OI=1000
    assert df_res.loc[0, 'aligned_oi'] == 1000
    
    # A. Continuous timestamps
    # row 1 decision = 00:10:00 -> OI=1010
    assert df_res.loc[1, 'aligned_oi'] == 1010
    
    # B. One missing timestamp
    # row 2 decision = 00:15:00 -> missing, OI=NaN
    assert pd.isna(df_res.loc[2, 'aligned_oi'])
    
    # G. OI timestamp later than decision_time must never be selected
    # row 2 has a value at 00:16:00, it should NOT substitute
    
    # C. Multiple missing timestamps
    # row 3 decision = 00:20:00 -> missing, OI=NaN
    assert pd.isna(df_res.loc[3, 'aligned_oi'])
    
    # H. OI timestamp earlier than decision_time must not substitute
    # row 4 decision = 00:25:00 -> missing (closest is 00:24:59), OI=NaN
    assert pd.isna(df_res.loc[4, 'aligned_oi'])
    
    # E. Last available timestamp
    # row 9 decision = 00:50:00 -> OI=1050
    assert df_res.loc[9, 'aligned_oi'] == 1050
    
    # Global Invariant: For every non-NaN observation, OI_timestamp == OHLCV_timestamp + 5m
    for idx, row in df_res.iterrows():
        if not pd.isna(row['aligned_oi']):
            expected_decision_time = row['timestamp'] + pd.Timedelta(minutes=5)
            # Find the actual OI value mapped
            oi_row = df_oi[df_oi['timestamp'] == expected_decision_time]
            assert not oi_row.empty, "Aligned OI value does not correspond to an exact decision_time match in the source data!"
            assert row['aligned_oi'] == oi_row.iloc[0]['sum_open_interest']
            
if __name__ == "__main__":
    pytest.main([__file__])
