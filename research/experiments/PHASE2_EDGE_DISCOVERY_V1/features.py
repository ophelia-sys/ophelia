import pandas as pd
import numpy as np

def build_base_features(df_1m: pd.DataFrame) -> pd.DataFrame:
    df_1m = df_1m.copy()
    if 'timestamp_dt' not in df_1m.columns:
        df_1m['timestamp_dt'] = pd.to_datetime(df_1m['timestamp'], unit='ms')
    df_1m = df_1m.set_index('timestamp_dt')
    
    # Base resample
    df_5m = df_1m.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'delta_v': 'sum',
        'timestamp': 'last'
    }).dropna()
    
    # Baseline CVD Features
    df_5m['cvd_delta_5m'] = df_5m['delta_v']
    df_5m['cvd_delta_15m'] = df_5m['cvd_delta_5m'].rolling(3).sum()
    df_5m['cvd_delta_1h'] = df_5m['cvd_delta_5m'].rolling(12).sum()
    
    buy_5m = (df_5m['volume'] + df_5m['delta_v']) / 2.0
    sell_5m = (df_5m['volume'] - df_5m['delta_v']) / 2.0
    
    buy_15m = buy_5m.rolling(3).sum()
    sell_15m = sell_5m.rolling(3).sum()
    buy_1h = buy_5m.rolling(12).sum()
    sell_1h = sell_5m.rolling(12).sum()
    
    df_5m['cvd_imbalance_5m'] = df_5m['cvd_delta_5m'] / (buy_5m + sell_5m + 1e-8)
    df_5m['cvd_imbalance_15m'] = df_5m['cvd_delta_15m'] / (buy_15m + sell_15m + 1e-8)
    df_5m['cvd_imbalance_1h'] = df_5m['cvd_delta_1h'] / (buy_1h + sell_1h + 1e-8)
    
    std_5m_raw = df_5m['cvd_delta_5m'].rolling(288).std(ddof=1)
    std_15m_raw = df_5m['cvd_delta_15m'].rolling(288).std(ddof=1)
    std_1h_raw = df_5m['cvd_delta_1h'].rolling(288).std(ddof=1)
    
    mean_5m = df_5m['cvd_delta_5m'].rolling(288).mean()
    mean_15m = df_5m['cvd_delta_15m'].rolling(288).mean()
    mean_1h = df_5m['cvd_delta_1h'].rolling(288).mean()
    
    df_5m['std_5m_raw'] = std_5m_raw
    df_5m['std_15m_raw'] = std_15m_raw
    df_5m['std_1h_raw'] = std_1h_raw
    
    df_5m['cvd_zscore_5m'] = np.where(std_5m_raw == 0.0, 0, (df_5m['cvd_delta_5m'] - mean_5m) / (std_5m_raw + 1e-8))
    df_5m['cvd_zscore_15m'] = np.where(std_15m_raw == 0.0, 0, (df_5m['cvd_delta_15m'] - mean_15m) / (std_15m_raw + 1e-8))
    df_5m['cvd_zscore_1h'] = np.where(std_1h_raw == 0.0, 0, (df_5m['cvd_delta_1h'] - mean_1h) / (std_1h_raw + 1e-8))
    
    df_5m['cvd_acceleration_15m'] = df_5m['cvd_delta_15m'] - df_5m['cvd_delta_15m'].shift(3)
    df_5m['cvd_acceleration_1h'] = df_5m['cvd_delta_1h'] - df_5m['cvd_delta_1h'].shift(12)
    
    # Base Features
    df_5m['ret_1'] = df_5m['close'].pct_change(1)
    df_5m['ret_3'] = df_5m['close'].pct_change(3)
    df_5m['ret_5'] = df_5m['close'].pct_change(5)
    
    df_5m['realized_vol_20'] = df_5m['ret_1'].rolling(20).std(ddof=1)
    
    high_low = df_5m['high'] - df_5m['low']
    high_close = (df_5m['high'] - df_5m['close'].shift()).abs()
    low_close = (df_5m['low'] - df_5m['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_5m['atr_pct_14'] = tr.rolling(14).mean() / df_5m['close']
    
    df_5m['mom_10'] = df_5m['close'] / df_5m['close'].shift(10) - 1.0
    
    vol_20 = df_5m['volume'].rolling(20).mean()
    vol_60 = df_5m['volume'].rolling(60).mean()
    df_5m['vol_ratio'] = vol_20 / (vol_60 + 1e-8)
    
    return df_5m

def add_adv_orderflow_features(df_5m: pd.DataFrame) -> pd.DataFrame:
    # Exact implementations of DTR / FLP / DIV / ABS from institutional/cvd/live_engine.py
    df_5m['delta_slope_3'] = (df_5m['cvd_delta_5m'] - df_5m['cvd_delta_5m'].shift(2)) / 2.0
    
    # DTR: Delta Deterioration
    df_5m['delta_deterioration_bearish'] = np.where(
        (df_5m['cvd_delta_15m'] > 0) & (df_5m['delta_slope_3'] < -np.abs(df_5m['std_5m_raw'] * 0.1)),
        1.0, 0.0
    )
    df_5m['delta_deterioration_bullish'] = np.where(
        (df_5m['cvd_delta_15m'] < 0) & (df_5m['delta_slope_3'] > np.abs(df_5m['std_5m_raw'] * 0.1)),
        1.0, 0.0
    )
    
    # FLP: Delta Flip
    prev_15m = df_5m['cvd_delta_15m'].shift(3)
    df_5m['delta_flip_bullish'] = np.where(
        (prev_15m < 0) & (df_5m['cvd_delta_15m'] > 0) & (df_5m['cvd_zscore_15m'] > 0.5),
        1.0, 0.0
    )
    df_5m['delta_flip_bearish'] = np.where(
        (prev_15m > 0) & (df_5m['cvd_delta_15m'] < 0) & (df_5m['cvd_zscore_15m'] < -0.5),
        1.0, 0.0
    )
    
    # DIV: Divergence
    rolling_low_20 = df_5m['low'].rolling(20).min()
    rolling_high_20 = df_5m['high'].rolling(20).max()
    is_swing_low = df_5m['low'] == rolling_low_20
    is_swing_high = df_5m['high'] == rolling_high_20
    
    last_swing_low_price = df_5m['low'].where(is_swing_low).ffill().shift(1)
    last_swing_low_cvd = df_5m['cvd_delta_1h'].where(is_swing_low).ffill().shift(1)
    df_5m['divergence_bullish'] = np.where(
        is_swing_low & (df_5m['low'] < last_swing_low_price) & (df_5m['cvd_delta_1h'] > last_swing_low_cvd),
        1.0, 0.0
    )
    
    last_swing_high_price = df_5m['high'].where(is_swing_high).ffill().shift(1)
    last_swing_high_cvd = df_5m['cvd_delta_1h'].where(is_swing_high).ffill().shift(1)
    df_5m['divergence_bearish'] = np.where(
        is_swing_high & (df_5m['high'] > last_swing_high_price) & (df_5m['cvd_delta_1h'] < last_swing_high_cvd),
        1.0, 0.0
    )
    
    # ABS: Absorption
    df_5m['absorption_bullish_proxy'] = np.where(
        (df_5m['cvd_zscore_5m'] < -1.5) & (df_5m['ret_1'] >= 0.0),
        1.0, 0.0
    )
    df_5m['absorption_bearish_proxy'] = np.where(
        (df_5m['cvd_zscore_5m'] > 1.5) & (df_5m['ret_1'] <= 0.0),
        1.0, 0.0
    )
    
    # Additional OF ideas
    df_5m['delta_persistence'] = (np.sign(df_5m['cvd_delta_5m']) == np.sign(df_5m['cvd_delta_5m'].shift(1))).astype(float)
    df_5m['aggressive_volume_conc'] = np.where(df_5m['volume'] > 0, np.abs(df_5m['delta_v']) / df_5m['volume'], 0)
    
    return df_5m

def add_regime_features(df_5m: pd.DataFrame) -> pd.DataFrame:
    # Regime & Trend Features
    df_5m['ret_15'] = df_5m['close'].pct_change(15)
    df_5m['ret_60'] = df_5m['close'].pct_change(60)
    
    ema_60 = df_5m['close'].ewm(span=60, adjust=False).mean()
    df_5m['ema_60_dist'] = (df_5m['close'] - ema_60) / (ema_60 + 1e-8)
    
    diff = abs(df_5m['close'] - df_5m['close'].shift(60))
    vol = df_5m['close'].diff().abs().rolling(60).sum()
    df_5m['normalized_trend_str'] = diff / (vol + 1e-8)
    
    df_5m['breakout_state_12'] = (df_5m['close'] > df_5m['high'].rolling(12).max().shift(1)).astype(float) - (df_5m['close'] < df_5m['low'].rolling(12).min().shift(1)).astype(float)
    return df_5m

def add_volatility_features(df_5m: pd.DataFrame) -> pd.DataFrame:
    # Volatility Features
    df_5m['vol_pct_60'] = df_5m['realized_vol_20'].rolling(60).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if not pd.isna(x).all() else 0.5, raw=False)
    
    high_low = df_5m['high'] - df_5m['low']
    df_5m['range_efficiency'] = (df_5m['close'] - df_5m['open']).abs() / (high_low + 1e-8)
    df_5m['body_wick_ratio'] = (df_5m['close'] - df_5m['open']).abs() / ((high_low - (df_5m['close'] - df_5m['open']).abs()) + 1e-8)
    
    return df_5m

def add_targets(df_5m: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
    df_5m['R_12'] = np.log(df_5m['close'].shift(-horizon) / df_5m['close'])
    df_5m['target_long'] = (df_5m['R_12'] > 10.0 / 10000.0).astype(int)
    df_5m['target_short'] = (df_5m['R_12'] < -10.0 / 10000.0).astype(int)
    
    df_5m.loc[df_5m.index[-horizon:], ['target_long', 'target_short', 'R_12']] = np.nan
    return df_5m

BASELINE_FEATURES = [
    "ret_1", "ret_3", "ret_5", "realized_vol_20", "atr_pct_14", "mom_10", "vol_ratio",
    "cvd_delta_5m", "cvd_delta_15m", "cvd_delta_1h",
    "cvd_imbalance_5m", "cvd_imbalance_15m", "cvd_imbalance_1h",
    "cvd_zscore_5m", "cvd_zscore_15m", "cvd_zscore_1h",
    "cvd_acceleration_15m", "cvd_acceleration_1h"
]

ADV_OF_FEATURES = [
    "delta_deterioration_bullish", "delta_deterioration_bearish",
    "delta_flip_bullish", "delta_flip_bearish",
    "divergence_bullish", "divergence_bearish",
    "absorption_bullish_proxy", "absorption_bearish_proxy",
    "delta_persistence", "aggressive_volume_conc"
]

REGIME_FEATURES = [
    "ret_15", "ret_60", "ema_60_dist", "normalized_trend_str", "breakout_state_12"
]

VOL_FEATURES = [
    "vol_pct_60", "range_efficiency", "body_wick_ratio"
]
