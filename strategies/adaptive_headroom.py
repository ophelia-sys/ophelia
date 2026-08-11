import math
from enum import Enum
from typing import Dict

class HeadroomDecision(Enum):
    ALLOW_NORMAL = "ALLOW_NORMAL"
    ALLOW_KRONOS_OVERRIDE = "ALLOW_KRONOS_OVERRIDE"
    BLOCK = "BLOCK"

class MarketTier(Enum):
    WEAK_CHOPPY = "WEAK_CHOPPY"
    NORMAL_TREND = "NORMAL_TREND"
    STRONG_TREND = "STRONG_TREND"
    EXTREME_ALIGNED_TREND = "EXTREME_ALIGNED_TREND"

class AdaptiveHeadroom:
    
    @staticmethod
    def is_lte(val: float, threshold: float, abs_tol: float = 1e-9) -> bool:
        """Evaluate less than or equal to, with float safe bounding."""
        return val <= threshold or math.isclose(val, threshold, abs_tol=abs_tol)
        
    @staticmethod
    def is_gt(val: float, threshold: float, abs_tol: float = 1e-9) -> bool:
        """Evaluate strictly greater than, with float safe bounding."""
        return val > threshold and not math.isclose(val, threshold, abs_tol=abs_tol)

    @staticmethod
    def evaluate_market_tier(
        er10: float, 
        nes: float, 
        nslope: float, 
        bbs: float, 
        rvol20: float, 
        mrs_bullish: float,
        mrs_bearish: float,
        trigger_direction: str,
        structure_5m_aligned: bool
    ) -> MarketTier:
        mrs = mrs_bullish if trigger_direction == "BULLISH" else mrs_bearish
        
        # Extreme Aligned Trend
        if (er10 >= 0.80 and 
            abs(nes) >= 0.80 and 
            abs(nslope) >= 0.20 and 
            bbs >= 0.90 and 
            rvol20 >= 1.50 and 
            mrs >= 80 and 
            structure_5m_aligned):
            return MarketTier.EXTREME_ALIGNED_TREND
            
        # Strong Trend
        if (er10 >= 0.60 and 
            abs(nes) >= 0.60 and 
            abs(nslope) >= 0.15 and 
            bbs >= 0.80 and 
            rvol20 >= 1.20 and 
            mrs >= 70 and 
            structure_5m_aligned):
            return MarketTier.STRONG_TREND
            
        # Normal Trend (Hard filters passed implicitly if we reach here, so >=65 MRS and >=0.50 ER10)
        if (er10 >= 0.50 and 
            abs(nes) >= 0.40 and 
            abs(nslope) >= 0.08 and 
            bbs >= 0.75 and 
            mrs >= 65 and 
            structure_5m_aligned):
            return MarketTier.NORMAL_TREND
            
        return MarketTier.WEAK_CHOPPY

    @classmethod
    def evaluate_oversized_candle(
        cls,
        timeframe: str,
        candle_pct: float,
        trigger_direction: str,
        kronos_direction: str,
        kronos_score: float,
        tier: MarketTier,
        candidate_thresholds: Dict[MarketTier, float],
        baseline_threshold: float = 0.77
    ) -> HeadroomDecision:
        
        # 1. Handle absolute blocks and allow normal
        if timeframe == "1m":
            if cls.is_gt(candle_pct, 0.40):
                return HeadroomDecision.BLOCK
            if cls.is_lte(candle_pct, 0.20):
                return HeadroomDecision.ALLOW_NORMAL
                
        elif timeframe == "5m":
            if cls.is_gt(candle_pct, 0.60):
                return HeadroomDecision.BLOCK
            if cls.is_lte(candle_pct, 0.35):
                return HeadroomDecision.ALLOW_NORMAL
                
        # 2. Oversized, evaluate Kronos Override
        # Direction must match perfectly
        if trigger_direction != kronos_direction:
            return HeadroomDecision.BLOCK
            
        # 3. Determine Candidate Threshold based on Tier
        threshold = baseline_threshold
        if tier in [MarketTier.STRONG_TREND, MarketTier.EXTREME_ALIGNED_TREND]:
            threshold = candidate_thresholds.get(tier, baseline_threshold)
            
        if tier == MarketTier.WEAK_CHOPPY:
            threshold = baseline_threshold

        # 4. Score check (must be strictly > threshold in magnitude)
        if trigger_direction == "BULLISH":
            if cls.is_gt(kronos_score, threshold):
                return HeadroomDecision.ALLOW_KRONOS_OVERRIDE
        elif trigger_direction == "BEARISH":
            if cls.is_gt(-kronos_score, threshold):
                return HeadroomDecision.ALLOW_KRONOS_OVERRIDE
                
        return HeadroomDecision.BLOCK
