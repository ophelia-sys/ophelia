import numpy as np
import pandas as pd
from indicators.ema import EMA


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's smoothing (RMA) is standard for ATR:
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr


def calculate_natr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Normalized ATR (NATR)."""
    atr = calculate_atr(df, period)
    close = df["close"].astype(float)
    # Avoid division by zero
    close = close.replace(0, np.nan)
    return (atr / close) * 100.0


def calculate_er(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """
    Calculate Kaufman Efficiency Ratio (ER).
    ER = abs(Close[t] - Close[t-N]) / sum(abs(Close[i] - Close[i-1]))
    """
    close = df["close"].astype(float)
    
    # Net change over period
    change = (close - close.shift(period)).abs()
    
    # Sum of absolute period-to-period changes (volatility)
    volatility = close.diff().abs().rolling(window=period).sum()
    
    er = change / volatility.replace(0, np.nan) # prevent div zero
    er = er.fillna(0.0) # If volatility is 0, ER is 0
    return er


def calculate_nes(df: pd.DataFrame, ema_fast: int = 9, ema_slow: int = 21, atr_period: int = 14) -> pd.Series:
    """
    Calculate Normalized EMA Spread (NES).
    NES = (EMA9 - EMA21) / ATR14
    """
    ema_fast_series = EMA.calculate(df, ema_fast)
    ema_slow_series = EMA.calculate(df, ema_slow)
    atr = calculate_atr(df, atr_period)
    
    nes = (ema_fast_series - ema_slow_series) / atr.replace(0, np.nan)
    return nes.fillna(0.0)


def calculate_nslope(df: pd.DataFrame, ema_period: int = 21, slope_lookback: int = 3, atr_period: int = 14) -> pd.Series:
    """
    Calculate Normalized EMA Slope (NSlope).
    NSlope = ((EMA21[t] - EMA21[t-k]) / k) / ATR14
    """
    ema_series = EMA.calculate(df, ema_period)
    atr = calculate_atr(df, atr_period)
    
    raw_slope = (ema_series - ema_series.shift(slope_lookback)) / slope_lookback
    nslope = raw_slope / atr.replace(0, np.nan)
    return nslope.fillna(0.0)


def calculate_bbs(df: pd.DataFrame, period: int = 20, stdev: float = 2.0, baseline_period: int = 50) -> pd.Series:
    """
    Calculate Bollinger Bandwidth Squeeze (BBS).
    BBW = (Upper - Lower) / Middle
    BBS = BBW / SMA(BBW, baseline_period)
    """
    close = df["close"].astype(float)
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    
    upper = sma + (std * stdev)
    lower = sma - (std * stdev)
    
    bbw = (upper - lower) / sma.replace(0, np.nan)
    bbw_sma = bbw.rolling(window=baseline_period).mean()
    
    bbs = bbw / bbw_sma.replace(0, np.nan)
    return bbs.fillna(0.0)


def calculate_rvol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Relative Volume (RVOL).
    RVOL = Volume / SMA(Volume, period)
    """
    volume = df["volume"].astype(float)
    sma_vol = volume.rolling(window=period).mean()
    rvol = volume / sma_vol.replace(0, np.nan)
    return rvol.fillna(0.0)


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD Line, Signal Line, and Histogram."""
    ema_fast = EMA.calculate(df, fast)
    ema_slow = EMA.calculate(df, slow)
    macd_line = ema_fast - ema_slow
    
    # Signal line is EMA of MACD line
    # Need to pass as dataframe column for EMA class
    temp_df = pd.DataFrame({"close": macd_line})
    signal_line = EMA.calculate(temp_df, signal)
    
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_mrs(df: pd.DataFrame, current_idx: int) -> dict:
    """
    Calculate Market Regime Score (MRS).
    Returns a dictionary with score, direction context, and sub-scores.
    Uses the latest completed data at current_idx.
    """
    if current_idx < 0:
        current_idx = len(df) + current_idx
        
    try:
        row = df.iloc[current_idx]
        prev_row = df.iloc[current_idx - 1] if current_idx > 0 else row
    except IndexError:
        return {"score": 0, "bullish_score": 0, "bearish_score": 0}

    # Extract required values
    close = float(row["close"])
    ema9 = float(row["ema9"])
    ema21 = float(row["ema21"])
    ema200 = float(row["ema200"])
    
    er = float(row["er10"])
    nes = float(row["nes"])
    nslope = float(row["nslope"])
    rvol = float(row["rvol20"])
    
    macd_hist = float(row["macd_hist"])
    macd_hist_prev = float(prev_row["macd_hist"])

    # 1. Structure (Max 25)
    # +10: directional EMA9/EMA21 alignment
    # +10: price aligned with EMA200
    # +5: EMA21 aligned with EMA200
    
    bullish_structure = 0
    bearish_structure = 0
    
    if ema9 > ema21: bullish_structure += 10
    if ema9 < ema21: bearish_structure += 10
        
    if close > ema200: bullish_structure += 10
    if close < ema200: bearish_structure += 10
        
    if ema21 > ema200: bullish_structure += 5
    if ema21 < ema200: bearish_structure += 5

    # 2. Efficiency (Max 30)
    # ER >= 0.60 -> +20; ER >= 0.40 -> +10
    efficiency = 0
    if er >= 0.60:
        efficiency = 20
    elif er >= 0.40:
        efficiency = 10
        
    # NES: abs >= 0.50 -> +10; abs >= 0.25 -> +5
    abs_nes = abs(nes)
    if abs_nes >= 0.50:
        efficiency += 10
    elif abs_nes >= 0.25:
        efficiency += 5

    # 3. Momentum / Slope (Max 25)
    # abs(NSlope) >= 0.12 -> +15; abs >= 0.06 -> +8
    momentum = 0
    abs_nslope = abs(nslope)
    if abs_nslope >= 0.12:
        momentum = 15
    elif abs_nslope >= 0.06:
        momentum = 8
        
    # MACD Histogram directionally meaningful progression
    bullish_macd = 0
    bearish_macd = 0
    if macd_hist > macd_hist_prev:
        bullish_macd = 10
    if macd_hist < macd_hist_prev:
        bearish_macd = 10

    # 4. Volume (Max 20)
    volume = 0
    if rvol >= 1.30:
        volume = 20
    elif rvol >= 0.90:
        volume = 10

    bullish_score = bullish_structure + efficiency + momentum + bullish_macd + volume
    bearish_score = bearish_structure + efficiency + momentum + bearish_macd + volume
    
    return {
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
        "structure": {"bullish": bullish_structure, "bearish": bearish_structure},
        "efficiency": efficiency,
        "momentum": momentum,
        "volume": volume,
        "macd": {"bullish": bullish_macd, "bearish": bearish_macd}
    }
