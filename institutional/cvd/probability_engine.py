import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from institutional.cvd.live_engine import LiveCVDEngine
from institutional.data.engine import InstitutionalDataEngine
from utils.logger import logger

class Phase7ProbabilityEngine:
    """
    Computes EXACT Phase 6.5 historical features (BASE + CVD) in real-time,
    evaluates them through the frozen Phase 7 LightGBM artifact,
    and returns the directional probability (P(up)).
    """
    def __init__(self, inst_data: InstitutionalDataEngine):
        self.inst_data = inst_data
        self.cvd_engines: Dict[str, LiveCVDEngine] = {}

    def _get_engine(self, symbol: str) -> LiveCVDEngine:
        if symbol not in self.cvd_engines:
            # LiveCVDEngine automatically attempts to load PHASE7_MODEL_FROZEN_{symbol}.pkl
            self.cvd_engines[symbol] = LiveCVDEngine(symbol)
        return self.cvd_engines[symbol]

    def _engineer_base_features(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """
        Replicates EXACTLY the logic from Phase5BaselineExperiment.engineer_features
        """
        if len(df) < 30:
            return None # Require at least 30 bars to safely compute 20-period rolling

        df = df.copy()
        c = df['close']
        
        # BASE-1: Returns
        df['ret_1'] = c.pct_change(1)
        df['ret_3'] = c.pct_change(3)
        df['ret_5'] = c.pct_change(5)
        
        # BASE-2: Volatility
        df['log_ret'] = np.log(c / c.shift(1))
        df['realized_vol_20'] = df['log_ret'].rolling(20).std(ddof=1) * np.sqrt(20)
        
        # BASE-3: ATR
        h_l = df['high'] - df['low']
        h_pc = (df['high'] - c.shift(1)).abs()
        l_pc = (df['low'] - c.shift(1)).abs()
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
        # Normalized ATR (percentage)
        df['atr_pct_14'] = df['atr_14'] / c
        
        # BASE-4: Momentum
        df['mom_10'] = df['log_ret'].rolling(10).sum()
        
        # BASE-5: Volume
        v = df['volume']
        df['vol_ma_20'] = v.rolling(20).mean()
        df['vol_ratio'] = v / (df['vol_ma_20'] + 1e-8)

        last_row = df.iloc[-1]
        
        # Strict NaN checking for the base features used
        base_features = {
            "ret_1": last_row['ret_1'],
            "ret_3": last_row['ret_3'],
            "ret_5": last_row['ret_5'],
            "realized_vol_20": last_row['realized_vol_20'],
            "atr_pct_14": last_row['atr_pct_14'],
            "mom_10": last_row['mom_10'],
            "vol_ratio": last_row['vol_ratio']
        }
        
        for k, v in base_features.items():
            if pd.isna(v) or np.isinf(v):
                return None
                
        return base_features

    def get_probability(self, symbol: str, now_ms: int) -> Optional[Dict[str, Any]]:
        try:
            cvd_engine = self._get_engine(symbol)
        except Exception as e:
            # Model routing fail closed (missing model, wrong LightGBM version, etc)
            logger.warning(f"[{symbol}] ProbabilityEngine model routing failed: {e}")
            return None

        # Feed latest trades from InstitutionalDataEngine to CVD Engine
        if symbol in self.inst_data._trades:
            with self.inst_data._lock:
                trades_list = list(self.inst_data._trades[symbol])
            for t in trades_list:
                cvd_engine.add_trade(t)
                
        # T_decision is exactly the 5m boundary
        T_decision = (now_ms // 300000) * 300000
        
        # Get base features (using 5m timeframe)
        snapshot = self.inst_data.get_snapshot(symbol, "5m")
        if not snapshot or not snapshot.ohlcv:
            return None
            
        data = []
        for bar in snapshot.ohlcv:
            data.append({
                'timestamp': pd.to_datetime(bar.timestamp, unit='ms'),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
            
        df = pd.DataFrame(data)
        
        base_features = self._engineer_base_features(df)
        if base_features is None:
            return None
            
        # Get final probability evaluation using the exactly ordered 18-feature contract
        result = cvd_engine.get_probability(base_features, T_decision)
        return result
