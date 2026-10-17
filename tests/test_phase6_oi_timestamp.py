import pytest
import pandas as pd
import numpy as np
import os
from research.data.normalize_parquet import ParquetNormalizer

def test_oi_timestamp_conversion_cases():
    normalizer = ParquetNormalizer()
    
    # Create dummy dataframe mimicking raw metrics
    data = {
        'create_time': [
            '2022-01-01 00:00:00',          # Naive (assumed UTC by Binance)
            '2022-01-01 00:05:00+00:00',    # Explicit UTC
            '2022-01-01 00:10:00',          # Another normal
            'invalid_date',                 # Malformed
            None,                           # Null
            '2022-01-01 00:10:00',          # Duplicate
            '2522-01-01 00:00:00',          # Future/Impossible
        ],
        'sum_open_interest': [100, 110, 120, 130, 140, 120, 150],
        'sum_open_interest_value': [1000, 1100, 1200, 1300, 1400, 1200, 1500]
    }
    df = pd.DataFrame(data)
    
    # Save to temp csv
    import tempfile
    temp_csv = os.path.join(tempfile.gettempdir(), "temp_test_metrics.csv")
    df.to_csv(temp_csv, index=False)
    
    try:
        parsed_df = normalizer.normalize_metrics(temp_csv)
        
        # Check parsed df
        assert parsed_df is not None
        assert not parsed_df.empty
        
        # Check integer type
        assert pd.api.types.is_integer_dtype(parsed_df['timestamp'])
        
        # Check expected values
        # 2022-01-01 00:00:00 UTC = 1640995200000 ms
        assert parsed_df.iloc[0]['timestamp'] == 1640995200000
        # 2022-01-01 00:05:00 UTC = 1640995500000 ms
        assert parsed_df.iloc[1]['timestamp'] == 1640995500000
        
        # Malformed and Null should be dropped, duplicate dropped, future dropped
        assert len(parsed_df) == 3  # 00:00, 00:05, 00:10
        
        # Wait, I need to implement the dropping in normalize_metrics
    finally:
        if os.path.exists(temp_csv):
            os.remove(temp_csv)

def test_causal_oi_join():
    normalizer = ParquetNormalizer()
    
    # klines: T-10m, T-5m, T, T+5m
    kline_data = {
        'timestamp': [
            1000000,  # T-10m
            1300000,  # T-5m
            1600000,  # T
            1900000,  # T+5m
        ]
    }
    kline_df = pd.DataFrame(kline_data)
    
    # oi: T-10m, T-5m, T+5m
    oi_data = {
        'timestamp': [
            1000000,  # Exact match for T-10m
            1300000,  # Exact match for T-5m
            1900000,  # Exact match for T+5m
        ],
        'sum_open_interest': [10, 20, 30],
        'sum_open_interest_value': [100, 200, 300]
    }
    oi_df = pd.DataFrame(oi_data)
    
    joined = normalizer.join_open_interest(kline_df, oi_df)
    
    # At T (1600000), the latest available OI is at T-5m (1300000)
    val_at_t = joined[joined['timestamp'] == 1600000].iloc[0]
    assert val_at_t['sum_open_interest'] == 20
    assert val_at_t['oi_timestamp'] == 1300000
    
    # Ensure no future leakage
    assert (joined['oi_timestamp'].dropna() <= joined['timestamp'].dropna()).all()

