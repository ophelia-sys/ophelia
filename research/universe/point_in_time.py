import pandas as pd
import numpy as np

def compute_historical_eligibility(metadata_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes point-in-time eligibility for all symbols across all available timestamps.
    
    metadata_df: DataFrame with columns ['symbol', 'timestamp', 'quote_volume']
                 where timestamp is a pandas datetime object for the daily kline.
                 
    Returns a DataFrame containing:
    ['timestamp', 'symbol', 'eligible', 'eligibility_reason', 'history_age_days', 'rolling_14d_median_vol', 'missing_bars_14d']
    """
    df = metadata_df.copy()
    
    # Ensure sorted by symbol and timestamp
    df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Compute basic rolling metrics grouped by symbol
    # Note: Using shift(1) is critical to ensure eligibility on day T is based ONLY on data up to T-1
    df['prev_quote_vol'] = df.groupby('symbol')['quote_volume'].shift(1)
    
    # Rolling 14-day median volume (requires min_periods=1 to start computing early)
    df['rolling_14d_median_vol'] = df.groupby('symbol')['prev_quote_vol'].transform(
        lambda x: x.rolling(window=14, min_periods=1).median()
    )
    
    # Compute history age: number of calendar days since the first observation of the symbol
    # Again, evaluated prior to current day, so shift(1) is not strictly needed for the min date,
    # but we measure age based on (T - first_date).
    first_dates = df.groupby('symbol')['timestamp'].transform('min')
    df['history_age_days'] = (df['timestamp'] - first_dates).dt.days
    
    # Data continuity: check missing bars in trailing 14 days
    # If the symbol has gaps in dates, those dates won't exist in the dataframe.
    # To check missing bars properly, we check if the difference between the 14th previous date and current date is 14 days.
    # Alternatively, we can reindex the dataframe to a full date grid, but a simpler proxy is:
    # count of observations in last 14 days = 14. If less, we have missing days.
    # To use a time-based window, we must pass on='timestamp'
    df['obs_count_14d'] = df.groupby('symbol').rolling(window='14D', on='timestamp', closed='left')['timestamp'].count().reset_index(drop=True).fillna(0)
    
    df['missing_bars_14d'] = 14 - df['obs_count_14d']
    # If age is < 14, missing bars will naturally be > 0. We only enforce this if age >= 14.
    
    # Evaluate Eligibility
    def determine_eligibility(row):
        if row['history_age_days'] < 30:
            return False, "INSUFFICIENT_HISTORY"
        
        if row['missing_bars_14d'] > 1:
            return False, "POOR_CONTINUITY"
            
        if pd.isna(row['rolling_14d_median_vol']) or row['rolling_14d_median_vol'] < 25000000:
            return False, "INSUFFICIENT_VOLUME"
            
        return True, "ELIGIBLE"

    # Apply rules
    results = df.apply(determine_eligibility, axis=1)
    df['eligible'] = [r[0] for r in results]
    df['eligibility_reason'] = [r[1] for r in results]
    
    return df[['timestamp', 'symbol', 'eligible', 'eligibility_reason', 'history_age_days', 'rolling_14d_median_vol', 'missing_bars_14d']]

def get_research_universe(timestamp: pd.Timestamp, metadata_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns exactly the instruments eligible at time `timestamp` based ONLY on information <= `timestamp`.
    """
    # Filter metadata up to and including the timestamp (the engine internally shifts by 1)
    # We pass data up to timestamp, and then extract the result for timestamp
    sub_df = metadata_df[metadata_df['timestamp'] <= timestamp].copy()
    
    # Ensure there's data
    if sub_df.empty:
        return pd.DataFrame()
        
    eligibility_df = compute_historical_eligibility(sub_df)
    
    # Filter to requested timestamp
    target_df = eligibility_df[eligibility_df['timestamp'] == timestamp].copy()
    return target_df
