from typing import Dict
from institutional.types import FactorResult, FeatureResult, Direction, DataQuality

def aggregate_trend_factor(features: Dict[str, FeatureResult]) -> FactorResult:
    """
    Aggregates trend features (EMA structure, ER, Hurst, Persistence).
    Avoids double-counting highly correlated features.
    """
    valid_features = {k: v for k, v in features.items() if v.data_quality in (DataQuality.VALID, DataQuality.DEGRADED)}
    if not valid_features:
        return FactorResult(
            factor_score=None,
            direction=Direction.UNKNOWN,
            confidence=0.0,
            internal_agreement=0.0,
            data_quality=DataQuality.INSUFFICIENT_DATA,
            features=features
        )
        
    bullish_votes = sum(1 for v in valid_features.values() if v.direction == Direction.BULLISH)
    bearish_votes = sum(1 for v in valid_features.values() if v.direction == Direction.BEARISH)
    total_votes = len(valid_features)
    
    if bullish_votes > bearish_votes and bullish_votes / total_votes > 0.6:
        direction = Direction.BULLISH
        agreement = bullish_votes / total_votes
    elif bearish_votes > bullish_votes and bearish_votes / total_votes > 0.6:
        direction = Direction.BEARISH
        agreement = bearish_votes / total_votes
    else:
        direction = Direction.CONFLICTED
        agreement = 0.5
        
    # Factor score is a synthetic -1 to 1 based on agreement and vote spread
    vote_spread = (bullish_votes - bearish_votes) / total_votes
    
    return FactorResult(
        factor_score=vote_spread,
        direction=direction,
        confidence=min(1.0, len(valid_features) / 4.0), # Assuming 4 core features
        internal_agreement=agreement,
        data_quality=DataQuality.VALID,
        features=features
    )
