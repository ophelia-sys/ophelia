import time
import numpy as np
import pandas as pd
from typing import Optional, Dict

from institutional.types import (
    MarketState, Direction, DataQuality, FeatureStatus, Provenance, FeatureResult
)
from institutional.data.models import MarketDataSnapshot
from institutional.volatility import (
    calculate_realized_volatility, calculate_parkinson_volatility, calculate_garman_klass_volatility, calculate_atr
)
from institutional.trend import (
    calculate_efficiency_ratio, calculate_directional_persistence, calculate_atr_scaled_trend, get_ema_structure
)
from institutional.momentum import (
    calculate_standardized_momentum, calculate_momentum_acceleration, calculate_volume_imbalance
)
from institutional.normalization import calculate_rolling_percentile, calculate_robust_z_score
from institutional.regime import classify_regime_hmm
from institutional.structural_break import detect_structural_break
from institutional.score import calculate_evidence_entropy, calculate_advisory_volatility_score, calculate_composite_directional_probability
from institutional.liquidity import (
    calculate_relative_spread, calculate_amihud_illiquidity, calculate_depth_imbalance, estimate_kyle_lambda
)
from institutional.order_flow import calculate_ofi, calculate_cvd, calculate_taker_volume_imbalance
from institutional.vwap import calculate_vwap
from institutional.open_interest import analyze_open_interest_state
from institutional.funding import analyze_funding_state
from institutional.liquidation import analyze_liquidation_state
from institutional.anomaly import detect_anomaly

class InstitutionalMathEngine:
    """
    Research-Grade Institutional Math Engine (v3)
    
    Produces mathematically defensible states of market structure, completely
    decoupled from trading execution or risk management. Features FAST PATH and SLOW PATH.
    """
    
    def __init__(self, normalization_window: int = 500):
        self.normalization_window = normalization_window

    def analyze(self, snapshot: 'MarketDataSnapshot') -> MarketState:
        """
        Calculates the complete market state for a given symbol and timeframe.
        """
        if not snapshot.ohlcv or len(snapshot.ohlcv) < self.normalization_window:
            return MarketState(
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                timeframe=snapshot.timeframe,
                data_quality=DataQuality.INSUFFICIENT_DATA
            )
            
        # Convert List[OHLCVBar] to pandas DataFrame for math functions
        df = pd.DataFrame([
            {
                "time": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume
            } for bar in snapshot.ohlcv
        ])
            
        # =====================================================================
        # FAST PATH (Synchronous, Low-Latency)
        # =====================================================================
        
        # 1. Volatility Math (Robust Realized Volatility)
        rv = calculate_realized_volatility(df, window=20)
        rv_current = float(rv.iloc[-1]) if not pd.isna(rv.iloc[-1]) else None
        
        rv_percentile = calculate_rolling_percentile(rv, window=self.normalization_window)
        rv_pct_current = float(rv_percentile.iloc[-1]) if not pd.isna(rv_percentile.iloc[-1]) else np.nan
        
        # 2. Trend Math
        er = calculate_efficiency_ratio(df, window=10)
        persistence = calculate_directional_persistence(df, window=10)
        atr_trend = calculate_atr_scaled_trend(df, window=20)
        persist_current = float(persistence.iloc[-1]) if not pd.isna(persistence.iloc[-1]) else None
        
        # 3. Momentum Math (Robust Z-Score)
        momentum = calculate_standardized_momentum(df, window=20)
        mom_current = float(momentum.iloc[-1]) if not pd.isna(momentum.iloc[-1]) else None
        
        mom_accel = calculate_momentum_acceleration(df, momentum_window=20, roc_window=5)
        accel_current = float(mom_accel.iloc[-1]) if not pd.isna(mom_accel.iloc[-1]) else None
        
        # 4. Liquidity & Order Flow (Graceful degradation if missing)
        spread = snapshot.microstructure.relative_spread if snapshot.microstructure and snapshot.microstructure.relative_spread is not None else np.nan
            
        ofi = np.nan # Canonical OFI is UNAVAILABLE
        cvd = snapshot.cvd if snapshot.cvd is not None else np.nan
        tvi = snapshot.tvi if snapshot.tvi is not None else np.nan
        
        # 5. Missing Data Modules
        oi_series = pd.Series([obs.open_interest for obs in snapshot.open_interest_history]) if snapshot.open_interest_history else None
        funding_series = pd.Series([obs.funding_rate for obs in snapshot.funding_history]) if snapshot.funding_history else None
        
        # VWAP integration
        vwap_result = calculate_vwap(df, window=15)
        snapshot.vwap_raw = vwap_result.raw_value
        snapshot.vwap_deviation = vwap_result.normalized_value
        
        # We need a price history that matches OI observations to infer OI states.
        # But OI history timestamps might not align perfectly with OHLCV. 
        # For this version, we will just pass the closing prices from OHLCV and align them loosely
        # by taking the tail matching the length of oi_series, or passing the full price_series.
        # If lengths mismatch, analyze_open_interest_state will compare start/end.
        price_series = pd.Series([bar.close for bar in snapshot.ohlcv]) if snapshot.ohlcv else None
        if oi_series is not None and price_series is not None:
            if len(price_series) > len(oi_series):
                price_series = price_series.tail(len(oi_series)).reset_index(drop=True)
            elif len(oi_series) > len(price_series):
                oi_series = oi_series.tail(len(price_series)).reset_index(drop=True)

        oi_state = analyze_open_interest_state(price_series, oi_series)
        funding_state = analyze_funding_state(funding_series)
        liq_state = analyze_liquidation_state()
        
        # =====================================================================
        # SLOW PATH (Asynchronous / Cached in production)
        # =====================================================================
        regime_data = classify_regime_hmm(None, None) # Stubbed
        structural_break = detect_structural_break(rv) # Stubbed
        
        # =====================================================================
        # SCORING & ENTROPY
        # =====================================================================
        vol_score = calculate_advisory_volatility_score(rv_pct_current)
        
        # Composite Probability (Logistic Regression Stub)
        direction_prob = calculate_composite_directional_probability({})
        direction = "UNKNOWN"
        
        # =====================================================================
        # ASSEMBLE STATE
        # =====================================================================
        return MarketState(
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            timeframe=snapshot.timeframe,
            
            direction=direction,
            direction_probability=direction_prob,
            
            volatility_score=vol_score,
            momentum_score=mom_current,
            trend_persistence=persist_current,
            
            liquidity_state="VALID" if not np.isnan(spread) else "UNAVAILABLE",
            order_flow_state="VALID" if not np.isnan(cvd) else "UNAVAILABLE",
            oi_state=oi_state.data_quality.name,
            funding_state=funding_state.data_quality.name,
            liquidation_state=liq_state.data_quality.name,
            
            vwap=snapshot.vwap_raw,
            vwap_deviation=snapshot.vwap_deviation,
            
            microstructure=snapshot.microstructure,
            
            regime=regime_data["dominant_state"],
            regime_probability=None,
            
            factor_conflict=None,
            structural_break=structural_break,
            
            # Freshness state for slow path
            slow_path_calculated_at=None,
            slow_path_age_seconds=None,
            slow_path_freshness="UNAVAILABLE",
            
            data_quality=DataQuality.VALID,
            feature_statuses={
                "volatility": FeatureStatus.VALIDATED,
                "momentum": FeatureStatus.VALIDATED,
                "trend": FeatureStatus.VALIDATED,
                "order_flow": FeatureStatus.EXPERIMENTAL,
                "vwap": vwap_result.data_quality.name,
                "regime": FeatureStatus.RESEARCH_ONLY,
                "logistic_regression": FeatureStatus.RESEARCH_ONLY
            }
        )
        return state
