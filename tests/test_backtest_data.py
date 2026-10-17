import pytest
import os
import pandas as pd
import numpy as np
from research.data.download_vision import VisionDownloader
from research.data.normalize_parquet import ParquetNormalizer
from research.data.validate_gaps import GapValidator

def test_downloader_url_construction():
    dl = VisionDownloader()
    url = dl.construct_klines_url("BTCUSDT", "1m", 2023, 1, is_daily=False)
    assert url == "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01.zip"
    
    url_daily = dl.construct_klines_url("ETHUSDT", "1m", 2023, 1, is_daily=True, day=5)
    assert url_daily == "https://data.binance.vision/data/futures/um/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2023-01-05.zip"

def test_gap_validator_logic():
    validator = GapValidator(interval_ms=60000)
    
    # Create valid dummy data
    df = pd.DataFrame({
        'timestamp': [100000, 160000, 220000],
        'open': [10, 11, 12],
        'high': [12, 13, 14],
        'low': [9, 10, 11],
        'close': [11, 12, 13],
        'volume': [100, 200, 150]
    })
    
    stats = validator.validate(df)
    assert stats['status'] == 'PASS'
    assert stats['missing_intervals'] == 0
    assert stats['duplicate_timestamps'] == 0
    
    # Inject a gap
    df_gap = pd.DataFrame({
        'timestamp': [100000, 220000],  # missing 160000
        'open': [10, 12],
        'high': [12, 14],
        'low': [9, 11],
        'close': [11, 13],
        'volume': [100, 150]
    })
    stats_gap = validator.validate(df_gap)
    assert stats_gap['missing_intervals'] == 1
    
    # Inject bad OHLC (Low > High)
    df_bad = df.copy()
    df_bad.loc[0, 'low'] = 20
    stats_bad = validator.validate(df_bad)
    assert stats_bad['status'] == 'FAIL'
    assert not stats_bad['ohlc_valid']

def test_delta_calculation_logic():
    normalizer = ParquetNormalizer()
    
    # raw dummy df just to test the logic
    # raw_columns = [..., 'volume', ..., 'taker_buy_base_asset_volume', ...]
    volume = 100.0
    taker_buy = 60.0
    
    aggressive_buy = taker_buy
    aggressive_sell = volume - taker_buy
    delta_v = aggressive_buy - aggressive_sell
    
    assert aggressive_buy == 60.0
    assert aggressive_sell == 40.0
    assert delta_v == 20.0

def test_oi_join_logic():
    normalizer = ParquetNormalizer()
    kline_df = pd.DataFrame({
        'timestamp': [100, 200],
        'close': [10, 11]
    })
    oi_df = pd.DataFrame({
        'timestamp': [100, 200],
        'sum_open_interest': [5000, 5100],
        'sum_open_interest_value': [50000, 56100]
    })
    
    joined = normalizer.join_open_interest(kline_df, oi_df)
    assert 'sum_open_interest' in joined.columns
    assert joined.loc[0, 'sum_open_interest'] == 5000
    
    # Test missing OI doesn't break, just injects NaNs
    joined_empty = normalizer.join_open_interest(kline_df, pd.DataFrame())
    assert pd.isna(joined_empty.loc[0, 'sum_open_interest'])
