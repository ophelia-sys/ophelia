"""Ophelia Phase 6A: Microstructure Research Data Models.

Authoritative contracts for Trade-Flow Innovation and Trade-Duration.
Strictly research mode only (zero trading authority).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class QualityState(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    MISSING = "MISSING"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    DEGRADED = "DEGRADED"


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class MissingnessState(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class AggressorSource(str, Enum):
    DIRECT = "DIRECT"
    INFERRED = "INFERRED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class FlowDirection(int, Enum):
    BUY = 1
    NEUTRAL = 0
    SELL = -1


@dataclass(frozen=True)
class TradeTick:
    """Individual trade tick ingested for microstructure analysis."""
    instrument: str
    venue: str
    event_timestamp: int  # ms
    received_timestamp: int  # ms
    price: float
    quantity: float
    aggressor_side: Optional[str] = None  # "BUY", "SELL", or None
    trade_id: Optional[str] = None
    source_quality: str = "REALTIME"

    @property
    def fingerprint(self) -> str:
        """Deterministic fingerprint for duplicate identification."""
        if self.trade_id:
            return f"{self.venue}:{self.instrument}:{self.trade_id}"
        return f"{self.venue}:{self.instrument}:{self.event_timestamp}:{self.price:.6f}:{self.quantity:.6f}:{self.aggressor_side or 'N'}"


@dataclass(frozen=True)
class MicrostructureProvenance:
    """Standardized machine-readable provenance contract."""
    instrument: str
    venue: str
    event_timestamp: int
    received_timestamp: int
    feature_version: str = "1.0.0"
    schema_version: str = "v1"
    source_data_type: str = "TRADE_TICKS"
    sample_count: int = 0
    quality_state: QualityState = QualityState.VALID
    freshness_state: FreshnessState = FreshnessState.FRESH
    missingness_state: MissingnessState = MissingnessState.COMPLETE
    calculation_window: int = 60000  # lookback window ms
    mode: str = "RESEARCH"


@dataclass(frozen=True)
class TradeFlowObservation:
    """Module 1: Trade-Flow Innovation Output Contract."""
    provenance: MicrostructureProvenance
    signed_flow: float
    expected_flow: float
    flow_innovation: float
    flow_zscore: float
    flow_direction: FlowDirection
    flow_persistence: float
    aggressor_source: AggressorSource
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.provenance.instrument,
            "venue": self.provenance.venue,
            "event_timestamp": self.provenance.event_timestamp,
            "received_timestamp": self.provenance.received_timestamp,
            "feature_version": self.provenance.feature_version,
            "schema_version": self.provenance.schema_version,
            "source_data_type": self.provenance.source_data_type,
            "sample_count": self.provenance.sample_count,
            "quality_state": self.provenance.quality_state.value,
            "freshness_state": self.provenance.freshness_state.value,
            "missingness_state": self.provenance.missingness_state.value,
            "calculation_window": self.provenance.calculation_window,
            "mode": self.provenance.mode,
            "signed_flow": round(self.signed_flow, 4),
            "expected_flow": round(self.expected_flow, 4),
            "flow_innovation": round(self.flow_innovation, 4),
            "flow_zscore": round(self.flow_zscore, 4),
            "flow_direction": self.flow_direction.value,
            "flow_persistence": round(self.flow_persistence, 4),
            "aggressor_source": self.aggressor_source.value,
            "detail": self.detail
        }


@dataclass(frozen=True)
class TradeDurationObservation:
    """Module 2: Trade Duration / Arrival Pressure Output Contract (Non-Directional)."""
    provenance: MicrostructureProvenance
    duration_ms: float
    expected_duration_ms: float
    duration_pressure: float
    arrival_intensity: float
    duration_zscore: float
    persistence: float
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.provenance.instrument,
            "venue": self.provenance.venue,
            "event_timestamp": self.provenance.event_timestamp,
            "received_timestamp": self.provenance.received_timestamp,
            "feature_version": self.provenance.feature_version,
            "schema_version": self.provenance.schema_version,
            "source_data_type": self.provenance.source_data_type,
            "sample_count": self.provenance.sample_count,
            "quality_state": self.provenance.quality_state.value,
            "freshness_state": self.provenance.freshness_state.value,
            "missingness_state": self.provenance.missingness_state.value,
            "calculation_window": self.provenance.calculation_window,
            "mode": self.provenance.mode,
            "duration_ms": round(self.duration_ms, 2),
            "expected_duration_ms": round(self.expected_duration_ms, 2),
            "duration_pressure": round(self.duration_pressure, 4),
            "arrival_intensity": round(self.arrival_intensity, 6),
            "duration_zscore": round(self.duration_zscore, 4),
            "persistence": round(self.persistence, 4),
            "detail": self.detail
        }


# ==========================================
# PHASE 6B: ORDER BOOK & SPREAD/LIQUIDITY
# ==========================================

@dataclass(frozen=True)
class OrderBookLevel:
    """Individual price level in order book."""
    price: float
    quantity: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Market depth snapshot ingested for microstructure analysis."""
    instrument: str
    venue: str
    event_timestamp: int  # ms
    received_timestamp: int  # ms
    bids: list[OrderBookLevel]  # sorted descending by price
    asks: list[OrderBookLevel]  # sorted ascending by price
    sequence_num: Optional[int] = None
    snapshot_id: Optional[str] = None
    source_quality: str = "REALTIME"

    @property
    def fingerprint(self) -> str:
        """Deterministic fingerprint for duplicate snapshot identification."""
        top_b = f"{self.bids[0].price:.4f}:{self.bids[0].quantity:.4f}" if self.bids else "0:0"
        top_a = f"{self.asks[0].price:.4f}:{self.asks[0].quantity:.4f}" if self.asks else "0:0"
        return f"{self.venue}:{self.instrument}:{self.event_timestamp}:{self.sequence_num or 'N'}:{top_b}:{top_a}"


@dataclass(frozen=True)
class OrderBookImbalanceObservation:
    """Module 3: Visible Order-Book Imbalance Output Contract."""
    provenance: MicrostructureProvenance
    depth_requested: int
    depth_available: int
    depth_used: int
    obi_top: Optional[float]
    obi_depth_N: Optional[float]
    bid_depth: float
    ask_depth: float
    imbalance_direction: int  # +1, 0, -1
    imbalance_persistence: Optional[float] = None
    obi_level_1: Optional[float] = None
    obi_level_5: Optional[float] = None
    obi_level_10: Optional[float] = None
    cancellation_flow: str = "NOT_AVAILABLE"
    hidden_liquidity: str = "NOT_AVAILABLE"
    book_snapshot_age_ms: int = 0
    sequence_state: str = "VALID"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.provenance.instrument,
            "venue": self.provenance.venue,
            "event_timestamp": self.provenance.event_timestamp,
            "received_timestamp": self.provenance.received_timestamp,
            "feature_version": self.provenance.feature_version,
            "schema_version": self.provenance.schema_version,
            "source_data_type": self.provenance.source_data_type,
            "sample_count": self.provenance.sample_count,
            "quality_state": self.provenance.quality_state.value,
            "freshness_state": self.provenance.freshness_state.value,
            "missingness_state": self.provenance.missingness_state.value,
            "calculation_window": self.provenance.calculation_window,
            "mode": self.provenance.mode,
            "depth_requested": self.depth_requested,
            "depth_available": self.depth_available,
            "depth_used": self.depth_used,
            "obi_top": round(self.obi_top, 4) if self.obi_top is not None else None,
            "obi_depth_N": round(self.obi_depth_N, 4) if self.obi_depth_N is not None else None,
            "bid_depth": round(self.bid_depth, 4),
            "ask_depth": round(self.ask_depth, 4),
            "imbalance_direction": self.imbalance_direction,
            "imbalance_persistence": round(self.imbalance_persistence, 4) if self.imbalance_persistence is not None else None,
            "obi_level_1": round(self.obi_level_1, 4) if self.obi_level_1 is not None else None,
            "obi_level_5": round(self.obi_level_5, 4) if self.obi_level_5 is not None else None,
            "obi_level_10": round(self.obi_level_10, 4) if self.obi_level_10 is not None else None,
            "cancellation_flow": self.cancellation_flow,
            "hidden_liquidity": self.hidden_liquidity,
            "book_snapshot_age_ms": self.book_snapshot_age_ms,
            "sequence_state": self.sequence_state,
            "detail": self.detail
        }


@dataclass(frozen=True)
class SpreadLiquidityStressObservation:
    """Module 4: Spread & Liquidity Stress Output Contract (Non-Directional)."""
    provenance: MicrostructureProvenance
    spread: Optional[float]
    mid_price: Optional[float]
    relative_spread: Optional[float]
    expected_spread: Optional[float] = None
    spread_zscore: Optional[float] = None
    spread_percentile: Optional[float] = None
    spread_stress: Optional[float] = None
    depth_stress: Optional[float] = None
    book_thinning: Optional[bool] = None
    liquidity_stress: Optional[float] = None
    liquidity_recovery_state: str = "NOT_AVAILABLE"  # NORMAL, THINNING, STRESSED, RECOVERING, NOT_AVAILABLE
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.provenance.instrument,
            "venue": self.provenance.venue,
            "event_timestamp": self.provenance.event_timestamp,
            "received_timestamp": self.provenance.received_timestamp,
            "feature_version": self.provenance.feature_version,
            "schema_version": self.provenance.schema_version,
            "source_data_type": self.provenance.source_data_type,
            "sample_count": self.provenance.sample_count,
            "quality_state": self.provenance.quality_state.value,
            "freshness_state": self.provenance.freshness_state.value,
            "missingness_state": self.provenance.missingness_state.value,
            "calculation_window": self.provenance.calculation_window,
            "mode": self.provenance.mode,
            "spread": round(self.spread, 4) if self.spread is not None else None,
            "mid_price": round(self.mid_price, 4) if self.mid_price is not None else None,
            "relative_spread": round(self.relative_spread, 6) if self.relative_spread is not None else None,
            "expected_spread": round(self.expected_spread, 4) if self.expected_spread is not None else None,
            "spread_zscore": round(self.spread_zscore, 4) if self.spread_zscore is not None else None,
            "spread_percentile": round(self.spread_percentile, 2) if self.spread_percentile is not None else None,
            "spread_stress": round(self.spread_stress, 4) if self.spread_stress is not None else None,
            "depth_stress": round(self.depth_stress, 4) if self.depth_stress is not None else None,
            "book_thinning": self.book_thinning,
            "liquidity_stress": round(self.liquidity_stress, 4) if self.liquidity_stress is not None else None,
            "liquidity_recovery_state": self.liquidity_recovery_state,
            "detail": self.detail
        }


# ==========================================
# PHASE 6C: PRICE IMPACT & TOXICITY REGIMES
# ==========================================

@dataclass(frozen=True)
class PriceImpactObservation:
    """Module 5: Empirical Price Impact Output Contract (Kyle-inspired)."""
    provenance: MicrostructureProvenance
    impact_coefficient: Optional[float] = None
    impact_direction: int = 0  # +1, 0, -1
    impact_stability: Optional[float] = None  # R^2 or coefficient t-ratio/stability
    impact_asymmetry: Optional[float] = None  # buy_impact - sell_impact
    buy_impact: Optional[float] = None
    sell_impact: Optional[float] = None
    flow_response: Optional[float] = None
    horizon_steps: int = 1
    sample_count: int = 0
    methodology_version: str = "KYLE_INSPIRED_EMPIRICAL_IMPACT"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.provenance.instrument,
            "venue": self.provenance.venue,
            "event_timestamp": self.provenance.event_timestamp,
            "received_timestamp": self.provenance.received_timestamp,
            "feature_version": self.provenance.feature_version,
            "schema_version": self.provenance.schema_version,
            "source_data_type": self.provenance.source_data_type,
            "sample_count": self.sample_count,
            "quality_state": self.provenance.quality_state.value,
            "freshness_state": self.provenance.freshness_state.value,
            "missingness_state": self.provenance.missingness_state.value,
            "calculation_window": self.provenance.calculation_window,
            "mode": self.provenance.mode,
            "methodology_version": self.methodology_version,
            "impact_coefficient": round(self.impact_coefficient, 6) if self.impact_coefficient is not None else None,
            "impact_direction": self.impact_direction,
            "impact_stability": round(self.impact_stability, 4) if self.impact_stability is not None else None,
            "impact_asymmetry": round(self.impact_asymmetry, 6) if self.impact_asymmetry is not None else None,
            "buy_impact": round(self.buy_impact, 6) if self.buy_impact is not None else None,
            "sell_impact": round(self.sell_impact, 6) if self.sell_impact is not None else None,
            "flow_response": round(self.flow_response, 6) if self.flow_response is not None else None,
            "horizon_steps": self.horizon_steps,
            "detail": self.detail
        }


@dataclass(frozen=True)
class ToxicityObservation:
    """Module 6: Toxicity / Adverse Flow Output Contract (VPIN-inspired research)."""
    provenance: MicrostructureProvenance
    flow_intensity: Optional[float] = None
    adverse_price_response: Optional[float] = None
    spread_stress_context: Optional[float] = None
    depth_stress_context: Optional[float] = None
    trade_arrival_stress: Optional[float] = None
    toxicity_metric: Optional[float] = None  # VPIN-inspired volume imbalance fraction
    toxicity_state: str = "NOT_AVAILABLE"  # LOW, NORMAL, ELEVATED, TOXIC, INSUFFICIENT_SAMPLE, NOT_AVAILABLE
    sample_count: int = 0
    methodology_version: str = "VPIN_INSPIRED_RESEARCH"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.provenance.instrument,
            "venue": self.provenance.venue,
            "event_timestamp": self.provenance.event_timestamp,
            "received_timestamp": self.provenance.received_timestamp,
            "feature_version": self.provenance.feature_version,
            "schema_version": self.provenance.schema_version,
            "source_data_type": self.provenance.source_data_type,
            "sample_count": self.sample_count,
            "quality_state": self.provenance.quality_state.value,
            "freshness_state": self.provenance.freshness_state.value,
            "missingness_state": self.provenance.missingness_state.value,
            "calculation_window": self.provenance.calculation_window,
            "mode": self.provenance.mode,
            "methodology_version": self.methodology_version,
            "flow_intensity": round(self.flow_intensity, 4) if self.flow_intensity is not None else None,
            "adverse_price_response": round(self.adverse_price_response, 6) if self.adverse_price_response is not None else None,
            "spread_stress_context": round(self.spread_stress_context, 4) if self.spread_stress_context is not None else None,
            "depth_stress_context": round(self.depth_stress_context, 4) if self.depth_stress_context is not None else None,
            "trade_arrival_stress": round(self.trade_arrival_stress, 4) if self.trade_arrival_stress is not None else None,
            "toxicity_metric": round(self.toxicity_metric, 4) if self.toxicity_metric is not None else None,
            "toxicity_state": self.toxicity_state,
            "detail": self.detail
        }


