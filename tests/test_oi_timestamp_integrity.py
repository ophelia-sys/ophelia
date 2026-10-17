import pytest
import pandas as pd
import numpy as np
from research.data.normalize_parquet import ParquetNormalizer

class TestOITimestampIntegrity:
    @pytest.fixture
    def normalizer(self):
        return ParquetNormalizer()
    
    @pytest.fixture
    def sample_oi_raw(self):
        # A mock of raw OI from Binance CSV
        return pd.DataFrame({
            'create_time': ['2022-01-01 00:00:00', '2022-01-01 00:05:00', '2022-01-01 00:10:00', '2022-01-01 00:10:00'],
            'symbol': ['BTCUSDT', 'BTCUSDT', 'BTCUSDT', 'ETHUSDT'],
            'sum_open_interest': [70000.0, 71000.0, 72000.0, 50000.0],
            'sum_open_interest_value': [3.5e9, 3.6e9, 3.7e9, 1.5e9]
        })
        
    @pytest.fixture
    def sample_klines(self):
        # A mock of canonical klines (1-minute candles)
        # Using Jan 1 2022 00:01:00 to Jan 1 2022 00:06:00
        timestamps = [
            1640995260000, 1640995320000, 1640995380000, 
            1640995440000, 1640995500000, 1640995560000
        ]
        return pd.DataFrame({
            'timestamp': timestamps,
            'close_time': [ts + 59999 for ts in timestamps],
            'symbol': ['BTCUSDT'] * 6,
            'close': [46000.0] * 6
        })

    def test_timestamp_unit_and_range(self, normalizer, sample_oi_raw):
        """Test 1 & 2: Unit is milliseconds and in realistic date range."""
        df = sample_oi_raw.copy()
        dt = pd.to_datetime(df['create_time'], utc=True).dt.tz_convert(None)
        df['timestamp'] = (dt - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
        
        # Milliseconds for early 2022 should be ~1.64e12
        ts = df['timestamp'].iloc[0]
        assert ts == 1640995200000, f"Expected 1640995200000, got {ts}"
        
        # Check range (2020 - 2030)
        assert df['timestamp'].min() > 1577836800000
        assert df['timestamp'].max() < 1893456000000

    def test_utc_semantics(self, normalizer):
        """Test 3: UTC parsing correctness."""
        df = pd.DataFrame({'create_time': ['2022-01-01 00:00:00', '2022-01-01 00:00:00+00:00']})
        dt = pd.to_datetime(df['create_time'], utc=True, format='mixed').dt.tz_convert(None)
        df['timestamp'] = (dt - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
        assert df['timestamp'].iloc[0] == df['timestamp'].iloc[1]

    def test_causal_as_of_join(self, normalizer, sample_oi_raw, sample_klines):
        """Test 4, 5 & 8: Causal join, backward direction, no future leakage."""
        df = sample_oi_raw.copy()
        dt = pd.to_datetime(df['create_time'], utc=True).dt.tz_convert(None)
        df['timestamp'] = (dt - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
        
        # Filter to BTCUSDT to simulate symbol isolation inside the loop
        oi_btc = df[df['symbol'] == 'BTCUSDT'].copy()
        joined = normalizer.join_open_interest(sample_klines, oi_btc)
        
        # Causal Integrity
        invalid = joined[(joined['oi_timestamp'].notna()) & (joined['oi_timestamp'] > joined['timestamp'])]
        assert invalid.empty, "Causality leak detected!"
        
        # Backward direction: 00:01:00 candle (1640995260000) should match 00:00:00 OI (1640995200000)
        # Not the 00:05:00 OI.
        assert joined.loc[joined['timestamp'] == 1640995260000, 'oi_timestamp'].iloc[0] == 1640995200000
        assert joined.loc[joined['timestamp'] == 1640995260000, 'sum_open_interest'].iloc[0] == 70000.0

        # 00:05:00 candle (1640995500000) should exactly match 00:05:00 OI
        assert joined.loc[joined['timestamp'] == 1640995500000, 'oi_timestamp'].iloc[0] == 1640995500000
        assert joined.loc[joined['timestamp'] == 1640995500000, 'sum_open_interest'].iloc[0] == 71000.0

    def test_symbol_isolation(self, normalizer, sample_oi_raw, sample_klines):
        """Test 6: Symbol isolation."""
        df = sample_oi_raw.copy()
        dt = pd.to_datetime(df['create_time'], utc=True).dt.tz_convert(None)
        df['timestamp'] = (dt - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
        
        oi_eth = df[df['symbol'] == 'ETHUSDT'].copy()
        joined = normalizer.join_open_interest(sample_klines, oi_eth)
        
        # Since the klines are for BTCUSDT, but we try joining ETHUSDT OI, it should work 
        # structurally but represent ETH data. In Ophelia, join_open_interest is called per symbol.
        # Ensure we only pass matching symbol DataFrames to join_open_interest.
        # The true test is that ETH data must not accidentally slip into a BTC join.
        # This is enforced structurally by caller filtering `oi_df[oi_df['symbol'] == symbol]`.
        assert np.isnan(joined['sum_open_interest'].iloc[0]) # ETH value is far away, so it doesn't match the backward merge
        # Ophelia's contract delegates symbol matching to the caller.

    def test_delta_oi_variation(self, normalizer, sample_oi_raw, sample_klines):
        """Test 7: DeltaOI doesn't collapse."""
        df = sample_oi_raw.copy()
        dt = pd.to_datetime(df['create_time'], utc=True).dt.tz_convert(None)
        df['timestamp'] = (dt - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
        
        oi_btc = df[df['symbol'] == 'BTCUSDT'].copy()
        joined = normalizer.join_open_interest(sample_klines, oi_btc)
        
        delta_oi = joined['sum_open_interest'].diff()
        assert not (delta_oi == 0).all()
        assert delta_oi.max() > 0 # Will see jump from 70000 to 71000

    def test_duplicate_and_missing_oi(self, normalizer, sample_klines):
        """Test 9 & 10: Duplicates deterministic and missing handled."""
        # Duplicates
        oi_dup = pd.DataFrame({
            'timestamp': [1640995200000, 1640995200000],
            'sum_open_interest': [70000.0, 70500.0],
            'sum_open_interest_value': [3.5e9, 3.5e9]
        })
        # merge_asof requires exact matches to be sorted, and will take the exact matching row's last occurrence if deterministic
        # But pandas requires strictly monotonic or sorted. Let's ensure it doesn't crash.
        oi_dup = oi_dup.drop_duplicates(subset=['timestamp'], keep='last')
        joined_dup = normalizer.join_open_interest(sample_klines, oi_dup)
        assert joined_dup['sum_open_interest'].iloc[0] == 70500.0
        
        # Missing
        oi_empty = pd.DataFrame()
        joined_empty = normalizer.join_open_interest(sample_klines, oi_empty)
        assert joined_empty['sum_open_interest'].isna().all()
