import pytest
import pandas as pd
import numpy as np
from institutional.volatility import calculate_realized_volatility
from institutional.momentum import calculate_standardized_momentum

def test_causality_realized_volatility():
    """
    Ensure that changing a future value does NOT change the past feature output.
    """
    df1 = pd.DataFrame({
        'close': np.random.randn(100).cumsum() + 100
    })
    # Copy df and change the last value only
    df2 = df1.copy()
    df2.loc[99, 'close'] = df2.loc[99, 'close'] + 50.0 
    
    rv1 = calculate_realized_volatility(df1, window=10)
    rv2 = calculate_realized_volatility(df2, window=10)
    
    # Values at index 98 and before must be exactly equal
    pd.testing.assert_series_equal(rv1.iloc[:99], rv2.iloc[:99])
    
    # Value at index 99 should differ
    assert rv1.iloc[99] != rv2.iloc[99]

def test_causality_momentum():
    df1 = pd.DataFrame({
        'close': np.random.randn(100).cumsum() + 100
    })
    df2 = df1.copy()
    df2.loc[99, 'close'] = df2.loc[99, 'close'] - 50.0 
    
    mom1 = calculate_standardized_momentum(df1, window=10)
    mom2 = calculate_standardized_momentum(df2, window=10)
    
    pd.testing.assert_series_equal(mom1.iloc[:99], mom2.iloc[:99])
    assert mom1.iloc[99] != mom2.iloc[99]
