import numpy as np
import pandas as pd
from typing import List, Dict

class FeatureGenerator:
    """
    Generates isolated mathematical feature families.
    Strictly prohibits look-ahead leakage.
    """
    
    @staticmethod
    def generate_features(df: pd.DataFrame, families: List[str] = None) -> pd.DataFrame:
        if families is None:
            families = ['baseline']
            
        df = df.copy()
        
        # 1. Price / Returns (Baseline)
        if 'baseline' in families or 'returns' in families:
            df['ret_1'] = df['close'].pct_change()
            df['ret_5'] = df['close'].pct_change(5)
            df['ret_15'] = df['close'].pct_change(15)
            
        # 2. Volatility
        if 'volatility' in families:
            df['vol_60'] = df['close'].pct_change().rolling(60).std()
            df['atr'] = (df['high'] - df['low']).rolling(14).mean()
            df['hist_atr'] = df['atr'].rolling(500).median()
            df['is_high_vol'] = (df['atr'] > df['hist_atr']).astype(float)
            
        # 3. Trend
        if 'trend' in families:
            diff = abs(df['close'] - df['close'].shift(60))
            vol = df['close'].diff().abs().rolling(60).sum()
            df['ker_60'] = diff / (vol + 1e-8)
            df['is_trend'] = (df['ker_60'] > df['ker_60'].rolling(500).median()).astype(float)
            
        # 4. Momentum
        if 'momentum' in families:
            df['mom_15'] = df['close'] - df['close'].shift(15)
            df['mom_60'] = df['close'] - df['close'].shift(60)
            
        # 5. Volume
        if 'volume' in families:
            df['vol_z'] = (df['volume'] - df['volume'].rolling(60).mean()) / (df['volume'].rolling(60).std() + 1e-8)
            df['delta_v_z'] = (df['delta_v'] - df['delta_v'].rolling(60).mean()) / (df['delta_v'].rolling(60).std() + 1e-8)
            
        # 6. Microstructure (Phase 5.3)
        if 'microstructure' in families:
            # We strictly use proxies since canonical OFI is unverified/unavailable.
            df['taker_buy_ratio'] = df['taker_buy_volume'] / (df['volume'] + 1e-8)
            
            # Using delta_v directly as a volume order flow imbalance proxy
            df['ofi_proxy_z'] = (df['delta_v'] - df['delta_v'].rolling(60).mean()) / (df['delta_v'].rolling(60).std() + 1e-8)
            
            if 'delta_oi' in df.columns:
                df['delta_oi_z'] = (df['delta_oi'] - df['delta_oi'].rolling(60).mean()) / (df['delta_oi'].rolling(60).std() + 1e-8)
            
        return df

    @staticmethod
    def get_feature_columns(families: List[str]) -> List[str]:
        cols = []
        if 'baseline' in families or 'returns' in families:
            cols.extend(['ret_1', 'ret_5', 'ret_15'])
        if 'volatility' in families:
            cols.extend(['vol_60', 'atr', 'hist_atr', 'is_high_vol'])
        if 'trend' in families:
            cols.extend(['ker_60', 'is_trend'])
        if 'momentum' in families:
            cols.extend(['mom_15', 'mom_60'])
        if 'volume' in families:
            cols.extend(['vol_z', 'delta_v_z'])
        if 'microstructure' in families:
            cols.extend(['taker_buy_ratio', 'ofi_proxy_z', 'delta_oi_z'])
        return cols
