from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class DataQuality(Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"

class FeatureStatus(Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    EXPERIMENTAL = "EXPERIMENTAL"
    VALIDATED = "VALIDATED"
    PRODUCTION_APPROVED = "PRODUCTION_APPROVED"

class Direction(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"

@dataclass
class Provenance:
    symbol: str
    timestamp: int
    timeframe: str
    source: str
    raw_inputs_used: List[str]
    lookback: int
    formula: str
    normalization_method: str
    calculation_version: str
    data_quality: DataQuality
    status: FeatureStatus
    calibrated: bool = False

@dataclass
class FeatureResult:
    raw_value: Optional[float]
    normalized_value: Optional[float]
    direction: Direction
    confidence: Optional[float]
    data_quality: DataQuality
    provenance: Provenance

@dataclass
class FactorResult:
    factor_score: Optional[float]
    direction: Direction
    confidence: Optional[float]
    internal_agreement: float
    data_quality: DataQuality
    features: Dict[str, FeatureResult] = field(default_factory=dict)
    provenance: Optional[Provenance] = None

@dataclass
class MicrostructureState:
    mid_price: Optional[float] = None
    spread: Optional[float] = None
    relative_spread: Optional[float] = None
    queue_imbalance: Optional[float] = None
    depth_imbalance: Optional[float] = None
    microprice: Optional[float] = None
    book_slope_bid: Optional[float] = None
    book_slope_ask: Optional[float] = None
    book_concentration: Optional[float] = None
    visible_impact_buy: Optional[float] = None
    visible_impact_sell: Optional[float] = None
    data_quality: DataQuality = DataQuality.UNAVAILABLE

@dataclass
class MarketState:
    symbol: str
    timestamp: int
    timeframe: str
    
    # Core outputs
    direction: str = "UNKNOWN"
    direction_probability: Optional[float] = None
    
    volatility_score: Optional[int] = None
    momentum_score: Optional[float] = None
    trend_persistence: Optional[float] = None
    
    # VWAP metrics
    vwap: Optional[float] = None
    vwap_deviation: Optional[float] = None
    
    # State fields
    liquidity_state: str = "UNAVAILABLE"
    order_flow_state: str = "UNAVAILABLE"
    oi_state: str = "UNAVAILABLE"
    funding_state: str = "UNAVAILABLE"
    liquidation_state: str = "UNAVAILABLE"
    
    microstructure: Optional[MicrostructureState] = None
    
    # Advanced stats
    regime: str = "UNKNOWN"
    regime_probability: Optional[float] = None
    
    factor_conflict: Optional[float] = None  # Entropy
    structural_break: Optional[bool] = None
    
    # Slow path freshness tracking
    slow_path_calculated_at: Optional[int] = None
    slow_path_age_seconds: Optional[float] = None
    slow_path_freshness: str = "UNAVAILABLE"
    
    # Diagnostics
    data_quality: DataQuality = DataQuality.UNAVAILABLE
    feature_statuses: Dict[str, FeatureStatus] = field(default_factory=dict)
    provenance: Optional[Provenance] = None
    explanations: List[str] = field(default_factory=list)
