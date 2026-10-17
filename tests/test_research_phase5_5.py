import pandas as pd
import numpy as np
import pytest
import os
import sys

# Add path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from research.experiments.exp_027_mtf_context import compute_causal_mtf

def test_mtf_causality():
    # Create synthetic 1m dataset
    dates = pd.date_range(start='2023-10-30 00:00:00', end='2023-11-01 12:00:00', freq='1min')
    df = pd.DataFrame({
        'dt': dates,
        'timestamp': dates.astype('datetime64[ms]').astype(np.int64),
        'open': np.linspace(100, 200, len(dates)),
        'high': np.linspace(105, 205, len(dates)),
        'low': np.linspace(95, 195, len(dates)),
        'close': np.linspace(102, 202, len(dates)),
        'volume': np.random.rand(len(dates)) * 100,
        'cvd': np.random.rand(len(dates)) * 10,
        'snapshot_ofi_proxy': np.random.rand(len(dates)) * 10
    })
    
    # Process through the MTF generator
    context_df = compute_causal_mtf(df)
    
    row_10_10 = context_df[context_df['dt'] == pd.to_datetime('2023-11-01 10:10:00')].iloc[0]
    row_10_14 = context_df[context_df['dt'] == pd.to_datetime('2023-11-01 10:14:00')].iloc[0]
    
    assert row_10_10['1h_volatility'] == row_10_14['1h_volatility'], "HTF features should not change intra-candle"
    
    assert '1h_volatility' in context_df.columns
    assert 'regime_vol' in context_df.columns
    assert 'regime_trend' in context_df.columns
    
def test_regime_stability():
    dates = pd.date_range(start='2023-10-25', end='2023-11-03', freq='1min')
    df = pd.DataFrame({
        'dt': dates,
        'timestamp': dates.astype('datetime64[ms]').astype(np.int64),
        'open': np.linspace(100, 200, len(dates)),
        'high': np.linspace(105, 205, len(dates)),
        'low': np.linspace(95, 195, len(dates)),
        'close': np.linspace(102, 202, len(dates)) + np.sin(np.linspace(0, 50, len(dates)))*5,
        'volume': np.random.rand(len(dates)) * 100,
        'cvd': np.random.rand(len(dates)) * 10,
        'snapshot_ofi_proxy': np.random.rand(len(dates)) * 10
    })
    
    context_df = compute_causal_mtf(df)
    
    valid_df = context_df.dropna(subset=['regime_vol', 'regime_trend', 'regime_mom'])
    
    vol_counts = valid_df['regime_vol'].value_counts().sum()
    assert vol_counts == len(valid_df), "Volatility regimes did not partition cleanly"
    
    trend_counts = valid_df['regime_trend'].value_counts().sum()
    assert trend_counts == len(valid_df), "Trend regimes did not partition cleanly"
