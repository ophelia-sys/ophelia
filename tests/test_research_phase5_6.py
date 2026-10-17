import pytest
import pandas as pd
import numpy as np

def test_htf_alignment_causality():
    """
    Test that higher-timeframe data is aligned strictly causally.
    A 1h candle spanning 09:00 to 09:59 closes at 09:59:59.999.
    It should only be available for a decision at 10:00:00.
    """
    # Create 1m data for two hours
    dt_index = pd.date_range("2023-01-01 09:00:00", "2023-01-01 10:59:00", freq="1min")
    df = pd.DataFrame({'dt': dt_index, 'close': np.arange(120)})
    df['timestamp'] = df['dt'].astype(np.int64) // 10**6
    
    # Simulate 1h resample (right closed, label left to match pandas 'h'/'min')
    df.set_index('dt', inplace=True)
    df_1h = df['close'].resample('1h', label='left', closed='left').last().reset_index()
    # For a candle from 09:00 to 10:00, the last trade is at 09:59.
    # The candle completes right before 10:00:00.
    # So its state is known at 10:00:00.
    df_1h['available_at'] = df_1h['dt'] + pd.Timedelta(hours=1)
    
    # Merge back to 1m decisions using merge_asof
    df.reset_index(inplace=True)
    
    # Cast to ns for merge_asof consistency
    df['dt'] = df['dt'].astype('datetime64[ns]')
    df_1h['available_at'] = df_1h['available_at'].astype('datetime64[ns]')
    
    merged = pd.merge_asof(
        df,
        df_1h[['available_at', 'close']].rename(columns={'close': 'prev_1h_close'}),
        left_on='dt',
        right_on='available_at',
        direction='backward'
    )
    
    # For a decision at 09:59:00, prev_1h_close should be NaN (09:00 candle not complete)
    assert pd.isna(merged.loc[merged['dt'] == pd.Timestamp("2023-01-01 09:59:00"), 'prev_1h_close'].iloc[0])
    
    # For a decision at 10:00:00, prev_1h_close should be 59 (from 09:59)
    assert merged.loc[merged['dt'] == pd.Timestamp("2023-01-01 10:00:00"), 'prev_1h_close'].iloc[0] == 59
    
    # For a decision at 10:30:00, prev_1h_close should still be 59
    assert merged.loc[merged['dt'] == pd.Timestamp("2023-01-01 10:30:00"), 'prev_1h_close'].iloc[0] == 59
    
    # For a decision at 11:00:00, prev_1h_close should be 119 (from 10:59)
    # 11:00 is out of range of df, but if it existed:
    df_11 = pd.DataFrame({'dt': [pd.Timestamp("2023-01-01 11:00:00")]})
    df_11['dt'] = df_11['dt'].astype('datetime64[ns]')
    
    merged_11 = pd.merge_asof(
        df_11,
        df_1h[['available_at', 'close']].rename(columns={'close': 'prev_1h_close'}),
        left_on='dt',
        right_on='available_at',
        direction='backward'
    )
    assert merged_11['prev_1h_close'].iloc[0] == 119


def test_maker_economics_adverse_selection():
    """
    Test calculation of adverse selection and expected net maker value.
    """
    # Suppose we place a bid at 100, and it fills.
    # 1 minute later, the mid price is 95. Adverse selection = -5.
    
    # Create synthetic book flow
    # Time 0: Bid 100, Ask 101. Fill at 100.
    # Time 1m: Bid 94, Ask 96. Mid = 95.
    data = [
        {'time_idx': 0, 'bid_p': 100.0, 'ask_p': 101.0, 'mid_p': 100.5},
        {'time_idx': 1, 'bid_p': 94.0,  'ask_p': 96.0,  'mid_p': 95.0}
    ]
    df = pd.DataFrame(data)
    
    # Fill price for a resting bid is 100.0
    fill_price = 100.0
    
    # Adverse selection 1 period later:
    future_mid = df.loc[1, 'mid_p']
    adverse_selection = future_mid - fill_price # 95.0 - 100.0 = -5.0
    
    assert adverse_selection == -5.0
    
    # Spread capture: True capture if price reverts? 
    # The half-spread captured initially was 0.5.
    # But after adverse selection, Net = +0.5 (spread) - 5.5 (mid move) = -5.0?
    # Actually, Net Pnl = future_mid - fill_price = -5.0. 
    # Spread capture vs mid at time 0 is 0.5. 
    # MTM movement of mid is -5.5.
    # Net = 0.5 + (-5.5) = -5.0. Matches.
    
    spread_capture = df.loc[0, 'mid_p'] - fill_price
    assert spread_capture == 0.5
    
    mtm_move = future_mid - df.loc[0, 'mid_p']
    assert mtm_move == -5.5
    
    assert spread_capture + mtm_move == adverse_selection
