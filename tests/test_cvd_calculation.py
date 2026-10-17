import pandas as pd
import numpy as np
import pytest

def process_chunk_to_1m(df):
    """
    Deterministic mapping for CVD aggregation to 1m buckets.
    """
    # Verify semantics: is_buyer_maker == False -> Taker Buy (positive)
    df['signed_volume'] = np.where(df['is_buyer_maker'], -df['quantity'], df['quantity'])
    df['buy_volume'] = np.where(~df['is_buyer_maker'], df['quantity'], 0.0)
    df['sell_volume'] = np.where(df['is_buyer_maker'], df['quantity'], 0.0)
    
    # Timestamps are ms, convert to datetime
    df['datetime'] = pd.to_datetime(df['transact_time'], unit='ms')
    
    # Flooring to 1m boundary
    df['minute'] = df['datetime'].dt.floor('1min')
    
    agg = df.groupby('minute').agg(
        delta_volume=('signed_volume', 'sum'),
        total_volume=('quantity', 'sum'),
        buy_volume=('buy_volume', 'sum'),
        sell_volume=('sell_volume', 'sum')
    ).reset_index()
    
    return agg

def aggregate_higher_timeframe(df_1m, freq):
    """
    Aggregates 1m CVD to 5m or 15m.
    """
    # Resample using the exact boundary
    df_1m = df_1m.set_index('minute')
    agg = df_1m.resample(freq).agg({
        'delta_volume': 'sum',
        'total_volume': 'sum',
        'buy_volume': 'sum',
        'sell_volume': 'sum'
    }).reset_index()
    return agg

def test_buyer_maker_sign_mapping():
    # is_buyer_maker: True -> Maker was buyer -> Taker was seller -> negative CVD
    # is_buyer_maker: False -> Maker was seller -> Taker was buyer -> positive CVD
    df = pd.DataFrame({
        'transact_time': [1640995200000, 1640995201000],
        'quantity': [10.0, 5.0],
        'is_buyer_maker': [True, False]
    })
    
    res = process_chunk_to_1m(df)
    assert len(res) == 1
    assert res['delta_volume'].iloc[0] == -10.0 + 5.0  # -5.0
    assert res['buy_volume'].iloc[0] == 5.0
    assert res['sell_volume'].iloc[0] == 10.0
    assert res['total_volume'].iloc[0] == 15.0

def test_quantity_aggregation():
    df = pd.DataFrame({
        'transact_time': [1640995200000, 1640995205000, 1640995210000],
        'quantity': [1.0, 2.0, 3.0],
        'is_buyer_maker': [False, False, True] # buys: 1+2=3, sell: 3
    })
    res = process_chunk_to_1m(df)
    assert res['delta_volume'].iloc[0] == 0.0
    assert res['buy_volume'].iloc[0] == 3.0
    assert res['sell_volume'].iloc[0] == 3.0
    assert res['total_volume'].iloc[0] == 6.0

def test_higher_timeframe_aggregation():
    df = pd.DataFrame({
        'transact_time': [
            1640995200000, # 00:00:00
            1640995260000, # 00:01:00
            1640995500000, # 00:05:00
        ],
        'quantity': [10.0, 20.0, 30.0],
        'is_buyer_maker': [False, True, False]
    })
    res_1m = process_chunk_to_1m(df)
    assert len(res_1m) == 3
    
    res_5m = aggregate_higher_timeframe(res_1m, '5min')
    assert len(res_5m) == 2
    
    # 00:00 bucket contains 00:00 and 00:01
    assert res_5m['minute'].iloc[0] == pd.Timestamp('2022-01-01 00:00:00')
    assert res_5m['delta_volume'].iloc[0] == 10.0 - 20.0 # -10.0
    
    # 00:05 bucket contains 00:05
    assert res_5m['minute'].iloc[1] == pd.Timestamp('2022-01-01 00:05:00')
    assert res_5m['delta_volume'].iloc[1] == 30.0

def test_conservation_of_volume():
    np.random.seed(42)
    df = pd.DataFrame({
        'transact_time': np.random.randint(1640995200000, 1640995200000 + 3600000, size=1000),
        'quantity': np.random.uniform(0.1, 10.0, size=1000),
        'is_buyer_maker': np.random.choice([True, False], size=1000)
    })
    res_1m = process_chunk_to_1m(df)
    res_15m = aggregate_higher_timeframe(res_1m, '15min')
    
    raw_delta = np.where(df['is_buyer_maker'], -df['quantity'], df['quantity']).sum()
    assert np.isclose(res_1m['delta_volume'].sum(), raw_delta)
    assert np.isclose(res_15m['delta_volume'].sum(), raw_delta)
    
    assert np.isclose(res_1m['buy_volume'].sum() - res_1m['sell_volume'].sum(), res_1m['delta_volume'].sum())
    assert np.isclose(res_1m['buy_volume'].sum() + res_1m['sell_volume'].sum(), res_1m['total_volume'].sum())
