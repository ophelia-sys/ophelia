import os
import json
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

from institutional.cvd.live_engine import LiveCVDEngine
from core.trade_geometry import TradeGeometryEngine, TradeGeometry
from institutional.data.engine import InstitutionalDataEngine
from research.experiments.exp_phase5_1_baseline import Phase5BaselineExperiment
from institutional.types import Direction
from utils.logger import logger

@dataclass
class PaperSignal:
    decision_timestamp: int
    symbol: str
    predicted_probability: float
    model_class: str
    model_version: str
    feature_registry_version: str
    data_quality: str
    source_latest_trade_timestamp: int
    feature_age_ms: int
    cvd_features: Dict[str, float]
    geometry_status: str
    trade_geometry: Optional[TradeGeometry] = None

class PaperSignalEngine:
    """
    OBSERVATION ONLY: Evaluates Phase 5.3 CVD logic live.
    Must NOT contain any execution paths (place_order, position mutation).
    """
    def __init__(self, inst_data: InstitutionalDataEngine, telegram_adapter=None, model_path="PHASE5_3_MODEL_G_FROZEN.pkl"):
        self.inst_data = inst_data
        self.telegram = telegram_adapter
        self.model_path = model_path
        self.cvd_engines: Dict[str, LiveCVDEngine] = {}
        self.geometry_engine = TradeGeometryEngine()
        self.baseline_exp = Phase5BaselineExperiment()
        self.evaluated_decisions = set()
        
        self.log_file = "logs/paper_signals.jsonl"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def _get_engine(self, symbol: str) -> LiveCVDEngine:
        if symbol not in self.cvd_engines:
            self.cvd_engines[symbol] = LiveCVDEngine(symbol, self.model_path)
        return self.cvd_engines[symbol]

    def _log_suppression(self, symbol: str, timestamp: int, reason: str):
        record = {
            "timestamp": timestamp,
            "symbol": symbol,
            "suppressed": True,
            "reason": reason
        }
        self._write_log(record)
        logger.warning(f"[PaperSignal] Suppressed {symbol} at {timestamp}: {reason}")

    def _write_log(self, record: dict):
        with open(self.log_file, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def evaluate(self, symbol: str, now_ms: int):
        cvd_engine = self._get_engine(symbol)
        
        # Feed latest trades from InstitutionalDataEngine
        if symbol in self.inst_data._trades:
            with self.inst_data._lock:
                trades_list = list(self.inst_data._trades[symbol])
            for t in trades_list:
                cvd_engine.add_trade(t)
                
        # T_decision is exactly the 5m boundary
        T_decision = (now_ms // 300000) * 300000
        
        if (symbol, T_decision) in self.evaluated_decisions:
            return
            
        # Get base features
        # Using 5m timeframe
        snapshot = self.inst_data.get_snapshot(symbol, "5m")
        if not snapshot or not snapshot.ohlcv:
            self._log_suppression(symbol, T_decision, "INSUFFICIENT_HISTORY")
            self.evaluated_decisions.add((symbol, T_decision))
            return
            
        # Convert to DataFrame
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
        df_ohlcv = pd.DataFrame(data)
        if df_ohlcv.empty:
            self._log_suppression(symbol, T_decision, "INSUFFICIENT_HISTORY")
            self.evaluated_decisions.add((symbol, T_decision))
            return
            
        # Expected bar open_time is T_decision - 5 minutes
        expected_open_time = pd.to_datetime(T_decision - 300000, unit='ms')
        
        # Engineer base features
        try:
            df_feat = self.baseline_exp.engineer_features(df_ohlcv)
        except Exception as e:
            self._log_suppression(symbol, T_decision, f"FEATURE_ERROR: {e}")
            self.evaluated_decisions.add((symbol, T_decision))
            return
            
        row = df_feat[df_feat['timestamp'] == expected_open_time]
        if row.empty:
            self._log_suppression(symbol, T_decision, "STALE_DATA")
            self.evaluated_decisions.add((symbol, T_decision))
            return
            
        base_features_dict = row.iloc[0].to_dict()
        
        # Get CVD Probability
        prob_res = cvd_engine.get_probability(base_features_dict, T_decision)
        if prob_res is None:
            self._log_suppression(symbol, T_decision, "MISSING_FEATURE_OR_NAN")
            self.evaluated_decisions.add((symbol, T_decision))
            return
            
        # Map to class
        prob = prob_res['probability']
        if prob > 0.5:
            model_class = "BULLISH"
            direction = Direction.BULLISH
        elif prob < 0.5:
            model_class = "BEARISH"
            direction = Direction.BEARISH
        else:
            model_class = "NEUTRAL"
            direction = None
            
        # Trade Geometry
        trade_geometry = None
        geometry_status = "NOT_AVAILABLE"
        
        if direction is not None:
            atr = base_features_dict.get('atr_14', 0.0)
            current_price = base_features_dict.get('close', 0.0)
            if atr > 0 and current_price > 0:
                trade_geometry = self.geometry_engine.calculate_geometry(
                    current_price=current_price,
                    atr=atr,
                    direction=direction,
                    spread=current_price * 0.0005 # Mock spread
                )
                if trade_geometry:
                    geometry_status = "AVAILABLE"
                    
        signal = PaperSignal(
            decision_timestamp=T_decision,
            symbol=symbol,
            predicted_probability=prob,
            model_class=model_class,
            model_version=prob_res['model_version'],
            feature_registry_version=prob_res['feature_registry_version'],
            data_quality=prob_res['data_quality'],
            source_latest_trade_timestamp=cvd_engine.latest_trade_time,
            feature_age_ms=T_decision - cvd_engine.latest_trade_time,
            cvd_features=prob_res['cvd_feature_values'],
            geometry_status=geometry_status,
            trade_geometry=trade_geometry
        )
        
        self.evaluated_decisions.add((symbol, T_decision))
        
        # Log it
        record = asdict(signal)
        record['suppressed'] = False
        self._write_log(record)
        
        # Telegram Notification
        if self.telegram:
            msg = (
                f"📊 *OPHELIA PAPER SIGNAL*\n\n"
                f"⚠️ *This is PAPER / OBSERVATION ONLY*\n\n"
                f"Symbol: `{symbol}`\n"
                f"Timestamp: `{T_decision}`\n"
                f"Predicted probability: `{prob:.4f}`\n"
                f"Model class: `{model_class}`\n"
                f"Data quality: `{signal.data_quality}`\n"
                f"Model version: `{signal.model_version}`\n"
                f"Geometry status: `{geometry_status}`\n\n"
                f"CVD Flow Summary:\n"
                f"• Δ5m: `{signal.cvd_features.get('cvd_delta_5m', 0.0):.2f}`\n"
                f"• Δ15m: `{signal.cvd_features.get('cvd_delta_15m', 0.0):.2f}`\n"
                f"• Δ1h: `{signal.cvd_features.get('cvd_delta_1h', 0.0):.2f}`\n"
            )
            self.telegram.notify(msg)
