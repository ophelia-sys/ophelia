import os
import json
import tempfile
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import warnings
from institutional.data.models import TradeEvent
from institutional.types import DataQuality

@dataclass
class CVDFeatureVector:
    """Strictly typed contract representing the 11 frozen model features."""
    cvd_delta_5m: float
    cvd_delta_15m: float
    cvd_delta_1h: float
    cvd_imbalance_5m: float
    cvd_imbalance_15m: float
    cvd_imbalance_1h: float
    cvd_zscore_5m: float
    cvd_zscore_15m: float
    cvd_zscore_1h: float
    cvd_acceleration_15m: float
    cvd_acceleration_1h: float
    
    calculated_at: int
    source_latest_trade_time: int
    feature_age_ms: int
    
    # Telemetry
    delta_deterioration_bearish: float = 0.0
    delta_deterioration_bullish: float = 0.0
    delta_flip_bearish: float = 0.0
    delta_flip_bullish: float = 0.0
    divergence_bearish: float = 0.0
    divergence_bullish: float = 0.0
    absorption_bearish_proxy: float = 0.0
    absorption_bullish_proxy: float = 0.0
    
    data_quality: DataQuality = DataQuality.VALID
    
    def to_array(self) -> np.ndarray:
        return np.array([
            self.cvd_delta_5m, self.cvd_delta_15m, self.cvd_delta_1h,
            self.cvd_imbalance_5m, self.cvd_imbalance_15m, self.cvd_imbalance_1h,
            self.cvd_zscore_5m, self.cvd_zscore_15m, self.cvd_zscore_1h,
            self.cvd_acceleration_15m, self.cvd_acceleration_1h
        ], dtype=float)

class LiveCVDEngine:
    REQUIRED_FEATURES = [
        "ret_1", "ret_3", "ret_5", "realized_vol_20", "atr_pct_14", "mom_10", "vol_ratio",
        "cvd_delta_5m", "cvd_delta_15m", "cvd_delta_1h",
        "cvd_imbalance_5m", "cvd_imbalance_15m", "cvd_imbalance_1h",
        "cvd_zscore_5m", "cvd_zscore_15m", "cvd_zscore_1h",
        "cvd_acceleration_15m", "cvd_acceleration_1h"
    ]

    def __init__(self, symbol: str, model_path_long: Optional[str] = None, model_path_short: Optional[str] = None):
        self.symbol = symbol
        # Default to new Phase 7 root model path format if none provided
        self.model_path_long = model_path_long if model_path_long else f"PHASE7_MODEL_FROZEN_{symbol.replace('-', '')}.pkl"
        self.model_path_short = model_path_short if model_path_short else f"PHASE7_SHORT_MODEL_FROZEN_{symbol.replace('-', '')}.pkl"
        
        self.clf_long = None
        self.clf_short = None
        self.model_info_long = {}
        self.model_info_short = {}
        try:
            self._load_models()
        except Exception as e:
            # We log but do NOT crash the engine init. Inference will just fail closed.
            import logging
            logging.getLogger(__name__).error(f"Failed to load models for {symbol}: {e}")
        
        self.trades = [] # temporary holding for current interval trades
        self.seen_trade_ids = set()
        
        # Historical blocks (5m intervals)
        self.history_blocks = [] # List of dicts
        self.max_history_len = 300 # Need 288 for 1d z-score + 12 for 1h acceleration
        self.latest_trade_time = 0
        
        self.state_file = os.path.join(os.path.dirname(__file__), f"../../data/cvd_state_{self.symbol}.json")
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._load_state()

    def _load_state(self):
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            
            blocks = data.get("history_blocks", [])
            self.latest_trade_time = data.get("latest_trade_time", 0)
            
            if not isinstance(blocks, list):
                return
                
            valid_blocks = []
            for b in blocks:
                if isinstance(b, dict) and "minute" in b:
                    valid_blocks.append(b)
            
            valid_blocks.sort(key=lambda x: x['minute'])
            self.history_blocks = valid_blocks[-self.max_history_len:]
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to load CVD state for {self.symbol}: {e}")

    def _save_state(self):
        try:
            data = {
                "latest_trade_time": self.latest_trade_time,
                "history_blocks": self.history_blocks
            }
            tmp_path = self.state_file + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, self.state_file)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to save CVD state for {self.symbol}: {e}")

        
    def _load_models(self):
        if not os.path.exists(self.model_path_long):
            raise FileNotFoundError(f"Missing Phase 7 Long artifact: {self.model_path_long}")
        if not os.path.exists(self.model_path_short):
            raise FileNotFoundError(f"Missing Phase 7 Short artifact: {self.model_path_short}")
            
        with open(self.model_path_long, "rb") as f:
            artifact_long = pickle.load(f)
        with open(self.model_path_short, "rb") as f:
            artifact_short = pickle.load(f)
            
        if "model_object" not in artifact_long or "model_object" not in artifact_short:
            raise ValueError("An artifact is malformed or not Phase 7 format.")
            
        active_lgb_ver = lgb.__version__
        
        self.model_info_long = artifact_long
        self.clf_long = artifact_long["model_object"]
        
        self.model_info_short = artifact_short
        self.clf_short = artifact_short["model_object"]
        
        if artifact_long["feature_contract"]["features"] != self.REQUIRED_FEATURES:
            raise ValueError("Long artifact feature contract does not perfectly match REQUIRED_FEATURES.")
        if artifact_short["feature_contract"]["features"] != self.REQUIRED_FEATURES:
            raise ValueError("Short artifact feature contract does not perfectly match REQUIRED_FEATURES.")
        
    def add_trade(self, event: TradeEvent):
        if event.symbol != self.symbol: return
        if event.trade_id in self.seen_trade_ids: return
        
        self.seen_trade_ids.add(event.trade_id)
        self.trades.append(event)
        self.latest_trade_time = max(self.latest_trade_time, event.timestamp)
        
    def get_features(self, T_decision: int) -> Optional[CVDFeatureVector]:
        # T_decision is expected to be exactly on a 5m boundary
        
        # 1. Separate trades into past blocks up to T_decision
        self.trades.sort(key=lambda x: x.timestamp)
        
        # trades < T_decision
        past_trades = [t for t in self.trades if t.timestamp < T_decision]
        
        # we only keep trades >= T_decision in self.trades for future
        self.trades = [t for t in self.trades if t.timestamp >= T_decision]
        
        # Prune seen_trade_ids to prevent memory leaks (keep only what's still in self.trades)
        self.seen_trade_ids = {t.trade_id for t in self.trades}
        
        # 2. Aggregate past_trades into 5m blocks
        # T_decision is usually OHLCV.open_time + 5m
        # The block ending at T_decision is [T_decision - 5m, T_decision)
        if len(past_trades) > 0:
            for t in past_trades:
                block_start = (t.timestamp // 300000) * 300000
                
                # Check if we already have this block
                if not self.history_blocks or self.history_blocks[-1]['minute'] != block_start:
                    self.history_blocks.append({
                        'minute': block_start,
                        'buy_volume': 0.0,
                        'sell_volume': 0.0,
                        'delta_volume': 0.0,
                        'open': t.price,
                        'high': t.price,
                        'low': t.price,
                        'close': t.price
                    })
                    
                b = self.history_blocks[-1]
                vol = t.price * t.quantity
                
                b['high'] = max(b['high'], t.price)
                b['low'] = min(b['low'], t.price)
                b['close'] = t.price
                
                if t.aggressor == "BUY":
                    b['buy_volume'] += vol
                    b['delta_volume'] += vol
                elif t.aggressor == "SELL":
                    b['sell_volume'] += vol
                    b['delta_volume'] -= vol
                    
        # Sort and truncate history
        self.history_blocks.sort(key=lambda x: x['minute'])
        
        # We need a continuous sequence of 5m blocks ending at T_decision - 300000.
        # Fill missing blocks with 0 volume.
        if len(self.history_blocks) > 0:
            filled_blocks = []
            curr = self.history_blocks[0]['minute']
            end_minute = T_decision - 300000
            
            idx = 0
            while curr <= end_minute:
                if idx < len(self.history_blocks) and self.history_blocks[idx]['minute'] == curr:
                    filled_blocks.append(self.history_blocks[idx])
                    idx += 1
                    curr += 300000
                else:
                    # If the gap to the next block (or end_minute) is massive, skip padding
                    # to prevent flushing out the valid historical 288 blocks.
                    next_minute = self.history_blocks[idx]['minute'] if idx < len(self.history_blocks) else end_minute + 300000
                    if (next_minute - curr) > 3600000:  # > 1 hour gap
                        import logging
                        logging.getLogger(__name__).warning(f"[GAP DETECTED] Skipping {int((next_minute - curr)/300000)} empty blocks to preserve CVD history.")
                        curr = next_minute
                        continue
                        
                    prev_close = filled_blocks[-1]['close'] if filled_blocks else 0.0
                    filled_blocks.append({
                        'minute': curr,
                        'buy_volume': 0.0,
                        'sell_volume': 0.0,
                        'delta_volume': 0.0,
                        'open': prev_close,
                        'high': prev_close,
                        'low': prev_close,
                        'close': prev_close
                    })
                    curr += 300000
            self.history_blocks = filled_blocks[-self.max_history_len:]
        
        self._save_state()
        
        if len(self.history_blocks) < 288:
            return None # Not enough history to calculate 288-period rolling features
            
        # 3. Calculate features using Pandas to perfectly match the historical pipeline logic
        df = pd.DataFrame(self.history_blocks)
        
        df['cvd_delta_5m'] = df['delta_volume']
        df['cvd_delta_15m'] = df['cvd_delta_5m'].rolling(3).sum()
        df['cvd_delta_1h'] = df['cvd_delta_5m'].rolling(12).sum()
        
        buy_5m = df['buy_volume']
        sell_5m = df['sell_volume']
        buy_15m = buy_5m.rolling(3).sum()
        sell_15m = sell_5m.rolling(3).sum()
        buy_1h = buy_5m.rolling(12).sum()
        sell_1h = sell_5m.rolling(12).sum()
        
        df['cvd_imbalance_5m'] = df['cvd_delta_5m'] / (buy_5m + sell_5m + 1e-8)
        df['cvd_imbalance_15m'] = df['cvd_delta_15m'] / (buy_15m + sell_15m + 1e-8)
        df['cvd_imbalance_1h'] = df['cvd_delta_1h'] / (buy_1h + sell_1h + 1e-8)
        
        df['std_5m_raw'] = df['cvd_delta_5m'].rolling(288).std(ddof=1)
        df['std_15m_raw'] = df['cvd_delta_15m'].rolling(288).std(ddof=1)
        df['std_1h_raw'] = df['cvd_delta_1h'].rolling(288).std(ddof=1)
        
        mean_5m = df['cvd_delta_5m'].rolling(288).mean()
        mean_15m = df['cvd_delta_15m'].rolling(288).mean()
        mean_1h = df['cvd_delta_1h'].rolling(288).mean()
        
        df['cvd_zscore_5m'] = (df['cvd_delta_5m'] - mean_5m) / df['std_5m_raw']
        df['cvd_zscore_15m'] = (df['cvd_delta_15m'] - mean_15m) / df['std_15m_raw']
        df['cvd_zscore_1h'] = (df['cvd_delta_1h'] - mean_1h) / df['std_1h_raw']
        
        df['cvd_zscore_5m'] = np.where(df['std_5m_raw'] == 0.0, np.nan, df['cvd_zscore_5m'])
        df['cvd_zscore_15m'] = np.where(df['std_15m_raw'] == 0.0, np.nan, df['cvd_zscore_15m'])
        df['cvd_zscore_1h'] = np.where(df['std_1h_raw'] == 0.0, np.nan, df['cvd_zscore_1h'])
        
        df['cvd_acceleration_15m'] = df['cvd_delta_15m'] - df['cvd_delta_15m'].shift(3)
        df['cvd_acceleration_1h'] = df['cvd_delta_1h'] - df['cvd_delta_1h'].shift(12)
        
        # Telemetry: Advanced Orderflow features
        df['delta_slope_3'] = (df['cvd_delta_5m'] - df['cvd_delta_5m'].shift(2)) / 2.0
        df['delta_deterioration_bearish'] = np.where(
            (df['cvd_delta_15m'] > 0) & (df['delta_slope_3'] < -np.abs(df['std_5m_raw'] * 0.1)),
            1.0, 0.0
        )
        df['delta_deterioration_bullish'] = np.where(
            (df['cvd_delta_15m'] < 0) & (df['delta_slope_3'] > np.abs(df['std_5m_raw'] * 0.1)),
            1.0, 0.0
        )
        
        prev_15m = df['cvd_delta_15m'].shift(3)
        df['delta_flip_bullish'] = np.where(
            (prev_15m < 0) & (df['cvd_delta_15m'] > 0) & (df['cvd_zscore_15m'] > 0.5),
            1.0, 0.0
        )
        df['delta_flip_bearish'] = np.where(
            (prev_15m > 0) & (df['cvd_delta_15m'] < 0) & (df['cvd_zscore_15m'] < -0.5),
            1.0, 0.0
        )
        
        rolling_low_20 = df['low'].rolling(20).min()
        rolling_high_20 = df['high'].rolling(20).max()
        is_swing_low = df['low'] == rolling_low_20
        is_swing_high = df['high'] == rolling_high_20
        
        last_swing_low_price = df['low'].where(is_swing_low).ffill().shift(1)
        last_swing_low_cvd = df['cvd_delta_1h'].where(is_swing_low).ffill().shift(1)
        df['divergence_bullish'] = np.where(
            is_swing_low & (df['low'] < last_swing_low_price) & (df['cvd_delta_1h'] > last_swing_low_cvd),
            1.0, 0.0
        )
        
        last_swing_high_price = df['high'].where(is_swing_high).ffill().shift(1)
        last_swing_high_cvd = df['cvd_delta_1h'].where(is_swing_high).ffill().shift(1)
        df['divergence_bearish'] = np.where(
            is_swing_high & (df['high'] > last_swing_high_price) & (df['cvd_delta_1h'] < last_swing_high_cvd),
            1.0, 0.0
        )
        
        ret_1 = df['close'].pct_change(1)
        df['absorption_bullish_proxy'] = np.where(
            (df['cvd_zscore_5m'] < -1.5) & (ret_1 >= 0.0),
            1.0, 0.0
        )
        df['absorption_bearish_proxy'] = np.where(
            (df['cvd_zscore_5m'] > 1.5) & (ret_1 <= 0.0),
            1.0, 0.0
        )
        
        last_row = df.iloc[-1]
        
        calculated_at = int(datetime.utcnow().timestamp() * 1000)
        age = calculated_at - self.latest_trade_time
            
        return CVDFeatureVector(
            cvd_delta_5m=float(last_row['cvd_delta_5m']),
            cvd_delta_15m=float(last_row['cvd_delta_15m']),
            cvd_delta_1h=float(last_row['cvd_delta_1h']),
            cvd_imbalance_5m=float(last_row['cvd_imbalance_5m']),
            cvd_imbalance_15m=float(last_row['cvd_imbalance_15m']),
            cvd_imbalance_1h=float(last_row['cvd_imbalance_1h']),
            cvd_zscore_5m=float(last_row['cvd_zscore_5m']),
            cvd_zscore_15m=float(last_row['cvd_zscore_15m']),
            cvd_zscore_1h=float(last_row['cvd_zscore_1h']),
            cvd_acceleration_15m=float(last_row['cvd_acceleration_15m']),
            cvd_acceleration_1h=float(last_row['cvd_acceleration_1h']),
            delta_deterioration_bearish=float(last_row['delta_deterioration_bearish']),
            delta_deterioration_bullish=float(last_row['delta_deterioration_bullish']),
            delta_flip_bearish=float(last_row['delta_flip_bearish']),
            delta_flip_bullish=float(last_row['delta_flip_bullish']),
            divergence_bearish=float(last_row['divergence_bearish']),
            divergence_bullish=float(last_row['divergence_bullish']),
            absorption_bearish_proxy=float(last_row['absorption_bearish_proxy']),
            absorption_bullish_proxy=float(last_row['absorption_bullish_proxy']),
            calculated_at=calculated_at,
            source_latest_trade_time=self.latest_trade_time,
            feature_age_ms=age,
            data_quality=DataQuality.VALID
        )
        
    def get_probability(self, base_features_dict: Dict[str, float], T_decision: int) -> Optional[Dict[str, Any]]:
        if self.clf_long is None or self.clf_short is None:
            return None # Fail closed if models didn't load properly

        cvd_fv = self.get_features(T_decision)
        if cvd_fv is None:
            return {"status": "warming", "blocks": len(self.history_blocks), "required": 288}
            
        # Combine
        combined = {}
        combined.update(base_features_dict)
        combined.update({
            'cvd_delta_5m': cvd_fv.cvd_delta_5m,
            'cvd_delta_15m': cvd_fv.cvd_delta_15m,
            'cvd_delta_1h': cvd_fv.cvd_delta_1h,
            'cvd_imbalance_5m': cvd_fv.cvd_imbalance_5m,
            'cvd_imbalance_15m': cvd_fv.cvd_imbalance_15m,
            'cvd_imbalance_1h': cvd_fv.cvd_imbalance_1h,
            'cvd_zscore_5m': cvd_fv.cvd_zscore_5m,
            'cvd_zscore_15m': cvd_fv.cvd_zscore_15m,
            'cvd_zscore_1h': cvd_fv.cvd_zscore_1h,
            'cvd_acceleration_15m': cvd_fv.cvd_acceleration_15m,
            'cvd_acceleration_1h': cvd_fv.cvd_acceleration_1h
        })
        
        # Strict checking - EXACT 18 features in EXACT order
        X_list = []
        for f in self.REQUIRED_FEATURES:
            val = combined.get(f)
            if val is None or np.isnan(val) or np.isinf(val):
                return None
            X_list.append(val)
                
        X_vec = np.array([X_list], dtype=float)
        
        # Inference (No Scaler)
        try:
            prob_long = self.clf_long.predict_proba(X_vec)[0, 1]
            prob_short = self.clf_short.predict_proba(X_vec)[0, 1]
        except Exception:
            return None
            
        if not (0.0 <= prob_long <= 1.0) or not (0.0 <= prob_short <= 1.0):
            return None

        result = {
            "probability_long": float(prob_long),
            "probability_short": float(prob_short),
            "timestamp": T_decision,
            "feature_age_ms": cvd_fv.feature_age_ms,
            "telemetry": {
                "delta_deterioration_bearish": cvd_fv.delta_deterioration_bearish,
                "delta_deterioration_bullish": cvd_fv.delta_deterioration_bullish,
                "delta_flip_bearish": cvd_fv.delta_flip_bearish,
                "delta_flip_bullish": cvd_fv.delta_flip_bullish,
                "divergence_bearish": cvd_fv.divergence_bearish,
                "divergence_bullish": cvd_fv.divergence_bullish,
                "absorption_bearish_proxy": cvd_fv.absorption_bearish_proxy,
                "absorption_bullish_proxy": cvd_fv.absorption_bullish_proxy
            },
            "model_version": self.model_info_long.get("model_version", "1.0"),
            "feature_registry_version": "PHASE7_RECONSTRUCTION"
        }
        return result
