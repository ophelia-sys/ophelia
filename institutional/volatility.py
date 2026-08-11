import numpy as np
import pandas as pd

def calculate_log_returns(df: pd.DataFrame, horizon: int = 1) -> pd.Series:
    """Calculate n-period log returns."""
    close = df["close"].astype(float)
    return np.log(close / close.shift(horizon))

def calculate_realized_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Realized Volatility: RV_N = sqrt(sum(r_t^2))
    Does not apply arbitrary annualization. Returns native timeframe volatility.
    """
    returns = calculate_log_returns(df, 1)
    squared_returns = returns ** 2
    return np.sqrt(squared_returns.rolling(window=window).sum())

def calculate_parkinson_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Parkinson volatility estimator based on High and Low prices.
    sigma_P = sqrt( 1/(4*ln(2)) * sum(ln(H/L)^2) )
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    
    hl_log_sq = np.log(high / low) ** 2
    factor = 1.0 / (4.0 * np.log(2.0))
    
    # We aggregate the sum over the window
    return np.sqrt(factor * hl_log_sq.rolling(window=window).sum())

def calculate_garman_klass_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Garman-Klass volatility estimator based on OHLC prices.
    sigma_GK = sqrt( sum( 0.5*ln(H/L)^2 - (2ln2 - 1)*ln(C/O)^2 ) )
    """
    open_p = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    
    hl_term = 0.5 * (np.log(high / low) ** 2)
    co_term = (2.0 * np.log(2.0) - 1.0) * (np.log(close / open_p) ** 2)
    
    gk_vol_sq = (hl_term - co_term).rolling(window=window).sum()
    return np.sqrt(gk_vol_sq.clip(lower=0))

def calculate_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Average True Range (ATR).
    TR = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|)
    ATR_N = rolling_mean(TR, N)
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = df["close"].astype(float).shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=window).mean()
