import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from point_in_time import compute_historical_eligibility, get_research_universe

def create_mock_metadata():
    data = []
    start_date = datetime(2022, 1, 1)
    
    # Symbol 1: A highly liquid coin that survives forever (e.g. BTC)
    for i in range(100):
        data.append({
            'symbol': 'BTCUSDT',
            'timestamp': start_date + timedelta(days=i),
            'quote_volume': 50000000.0  # 50M daily
        })
        
    # Symbol 2: A delisted coin (e.g. LUNAUSDT). Liquid for 40 days, then dies.
    for i in range(40):
        data.append({
            'symbol': 'LUNAUSDT',
            'timestamp': start_date + timedelta(days=i),
            'quote_volume': 100000000.0  # 100M daily
        })
        
    # Symbol 3: A future winner. Illiquid for 50 days (10M vol), then becomes liquid (50M vol)
    for i in range(100):
        vol = 10000000.0 if i < 50 else 50000000.0
        data.append({
            'symbol': 'SOLUSDT',
            'timestamp': start_date + timedelta(days=i),
            'quote_volume': vol
        })
        
    # Symbol 4: Missing data / bad continuity
    for i in range(100):
        if i not in [35, 36, 37]: # missing 3 consecutive days after 30 days
            data.append({
                'symbol': 'BADUSDT',
                'timestamp': start_date + timedelta(days=i),
                'quote_volume': 50000000.0
            })
            
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def test_history_requirement():
    df = create_mock_metadata()
    res = compute_historical_eligibility(df)
    
    btc_res = res[res['symbol'] == 'BTCUSDT'].set_index('timestamp')
    
    # Day 0 to 29 (history age 0 to 29): Should be INSUFFICIENT_HISTORY
    assert btc_res.loc[pd.Timestamp('2022-01-20'), 'eligible'] == False
    assert btc_res.loc[pd.Timestamp('2022-01-20'), 'eligibility_reason'] == 'INSUFFICIENT_HISTORY'
    
    # Day 30: Should be ELIGIBLE (history_age_days = 30)
    assert btc_res.loc[pd.Timestamp('2022-01-31'), 'eligible'] == True
    assert btc_res.loc[pd.Timestamp('2022-01-31'), 'eligibility_reason'] == 'ELIGIBLE'

def test_delisted_symbol_inclusion():
    df = create_mock_metadata()
    res = compute_historical_eligibility(df)
    
    luna_res = res[res['symbol'] == 'LUNAUSDT'].set_index('timestamp')
    
    # On day 35, LUNA is liquid and has history. It should be eligible.
    assert luna_res.loc[pd.Timestamp('2022-02-05'), 'eligible'] == True
    
    # LUNA's last day is 2022-02-09. If we check universe on 2022-02-15, LUNA should NOT be in the dataframe for that day.
    target_date = pd.Timestamp('2022-02-15')
    univ = get_research_universe(target_date, df)
    assert 'LUNAUSDT' not in univ['symbol'].values

def test_future_leakage():
    df = create_mock_metadata()
    res = compute_historical_eligibility(df)
    
    sol_res = res[res['symbol'] == 'SOLUSDT'].set_index('timestamp')
    
    # On day 40 (2022-02-10), SOL is still illiquid (10M volume). Should be INSUFFICIENT_VOLUME
    assert sol_res.loc[pd.Timestamp('2022-02-10'), 'eligible'] == False
    assert sol_res.loc[pd.Timestamp('2022-02-10'), 'eligibility_reason'] == 'INSUFFICIENT_VOLUME'
    
    # On day 50, volume jumps to 50M. But it's evaluated trailing, so day 51 will start seeing 50M in the window.
    # We need the median to rise above 25M, which takes 7 days of 50M volume in a 14-day window.
    # By day 60 (2022-03-02), it should be ELIGIBLE.
    assert sol_res.loc[pd.Timestamp('2022-03-02'), 'eligible'] == True

def test_poor_continuity():
    df = create_mock_metadata()
    res = compute_historical_eligibility(df)
    
    bad_res = res[res['symbol'] == 'BADUSDT'].set_index('timestamp')
    
    # On day 34, it is eligible
    assert bad_res.loc[pd.Timestamp('2022-02-04'), 'eligible'] == True
    
    # It misses days 35, 36, 37. On day 38 (2022-02-08), it has 3 missing bars in trailing 14d.
    assert bad_res.loc[pd.Timestamp('2022-02-08'), 'eligible'] == False
    assert bad_res.loc[pd.Timestamp('2022-02-08'), 'eligibility_reason'] == 'POOR_CONTINUITY'

if __name__ == '__main__':
    pytest.main([__file__])
