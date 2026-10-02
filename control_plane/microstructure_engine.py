"""Ophelia Phase 6A: Microstructure Research Engine.

Modules:
- Module 1: Trade-Flow Innovation
- Module 2: Trade Duration / Arrival Pressure (Dufour-Engle Style)

Strictly RESEARCH ONLY. Zero direct execution authority.
"""
from __future__ import annotations

import collections
import json
import logging
import math
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from models.microstructure import (
    AggressorSource,
    FlowDirection,
    FreshnessState,
    MicrostructureProvenance,
    MissingnessState,
    OrderBookImbalanceObservation,
    OrderBookLevel,
    OrderBookSnapshot,
    PriceImpactObservation,
    QualityState,
    SpreadLiquidityStressObservation,
    ToxicityObservation,
    TradeDurationObservation,
    TradeFlowObservation,
    TradeTick,
)

logger = logging.getLogger("ophelia.microstructure")


class TradeFlowInnovationEngine:
    """Module 1: Trade-Flow Innovation Research Feature."""

    def __init__(
        self,
        instrument: str,
        venue: str = "BINGX",
        min_sample_size: int = 20,
        slow_window_size: int = 100,
        max_freshness_ms: int = 300000,  # 5 minutes
    ):
        self.instrument = instrument
        self.venue = venue
        self.min_sample_size = min_sample_size
        self.slow_window_size = slow_window_size
        self.max_freshness_ms = max_freshness_ms

        self.last_event_ts: Optional[int] = None
        self.prev_price: Optional[float] = None
        self.prev_aggressor_side: Optional[str] = None

        # Rolling history of signed volumes: List[float]
        self.signed_volumes: collections.deque[float] = collections.deque(maxlen=self.slow_window_size)
        self.seen_fingerprints: collections.deque[str] = collections.deque(maxlen=1000)
        self._fingerprints_set: set[str] = set()

    def _track_fingerprint(self, fp: str) -> bool:
        if fp in self._fingerprints_set:
            return True
        if len(self.seen_fingerprints) >= 1000:
            removed = self.seen_fingerprints.popleft()
            self._fingerprints_set.discard(removed)
        self.seen_fingerprints.append(fp)
        self._fingerprints_set.add(fp)
        return False

    def process_tick(self, tick: TradeTick) -> TradeFlowObservation:
        now_ms = int(time.time() * 1000)
        fp = tick.fingerprint

        # 1. Duplicate check
        if self._track_fingerprint(fp):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.signed_volumes),
                quality_state=QualityState.DUPLICATE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.COMPLETE,
            )
            return TradeFlowObservation(
                provenance=prov,
                signed_flow=0.0,
                expected_flow=self._get_expected_flow(),
                flow_innovation=0.0,
                flow_zscore=0.0,
                flow_direction=FlowDirection.NEUTRAL,
                flow_persistence=self._calculate_persistence(),
                aggressor_source=AggressorSource.NOT_AVAILABLE,
                detail={"reason": "DUPLICATE_TICK_DROPPED", "fingerprint": fp}
            )

        # 2. Future timestamp check
        if tick.event_timestamp > (now_ms + 60000):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.signed_volumes),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.NOT_AVAILABLE,
                missingness_state=MissingnessState.MISSING,
            )
            return TradeFlowObservation(
                provenance=prov,
                signed_flow=0.0,
                expected_flow=self._get_expected_flow(),
                flow_innovation=0.0,
                flow_zscore=0.0,
                flow_direction=FlowDirection.NEUTRAL,
                flow_persistence=0.0,
                aggressor_source=AggressorSource.NOT_AVAILABLE,
                detail={"reason": "FUTURE_TIMESTAMP_REJECTED", "event_ts": tick.event_timestamp, "now_ms": now_ms}
            )

        # 3. Out-of-order event check
        if self.last_event_ts is not None and tick.event_timestamp < self.last_event_ts:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.signed_volumes),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return TradeFlowObservation(
                provenance=prov,
                signed_flow=0.0,
                expected_flow=self._get_expected_flow(),
                flow_innovation=0.0,
                flow_zscore=0.0,
                flow_direction=FlowDirection.NEUTRAL,
                flow_persistence=self._calculate_persistence(),
                aggressor_source=AggressorSource.NOT_AVAILABLE,
                detail={"reason": "OUT_OF_ORDER_EVENT", "last_ts": self.last_event_ts, "tick_ts": tick.event_timestamp}
            )

        # 4. Zero / Invalid quantity check
        if tick.quantity <= 0.0 or tick.price <= 0.0:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.signed_volumes),
                quality_state=QualityState.DEGRADED,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return TradeFlowObservation(
                provenance=prov,
                signed_flow=0.0,
                expected_flow=self._get_expected_flow(),
                flow_innovation=0.0,
                flow_zscore=0.0,
                flow_direction=FlowDirection.NEUTRAL,
                flow_persistence=self._calculate_persistence(),
                aggressor_source=AggressorSource.NOT_AVAILABLE,
                detail={"reason": "INVALID_QUANTITY_OR_PRICE", "qty": tick.quantity, "price": tick.price}
            )

        # 5. Resolve aggressor side
        aggressor_source = AggressorSource.DIRECT
        side = tick.aggressor_side

        if side in ("BUY", "SELL"):
            aggressor_source = AggressorSource.DIRECT
        else:
            # Tick rule inference
            if self.prev_price is not None:
                if tick.price > self.prev_price:
                    side = "BUY"
                    aggressor_source = AggressorSource.INFERRED
                elif tick.price < self.prev_price:
                    side = "SELL"
                    aggressor_source = AggressorSource.INFERRED
                else:
                    side = self.prev_aggressor_side
                    aggressor_source = AggressorSource.INFERRED if side else AggressorSource.NOT_AVAILABLE
            else:
                side = None
                aggressor_source = AggressorSource.NOT_AVAILABLE

        # Sign multiplier
        if side == "BUY":
            sign = 1.0
            direction = FlowDirection.BUY
        elif side == "SELL":
            sign = -1.0
            direction = FlowDirection.SELL
        else:
            sign = 0.0
            direction = FlowDirection.NEUTRAL

        signed_vol = sign * tick.quantity

        # Quality & Freshness determination
        staleness_ms = now_ms - tick.event_timestamp
        if staleness_ms > self.max_freshness_ms or tick.event_timestamp <= 0:
            freshness = FreshnessState.STALE
            quality = QualityState.STALE
        elif len(self.signed_volumes) + 1 < self.min_sample_size:
            freshness = FreshnessState.FRESH
            quality = QualityState.INSUFFICIENT_SAMPLE
        else:
            freshness = FreshnessState.FRESH
            quality = QualityState.VALID

        # Expected flow & Innovation calculations against prior baseline
        expected_flow = self._get_expected_flow()
        flow_innovation = signed_vol - expected_flow

        # Z-score calculation with winsorization [-5.0, 5.0]
        std = self._get_std_flow()
        if std > 1e-9:
            raw_z = flow_innovation / std
            flow_zscore = max(-5.0, min(5.0, raw_z))
        elif len(self.signed_volumes) > 1 and abs(flow_innovation) > 1e-6:
            flow_zscore = 5.0 if flow_innovation > 0 else -5.0
        else:
            flow_zscore = 0.0

        # Now append signed_vol to rolling window
        self.signed_volumes.append(signed_vol)
        self.last_event_ts = tick.event_timestamp
        self.prev_price = tick.price
        if side:
            self.prev_aggressor_side = side

        sample_count = len(self.signed_volumes)
        persistence = self._calculate_persistence()

        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue=self.venue,
            event_timestamp=tick.event_timestamp,
            received_timestamp=tick.received_timestamp or now_ms,
            sample_count=sample_count,
            quality_state=quality,
            freshness_state=freshness,
            missingness_state=MissingnessState.COMPLETE if quality == QualityState.VALID else MissingnessState.PARTIAL,
        )

        return TradeFlowObservation(
            provenance=prov,
            signed_flow=signed_vol,
            expected_flow=expected_flow,
            flow_innovation=flow_innovation,
            flow_zscore=flow_zscore,
            flow_direction=direction,
            flow_persistence=persistence,
            aggressor_source=aggressor_source,
            detail={
                "price": tick.price,
                "quantity": tick.quantity,
                "trade_id": tick.trade_id,
                "rolling_samples": sample_count
            }
        )

    def _get_expected_flow(self) -> float:
        if not self.signed_volumes:
            return 0.0
        return sum(self.signed_volumes) / len(self.signed_volumes)

    def _get_std_flow(self) -> float:
        n = len(self.signed_volumes)
        if n < 2:
            return 0.0
        mean = sum(self.signed_volumes) / n
        var = sum((x - mean) ** 2 for x in self.signed_volumes) / (n - 1)
        return math.sqrt(max(0.0, var))

    def _calculate_persistence(self) -> float:
        """Autocorrelation lag-1 of signed flow in window."""
        n = len(self.signed_volumes)
        if n < 4:
            return 0.0
        flows = list(self.signed_volumes)
        mean = sum(flows) / n
        var = sum((x - mean) ** 2 for x in flows)
        if var <= 1e-9:
            return 0.0
        cov = sum((flows[i] - mean) * (flows[i - 1] - mean) for i in range(1, n))
        return cov / var


class TradeDurationEngine:
    """Module 2: Trade Duration / Arrival Pressure (Dufour-Engle Style).

    Strictly NON-DIRECTIONAL.
    """

    def __init__(
        self,
        instrument: str,
        venue: str = "BINGX",
        min_sample_size: int = 15,
        window_size: int = 50,
        max_freshness_ms: int = 300000,
    ):
        self.instrument = instrument
        self.venue = venue
        self.min_sample_size = min_sample_size
        self.window_size = window_size
        self.max_freshness_ms = max_freshness_ms

        self.last_event_ts: Optional[int] = None
        self.durations: collections.deque[float] = collections.deque(maxlen=self.window_size)
        self.seen_fingerprints: collections.deque[str] = collections.deque(maxlen=1000)
        self._fingerprints_set: set[str] = set()

    def _track_fingerprint(self, fp: str) -> bool:
        if fp in self._fingerprints_set:
            return True
        if len(self.seen_fingerprints) >= 1000:
            removed = self.seen_fingerprints.popleft()
            self._fingerprints_set.discard(removed)
        self.seen_fingerprints.append(fp)
        self._fingerprints_set.add(fp)
        return False

    def process_tick(self, tick: TradeTick) -> TradeDurationObservation:
        now_ms = int(time.time() * 1000)
        fp = tick.fingerprint

        # 1. Duplicate check
        if self._track_fingerprint(fp):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.durations),
                quality_state=QualityState.DUPLICATE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.COMPLETE,
            )
            return TradeDurationObservation(
                provenance=prov,
                duration_ms=0.0,
                expected_duration_ms=self._get_median_duration(),
                duration_pressure=0.0,
                arrival_intensity=self._get_arrival_intensity(),
                duration_zscore=0.0,
                persistence=self._calculate_persistence(),
                detail={"reason": "DUPLICATE_TICK_DROPPED", "fingerprint": fp}
            )

        # 2. Future timestamp check
        if tick.event_timestamp > (now_ms + 60000):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.durations),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.NOT_AVAILABLE,
                missingness_state=MissingnessState.MISSING,
            )
            return TradeDurationObservation(
                provenance=prov,
                duration_ms=0.0,
                expected_duration_ms=0.0,
                duration_pressure=0.0,
                arrival_intensity=0.0,
                duration_zscore=0.0,
                persistence=0.0,
                detail={"reason": "FUTURE_TIMESTAMP_REJECTED", "event_ts": tick.event_timestamp, "now_ms": now_ms}
            )

        # 3. First tick initialization (one-trade stream)
        if self.last_event_ts is None:
            self.last_event_ts = tick.event_timestamp
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=0,
                quality_state=QualityState.INSUFFICIENT_SAMPLE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return TradeDurationObservation(
                provenance=prov,
                duration_ms=0.0,
                expected_duration_ms=0.0,
                duration_pressure=0.0,
                arrival_intensity=0.0,
                duration_zscore=0.0,
                persistence=0.0,
                detail={"reason": "FIRST_TICK_INITIALIZATION"}
            )

        # 4. Out-of-order event check
        if tick.event_timestamp < self.last_event_ts:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.durations),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return TradeDurationObservation(
                provenance=prov,
                duration_ms=0.0,
                expected_duration_ms=self._get_median_duration(),
                duration_pressure=0.0,
                arrival_intensity=self._get_arrival_intensity(),
                duration_zscore=0.0,
                persistence=self._calculate_persistence(),
                detail={"reason": "OUT_OF_ORDER_EVENT", "last_ts": self.last_event_ts, "tick_ts": tick.event_timestamp}
            )

        # Duration delta in ms
        duration_ms = float(tick.event_timestamp - self.last_event_ts)
        self.durations.append(duration_ms)
        self.last_event_ts = tick.event_timestamp

        sample_count = len(self.durations)

        # Staleness & Quality
        staleness_ms = now_ms - tick.event_timestamp
        if staleness_ms > self.max_freshness_ms or tick.event_timestamp <= 0:
            freshness = FreshnessState.STALE
            quality = QualityState.STALE
        elif sample_count < self.min_sample_size:
            freshness = FreshnessState.FRESH
            quality = QualityState.INSUFFICIENT_SAMPLE
        else:
            freshness = FreshnessState.FRESH
            quality = QualityState.VALID

        median_dur = self._get_median_duration()
        arrival_intensity = 1.0 / max(median_dur, 1.0)
        std_dur = self._get_std_duration()

        # Duration pressure = (expected_duration - duration) / sigma
        # Shorter duration means higher arrival pressure (> 0)
        if std_dur > 1e-6:
            duration_pressure = (median_dur - duration_ms) / std_dur
            duration_zscore = (duration_ms - median_dur) / std_dur
        else:
            duration_pressure = 0.0
            duration_zscore = 0.0

        persistence = self._calculate_persistence()

        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue=self.venue,
            event_timestamp=tick.event_timestamp,
            received_timestamp=tick.received_timestamp or now_ms,
            sample_count=sample_count,
            quality_state=quality,
            freshness_state=freshness,
            missingness_state=MissingnessState.COMPLETE if quality == QualityState.VALID else MissingnessState.PARTIAL,
        )

        return TradeDurationObservation(
            provenance=prov,
            duration_ms=duration_ms,
            expected_duration_ms=median_dur,
            duration_pressure=duration_pressure,
            arrival_intensity=arrival_intensity,
            duration_zscore=duration_zscore,
            persistence=persistence,
            detail={
                "price": tick.price,
                "quantity": tick.quantity,
                "trade_id": tick.trade_id,
                "rolling_samples": sample_count
            }
        )

    def _get_median_duration(self) -> float:
        if not self.durations:
            return 0.0
        sorted_d = sorted(self.durations)
        n = len(sorted_d)
        mid = n // 2
        if n % 2 == 1:
            return sorted_d[mid]
        return (sorted_d[mid - 1] + sorted_d[mid]) / 2.0

    def _get_arrival_intensity(self) -> float:
        med = self._get_median_duration()
        return 1.0 / max(med, 1.0)

    def _get_std_duration(self) -> float:
        n = len(self.durations)
        if n < 2:
            return 0.0
        mean = sum(self.durations) / n
        var = sum((x - mean) ** 2 for x in self.durations) / (n - 1)
        return math.sqrt(max(0.0, var))

    def _calculate_persistence(self) -> float:
        """Autocorrelation lag-1 of durations in window."""
        n = len(self.durations)
        if n < 4:
            return 0.0
        vals = list(self.durations)
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals)
        if var <= 1e-9:
            return 0.0
        cov = sum((vals[i] - mean) * (vals[i - 1] - mean) for i in range(1, n))
        return cov / var


class OrderBookImbalanceEngine:
    """Module 3: Visible Order-Book Imbalance Research Engine."""

    def __init__(
        self,
        instrument: str,
        venue: str = "BINGX",
        depth_requested: int = 10,
        max_window_ms: int = 60000,
        max_samples: int = 100,
        max_freshness_ms: int = 30000,
        min_persistence_samples: int = 5,
    ):
        self.instrument = instrument.upper()
        self.venue = venue.upper()
        self.depth_requested = depth_requested
        self.max_window_ms = max_window_ms
        self.max_samples = max_samples
        self.max_freshness_ms = max_freshness_ms
        self.min_persistence_samples = min_persistence_samples

        self.history: collections.deque[Tuple[int, float]] = collections.deque(maxlen=max_samples)
        self.processed_fingerprints: collections.deque[str] = collections.deque(maxlen=1000)
        self.last_event_ts: int = 0
        self.last_sequence_num: Optional[int] = None

    def process_snapshot(self, snapshot: OrderBookSnapshot) -> OrderBookImbalanceObservation:
        now_ms = int(time.time() * 1000)
        snapshot_age_ms = max(0, now_ms - snapshot.event_timestamp)

        # 1. Reject future event timestamps (> 5s ahead)
        if snapshot.event_timestamp > now_ms + 5000:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.history),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.DEGRADED,
                missingness_state=MissingnessState.PARTIAL,
            )
            return OrderBookImbalanceObservation(
                provenance=prov,
                depth_requested=self.depth_requested,
                depth_available=0,
                depth_used=0,
                obi_top=None,
                obi_depth_N=None,
                bid_depth=0.0,
                ask_depth=0.0,
                imbalance_direction=0,
                imbalance_persistence=self._calculate_persistence(),
                book_snapshot_age_ms=snapshot_age_ms,
                sequence_state="NOT_AVAILABLE",
                detail={"error": "future_timestamp_rejected"}
            )

        # 2. Check out-of-order event timestamps
        if self.last_event_ts > 0 and snapshot.event_timestamp < self.last_event_ts:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.history),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.DEGRADED,
                missingness_state=MissingnessState.PARTIAL,
            )
            return OrderBookImbalanceObservation(
                provenance=prov,
                depth_requested=self.depth_requested,
                depth_available=0,
                depth_used=0,
                obi_top=None,
                obi_depth_N=None,
                bid_depth=0.0,
                ask_depth=0.0,
                imbalance_direction=0,
                imbalance_persistence=self._calculate_persistence(),
                book_snapshot_age_ms=snapshot_age_ms,
                sequence_state="NOT_AVAILABLE",
                detail={"error": "out_of_order_snapshot"}
            )

        # 3. Check duplicate snapshots
        fp = snapshot.fingerprint
        if fp in self.processed_fingerprints:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.history),
                quality_state=QualityState.DUPLICATE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return OrderBookImbalanceObservation(
                provenance=prov,
                depth_requested=self.depth_requested,
                depth_available=0,
                depth_used=0,
                obi_top=None,
                obi_depth_N=None,
                bid_depth=0.0,
                ask_depth=0.0,
                imbalance_direction=0,
                imbalance_persistence=self._calculate_persistence(),
                book_snapshot_age_ms=snapshot_age_ms,
                sequence_state="NOT_AVAILABLE",
                detail={"error": "duplicate_snapshot"}
            )

        # 4. Check sequence gaps
        sequence_state = "NOT_AVAILABLE"
        has_sequence_gap = False
        if snapshot.sequence_num is not None:
            if self.last_sequence_num is not None and snapshot.sequence_num != self.last_sequence_num + 1:
                sequence_state = "GAP_DETECTED"
                has_sequence_gap = True
            else:
                sequence_state = "VALID"

        # 5. Check staleness
        is_stale = snapshot_age_ms > self.max_freshness_ms
        freshness = FreshnessState.STALE if is_stale else FreshnessState.FRESH

        quality = QualityState.VALID
        if is_stale:
            quality = QualityState.STALE
        elif has_sequence_gap:
            quality = QualityState.DEGRADED

        # 6. Check empty book
        if not snapshot.bids and not snapshot.asks:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.history),
                quality_state=QualityState.MISSING,
                freshness_state=freshness,
                missingness_state=MissingnessState.MISSING,
            )
            return OrderBookImbalanceObservation(
                provenance=prov,
                depth_requested=self.depth_requested,
                depth_available=0,
                depth_used=0,
                obi_top=None,
                obi_depth_N=None,
                bid_depth=0.0,
                ask_depth=0.0,
                imbalance_direction=0,
                imbalance_persistence=self._calculate_persistence(),
                book_snapshot_age_ms=snapshot_age_ms,
                sequence_state=sequence_state,
                detail={"error": "empty_book"}
            )

        # 7. Check one-sided book
        if not snapshot.bids or not snapshot.asks:
            bid_d = sum(b.quantity for b in snapshot.bids)
            ask_d = sum(a.quantity for a in snapshot.asks)
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.history),
                quality_state=QualityState.INSUFFICIENT_SAMPLE,
                freshness_state=freshness,
                missingness_state=MissingnessState.PARTIAL,
            )
            return OrderBookImbalanceObservation(
                provenance=prov,
                depth_requested=self.depth_requested,
                depth_available=0,
                depth_used=0,
                obi_top=None,
                obi_depth_N=None,
                bid_depth=bid_d,
                ask_depth=ask_d,
                imbalance_direction=0,
                imbalance_persistence=self._calculate_persistence(),
                book_snapshot_age_ms=snapshot_age_ms,
                sequence_state=sequence_state,
                detail={"error": "one_sided_book"}
            )

        # 8. Check crossed book
        if snapshot.bids[0].price >= snapshot.asks[0].price:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.history),
                quality_state=QualityState.DEGRADED,
                freshness_state=freshness,
                missingness_state=MissingnessState.PARTIAL,
            )
            return OrderBookImbalanceObservation(
                provenance=prov,
                depth_requested=self.depth_requested,
                depth_available=min(len(snapshot.bids), len(snapshot.asks)),
                depth_used=0,
                obi_top=None,
                obi_depth_N=None,
                bid_depth=0.0,
                ask_depth=0.0,
                imbalance_direction=0,
                imbalance_persistence=self._calculate_persistence(),
                book_snapshot_age_ms=snapshot_age_ms,
                sequence_state=sequence_state,
                detail={"error": "crossed_book"}
            )

        # 9. Compute multi-level depths and imbalances
        depth_avail = min(len(snapshot.bids), len(snapshot.asks))
        depth_used = min(self.depth_requested, depth_avail)

        # Level 1 (top of book)
        b1 = snapshot.bids[0].quantity
        a1 = snapshot.asks[0].quantity
        obi_top = (b1 - a1) / (b1 + a1) if (b1 + a1) > 0 else None
        obi_level_1 = obi_top

        # Level 5
        obi_level_5 = None
        if depth_avail >= 5:
            b5 = sum(b.quantity for b in snapshot.bids[:5])
            a5 = sum(a.quantity for a in snapshot.asks[:5])
            obi_level_5 = (b5 - a5) / (b5 + a5) if (b5 + a5) > 0 else None

        # Level 10
        obi_level_10 = None
        if depth_avail >= 10:
            b10 = sum(b.quantity for b in snapshot.bids[:10])
            a10 = sum(a.quantity for a in snapshot.asks[:10])
            obi_level_10 = (b10 - a10) / (b10 + a10) if (b10 + a10) > 0 else None

        # Depth N (depth_used)
        bid_depth = sum(b.quantity for b in snapshot.bids[:depth_used])
        ask_depth = sum(a.quantity for a in snapshot.asks[:depth_used])
        total_depth = bid_depth + ask_depth

        if total_depth <= 0.0:
            obi_depth_N = None
            quality = QualityState.NOT_AVAILABLE
            direction = 0
        else:
            obi_depth_N = (bid_depth - ask_depth) / total_depth
            direction = 1 if bid_depth > ask_depth else (-1 if ask_depth > bid_depth else 0)

        # Update historical state
        if obi_depth_N is not None:
            self.history.append((snapshot.event_timestamp, obi_depth_N))
        self.processed_fingerprints.append(fp)
        self.last_event_ts = snapshot.event_timestamp
        if snapshot.sequence_num is not None:
            self.last_sequence_num = snapshot.sequence_num

        persistence = self._calculate_persistence()

        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue=self.venue,
            event_timestamp=snapshot.event_timestamp,
            received_timestamp=snapshot.received_timestamp or now_ms,
            source_data_type="SNAPSHOT_DATA",
            sample_count=len(self.history),
            quality_state=quality,
            freshness_state=freshness,
            missingness_state=MissingnessState.COMPLETE if quality == QualityState.VALID else MissingnessState.PARTIAL,
        )

        return OrderBookImbalanceObservation(
            provenance=prov,
            depth_requested=self.depth_requested,
            depth_available=depth_avail,
            depth_used=depth_used,
            obi_top=obi_top,
            obi_depth_N=obi_depth_N,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            imbalance_direction=direction,
            imbalance_persistence=persistence,
            obi_level_1=obi_level_1,
            obi_level_5=obi_level_5,
            obi_level_10=obi_level_10,
            cancellation_flow="NOT_AVAILABLE",
            hidden_liquidity="NOT_AVAILABLE",
            book_snapshot_age_ms=snapshot_age_ms,
            sequence_state=sequence_state,
            detail={
                "best_bid": snapshot.bids[0].price,
                "best_ask": snapshot.asks[0].price,
                "history_len": len(self.history)
            }
        )

    def _calculate_persistence(self) -> Optional[float]:
        n = len(self.history)
        if n < self.min_persistence_samples:
            return None
        vals = [v for _, v in self.history]
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals)
        if var <= 1e-9:
            return 0.0
        cov = sum((vals[i] - mean) * (vals[i - 1] - mean) for i in range(1, n))
        return cov / var


class SpreadLiquidityStressEngine:
    """Module 4: Spread & Liquidity Stress Research Engine (Non-Directional)."""

    def __init__(
        self,
        instrument: str,
        venue: str = "BINGX",
        max_window_ms: int = 60000,
        max_samples: int = 100,
        max_freshness_ms: int = 30000,
        min_baseline_samples: int = 5,
    ):
        self.instrument = instrument.upper()
        self.venue = venue.upper()
        self.max_window_ms = max_window_ms
        self.max_samples = max_samples
        self.max_freshness_ms = max_freshness_ms
        self.min_baseline_samples = min_baseline_samples

        self.spread_history: collections.deque[float] = collections.deque(maxlen=max_samples)
        self.depth_history: collections.deque[float] = collections.deque(maxlen=max_samples)
        self.processed_fingerprints: collections.deque[str] = collections.deque(maxlen=1000)
        self.last_event_ts: int = 0
        self.prev_recovery_state: str = "NORMAL"

    def process_snapshot(self, snapshot: OrderBookSnapshot) -> SpreadLiquidityStressObservation:
        now_ms = int(time.time() * 1000)
        snapshot_age_ms = max(0, now_ms - snapshot.event_timestamp)

        # 1. Reject future event timestamps (> 5s ahead)
        if snapshot.event_timestamp > now_ms + 5000:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.spread_history),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.DEGRADED,
                missingness_state=MissingnessState.PARTIAL,
            )
            return SpreadLiquidityStressObservation(
                provenance=prov,
                spread=None,
                mid_price=None,
                relative_spread=None,
                expected_spread=None,
                spread_zscore=None,
                spread_percentile=None,
                spread_stress=None,
                depth_stress=None,
                book_thinning=None,
                liquidity_stress=None,
                liquidity_recovery_state="NOT_AVAILABLE",
                detail={"error": "future_timestamp_rejected"}
            )

        # 2. Check out-of-order event timestamps
        if self.last_event_ts > 0 and snapshot.event_timestamp < self.last_event_ts:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.spread_history),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.DEGRADED,
                missingness_state=MissingnessState.PARTIAL,
            )
            return SpreadLiquidityStressObservation(
                provenance=prov,
                spread=None,
                mid_price=None,
                relative_spread=None,
                expected_spread=None,
                spread_zscore=None,
                spread_percentile=None,
                spread_stress=None,
                depth_stress=None,
                book_thinning=None,
                liquidity_stress=None,
                liquidity_recovery_state="NOT_AVAILABLE",
                detail={"error": "out_of_order_snapshot"}
            )

        # 3. Check duplicate snapshots
        fp = snapshot.fingerprint
        if fp in self.processed_fingerprints:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.spread_history),
                quality_state=QualityState.DUPLICATE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return SpreadLiquidityStressObservation(
                provenance=prov,
                spread=None,
                mid_price=None,
                relative_spread=None,
                expected_spread=None,
                spread_zscore=None,
                spread_percentile=None,
                spread_stress=None,
                depth_stress=None,
                book_thinning=None,
                liquidity_stress=None,
                liquidity_recovery_state="NOT_AVAILABLE",
                detail={"error": "duplicate_snapshot"}
            )

        # 4. Check staleness
        is_stale = snapshot_age_ms > self.max_freshness_ms
        freshness = FreshnessState.STALE if is_stale else FreshnessState.FRESH

        quality = QualityState.VALID
        if is_stale:
            quality = QualityState.STALE

        # 5. Check empty book
        if not snapshot.bids and not snapshot.asks:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.spread_history),
                quality_state=QualityState.MISSING,
                freshness_state=freshness,
                missingness_state=MissingnessState.MISSING,
            )
            return SpreadLiquidityStressObservation(
                provenance=prov,
                spread=None,
                mid_price=None,
                relative_spread=None,
                expected_spread=None,
                spread_zscore=None,
                spread_percentile=None,
                spread_stress=None,
                depth_stress=None,
                book_thinning=None,
                liquidity_stress=None,
                liquidity_recovery_state="NOT_AVAILABLE",
                detail={"error": "empty_book"}
            )

        # 6. Check one-sided book
        if not snapshot.bids or not snapshot.asks:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.spread_history),
                quality_state=QualityState.INSUFFICIENT_SAMPLE,
                freshness_state=freshness,
                missingness_state=MissingnessState.PARTIAL,
            )
            return SpreadLiquidityStressObservation(
                provenance=prov,
                spread=None,
                mid_price=None,
                relative_spread=None,
                expected_spread=None,
                spread_zscore=None,
                spread_percentile=None,
                spread_stress=None,
                depth_stress=None,
                book_thinning=None,
                liquidity_stress=None,
                liquidity_recovery_state="NOT_AVAILABLE",
                detail={"error": "one_sided_book"}
            )

        # 7. Check crossed book
        best_bid = snapshot.bids[0].price
        best_ask = snapshot.asks[0].price
        if best_bid >= best_ask:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=snapshot.event_timestamp,
                received_timestamp=snapshot.received_timestamp or now_ms,
                source_data_type="SNAPSHOT_DATA",
                sample_count=len(self.spread_history),
                quality_state=QualityState.DEGRADED,
                freshness_state=freshness,
                missingness_state=MissingnessState.PARTIAL,
            )
            return SpreadLiquidityStressObservation(
                provenance=prov,
                spread=None,
                mid_price=None,
                relative_spread=None,
                expected_spread=None,
                spread_zscore=None,
                spread_percentile=None,
                spread_stress=None,
                depth_stress=None,
                book_thinning=None,
                liquidity_stress=None,
                liquidity_recovery_state="NOT_AVAILABLE",
                detail={"error": "crossed_book", "bid": best_bid, "ask": best_ask}
            )

        # 8. Compute raw observables (immediately valid on N=1)
        spread = best_ask - best_bid
        mid_price = (best_ask + best_bid) / 2.0
        relative_spread = (spread / mid_price) if mid_price > 0 else 0.0

        # Total visible top-5 depth
        top5_bids = sum(b.quantity for b in snapshot.bids[:5])
        top5_asks = sum(a.quantity for a in snapshot.asks[:5])
        total_top5_depth = top5_bids + top5_asks

        # 9. Compute baseline-derived metrics (require min_baseline_samples)
        spread_samples = list(self.spread_history)
        depth_samples = list(self.depth_history)

        if len(spread_samples) < self.min_baseline_samples:
            expected_spread = None
            spread_zscore = None
            spread_percentile = None
            spread_stress = None
            depth_stress = None
            book_thinning = None
            composite_stress = None
            recovery_state = "NOT_AVAILABLE"
            if quality == QualityState.VALID:
                quality = QualityState.INSUFFICIENT_SAMPLE
        else:
            mean_s = sum(spread_samples) / len(spread_samples)
            var_s = sum((x - mean_s) ** 2 for x in spread_samples) / (len(spread_samples) - 1)
            std_s = math.sqrt(max(0.0, var_s))
            expected_spread = mean_s
            spread_zscore = max(-5.0, min(5.0, (spread - mean_s) / max(std_s, 1e-6)))
            spread_percentile = (sum(1 for x in spread_samples if x <= spread) / len(spread_samples)) * 100.0
            spread_stress = max(0.0, spread_zscore)

            mean_d = sum(depth_samples) / len(depth_samples)
            var_d = sum((x - mean_d) ** 2 for x in depth_samples) / (len(depth_samples) - 1)
            std_d = math.sqrt(max(0.0, var_d))
            depth_stress = max(0.0, (mean_d - total_top5_depth) / max(std_d, 1e-6))
            book_thinning = total_top5_depth < (mean_d - 1.5 * std_d)

            composite_stress = 0.5 * spread_stress + 0.5 * depth_stress

            if composite_stress > 2.0:
                recovery_state = "STRESSED"
            elif composite_stress > 1.0:
                recovery_state = "THINNING"
            elif self.prev_recovery_state in ("STRESSED", "THINNING") and composite_stress < 0.8:
                recovery_state = "RECOVERING"
            else:
                recovery_state = "NORMAL"

            self.prev_recovery_state = recovery_state

        self.spread_history.append(spread)
        self.depth_history.append(total_top5_depth)
        self.processed_fingerprints.append(fp)
        self.last_event_ts = snapshot.event_timestamp

        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue=self.venue,
            event_timestamp=snapshot.event_timestamp,
            received_timestamp=snapshot.received_timestamp or now_ms,
            source_data_type="SNAPSHOT_DATA",
            sample_count=len(self.spread_history),
            quality_state=quality,
            freshness_state=freshness,
            missingness_state=MissingnessState.COMPLETE if quality == QualityState.VALID else MissingnessState.PARTIAL,
        )

        return SpreadLiquidityStressObservation(
            provenance=prov,
            spread=spread,
            mid_price=mid_price,
            relative_spread=relative_spread,
            expected_spread=expected_spread,
            spread_zscore=spread_zscore,
            spread_percentile=spread_percentile,
            spread_stress=spread_stress,
            depth_stress=depth_stress,
            book_thinning=book_thinning,
            liquidity_stress=composite_stress,
            liquidity_recovery_state=recovery_state,
            detail={
                "best_bid": best_bid,
                "best_ask": best_ask,
                "top5_depth": total_top5_depth,
                "sample_count": len(self.spread_history)
            }
        )


class PriceImpactEngine:
    """Module 5: Empirical Price Impact Research Engine (Kyle-inspired).
    Strictly causal horizon: flow at t paired with forward return over (t, t+h].
    Zero contemporaneous or future leakage.
    Strictly RESEARCH ONLY.
    """

    def __init__(
        self,
        instrument: str,
        venue: str = "BINGX",
        horizon_steps: int = 1,
        min_sample_size: int = 20,
        max_window_size: int = 100,
        max_freshness_ms: int = 300000,
        min_side_samples: int = 5,
    ):
        self.instrument = instrument.upper()
        self.venue = venue.upper()
        self.horizon_steps = max(1, horizon_steps)
        self.min_sample_size = min_sample_size
        self.max_window_size = max_window_size
        self.max_freshness_ms = max_freshness_ms
        self.min_side_samples = min_side_samples

        # Pending ticks waiting for strictly forward prices: (event_ts, price, signed_flow, quantity, is_buy)
        self.pending_ticks: collections.deque[Tuple[int, float, float, float, bool]] = collections.deque()
        # Evaluated pairs of (signed_flow, forward_return, quantity, is_buy)
        self.evaluated_pairs: collections.deque[Tuple[float, float, float, bool]] = collections.deque(maxlen=max_window_size)
        self.seen_fingerprints: collections.deque[str] = collections.deque(maxlen=1000)
        self._fingerprints_set: set[str] = set()

        self.last_event_ts: Optional[int] = None
        self.prev_price: Optional[float] = None
        self.prev_aggressor_side: Optional[str] = None

    def _track_fingerprint(self, fp: str) -> bool:
        if fp in self._fingerprints_set:
            return True
        if len(self.seen_fingerprints) >= 1000:
            removed = self.seen_fingerprints.popleft()
            self._fingerprints_set.discard(removed)
        self.seen_fingerprints.append(fp)
        self._fingerprints_set.add(fp)
        return False

    def process_tick(self, tick: TradeTick) -> PriceImpactObservation:
        now_ms = int(time.time() * 1000)
        fp = tick.fingerprint

        # 1. Duplicate check
        if self._track_fingerprint(fp):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.evaluated_pairs),
                quality_state=QualityState.DUPLICATE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.COMPLETE,
            )
            return PriceImpactObservation(
                provenance=prov,
                impact_coefficient=None,
                impact_direction=0,
                impact_stability=None,
                impact_asymmetry=None,
                buy_impact=None,
                sell_impact=None,
                flow_response=None,
                horizon_steps=self.horizon_steps,
                sample_count=len(self.evaluated_pairs),
                methodology_version="KYLE_INSPIRED_EMPIRICAL_IMPACT",
                detail={"reason": "DUPLICATE_TICK_DROPPED", "fingerprint": fp}
            )

        # 2. Future timestamp check
        if tick.event_timestamp > (now_ms + 60000):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.evaluated_pairs),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.NOT_AVAILABLE,
                missingness_state=MissingnessState.MISSING,
            )
            return PriceImpactObservation(
                provenance=prov,
                impact_coefficient=None,
                impact_direction=0,
                impact_stability=None,
                impact_asymmetry=None,
                buy_impact=None,
                sell_impact=None,
                flow_response=None,
                horizon_steps=self.horizon_steps,
                sample_count=len(self.evaluated_pairs),
                methodology_version="KYLE_INSPIRED_EMPIRICAL_IMPACT",
                detail={"reason": "FUTURE_TIMESTAMP_REJECTED", "event_ts": tick.event_timestamp}
            )

        # 3. Out-of-order event check
        if self.last_event_ts is not None and tick.event_timestamp < self.last_event_ts:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.evaluated_pairs),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return PriceImpactObservation(
                provenance=prov,
                impact_coefficient=None,
                impact_direction=0,
                impact_stability=None,
                impact_asymmetry=None,
                buy_impact=None,
                sell_impact=None,
                flow_response=None,
                horizon_steps=self.horizon_steps,
                sample_count=len(self.evaluated_pairs),
                methodology_version="KYLE_INSPIRED_EMPIRICAL_IMPACT",
                detail={"reason": "OUT_OF_ORDER_EVENT", "last_ts": self.last_event_ts, "tick_ts": tick.event_timestamp}
            )

        # 4. Zero / Invalid quantity or price check
        if tick.quantity <= 0.0 or tick.price <= 0.0:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.evaluated_pairs),
                quality_state=QualityState.DEGRADED,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return PriceImpactObservation(
                provenance=prov,
                impact_coefficient=None,
                impact_direction=0,
                impact_stability=None,
                impact_asymmetry=None,
                buy_impact=None,
                sell_impact=None,
                flow_response=None,
                horizon_steps=self.horizon_steps,
                sample_count=len(self.evaluated_pairs),
                methodology_version="KYLE_INSPIRED_EMPIRICAL_IMPACT",
                detail={"reason": "INVALID_QUANTITY_OR_PRICE", "qty": tick.quantity, "price": tick.price}
            )

        # 5. Resolve aggressor side
        side = tick.aggressor_side
        if side not in ("BUY", "SELL"):
            if self.prev_price is not None:
                if tick.price > self.prev_price:
                    side = "BUY"
                elif tick.price < self.prev_price:
                    side = "SELL"
                else:
                    side = self.prev_aggressor_side
            else:
                side = None

        sign = 1.0 if side == "BUY" else (-1.0 if side == "SELL" else 0.0)
        signed_flow = sign * tick.quantity
        is_buy = (side == "BUY")

        # 6. Strictly causal pairing:
        # Ticks waiting in pending_ticks reached horizon_steps forward observations.
        # Current tick price tick.price is strictly forward relative to pending ticks.
        while len(self.pending_ticks) >= self.horizon_steps:
            old_ts, old_price, old_flow, old_qty, old_is_buy = self.pending_ticks.popleft()
            if old_price > 0.0:
                fwd_return = (tick.price - old_price) / old_price
                self.evaluated_pairs.append((old_flow, fwd_return, old_qty, old_is_buy))

        self.pending_ticks.append((tick.event_timestamp, tick.price, signed_flow, tick.quantity, is_buy))
        self.last_event_ts = tick.event_timestamp
        self.prev_price = tick.price
        if side:
            self.prev_aggressor_side = side

        # 7. Quality & Freshness determination
        staleness_ms = now_ms - tick.event_timestamp
        n_pairs = len(self.evaluated_pairs)

        if staleness_ms > self.max_freshness_ms or tick.event_timestamp <= 0:
            freshness = FreshnessState.STALE
            quality = QualityState.STALE
        elif n_pairs < self.min_sample_size:
            freshness = FreshnessState.FRESH
            quality = QualityState.INSUFFICIENT_SAMPLE
        else:
            freshness = FreshnessState.FRESH
            quality = QualityState.VALID

        # 8. Empirical Impact Estimation (Kyle-inspired regression: r = lambda * f + epsilon)
        if n_pairs < self.min_sample_size:
            impact_coeff = None
            impact_direction = 0
            impact_stability = None
            impact_asymmetry = None
            buy_impact = None
            sell_impact = None
            flow_response = None
        else:
            flows = [p[0] for p in self.evaluated_pairs]
            returns = [p[1] for p in self.evaluated_pairs]

            mean_f = sum(flows) / n_pairs
            mean_r = sum(returns) / n_pairs

            cov_fr = sum((flows[i] - mean_f) * (returns[i] - mean_r) for i in range(n_pairs))
            var_f = sum((flows[i] - mean_f) ** 2 for i in range(n_pairs))
            var_r = sum((returns[i] - mean_r) ** 2 for i in range(n_pairs))

            if var_f > 1e-12:
                impact_coeff = cov_fr / var_f
                if impact_coeff > 1e-7:
                    impact_direction = 1
                elif impact_coeff < -1e-7:
                    impact_direction = -1
                else:
                    impact_direction = 0

                avg_abs_flow = sum(abs(f) for f in flows) / n_pairs
                flow_response = impact_coeff * avg_abs_flow
            else:
                impact_coeff = 0.0
                impact_direction = 0
                flow_response = 0.0

            if var_f > 1e-12 and var_r > 1e-12:
                r2 = (cov_fr ** 2) / (var_f * var_r)
                impact_stability = max(0.0, min(1.0, r2))
            else:
                impact_stability = 0.0

            # Buy-flow and Sell-flow Impact Asymmetry
            buy_pairs = [(p[0], p[1]) for p in self.evaluated_pairs if p[3] and p[0] > 0]
            sell_pairs = [(p[0], p[1]) for p in self.evaluated_pairs if (not p[3]) and p[0] < 0]

            if len(buy_pairs) >= self.min_side_samples:
                bf_mean = sum(x[0] for x in buy_pairs) / len(buy_pairs)
                br_mean = sum(x[1] for x in buy_pairs) / len(buy_pairs)
                bf_var = sum((x[0] - bf_mean) ** 2 for x in buy_pairs)
                if bf_var > 1e-12:
                    buy_impact = sum((x[0] - bf_mean) * (x[1] - br_mean) for x in buy_pairs) / bf_var
                else:
                    buy_impact = br_mean / max(bf_mean, 1e-6)
            else:
                buy_impact = None

            if len(sell_pairs) >= self.min_side_samples:
                sf_mean = sum(x[0] for x in sell_pairs) / len(sell_pairs)
                sr_mean = sum(x[1] for x in sell_pairs) / len(sell_pairs)
                sf_var = sum((x[0] - sf_mean) ** 2 for x in sell_pairs)
                if sf_var > 1e-12:
                    sell_impact = sum((x[0] - sf_mean) * (x[1] - sr_mean) for x in sell_pairs) / sf_var
                else:
                    sell_impact = sr_mean / min(sf_mean, -1e-6)
            else:
                sell_impact = None

            if buy_impact is not None and sell_impact is not None:
                impact_asymmetry = buy_impact - sell_impact
            else:
                impact_asymmetry = None

        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue=self.venue,
            event_timestamp=tick.event_timestamp,
            received_timestamp=tick.received_timestamp or now_ms,
            sample_count=n_pairs,
            quality_state=quality,
            freshness_state=freshness,
            missingness_state=MissingnessState.COMPLETE if quality == QualityState.VALID else MissingnessState.PARTIAL,
            calculation_window=self.max_window_size,
            mode="RESEARCH",
        )

        return PriceImpactObservation(
            provenance=prov,
            impact_coefficient=impact_coeff,
            impact_direction=impact_direction,
            impact_stability=impact_stability,
            impact_asymmetry=impact_asymmetry,
            buy_impact=buy_impact,
            sell_impact=sell_impact,
            flow_response=flow_response,
            horizon_steps=self.horizon_steps,
            sample_count=n_pairs,
            methodology_version="KYLE_INSPIRED_EMPIRICAL_IMPACT",
            detail={
                "price": tick.price,
                "quantity": tick.quantity,
                "evaluated_pairs_count": n_pairs,
                "pending_ticks_count": len(self.pending_ticks)
            }
        )


class ToxicityEngine:
    """Module 6: Toxicity & Adverse Flow Research Engine (VPIN-inspired research).
    Strictly observable flow/volume behavior and empirical adverse response.
    Zero speculation on MM intent, manipulation, or hidden liquidity.
    Strictly RESEARCH ONLY.
    """

    def __init__(
        self,
        instrument: str,
        venue: str = "BINGX",
        min_sample_size: int = 20,
        max_window_size: int = 100,
        max_freshness_ms: int = 300000,
        num_buckets: int = 5,
    ):
        self.instrument = instrument.upper()
        self.venue = venue.upper()
        self.min_sample_size = min_sample_size
        self.max_window_size = max_window_size
        self.max_freshness_ms = max_freshness_ms
        self.num_buckets = num_buckets

        # Rolling trades: List of (event_ts, price, quantity, signed_flow, side)
        self.trades: collections.deque[Tuple[int, float, float, float, str]] = collections.deque(maxlen=max_window_size)
        self.seen_fingerprints: collections.deque[str] = collections.deque(maxlen=1000)
        self._fingerprints_set: set[str] = set()

        self.last_event_ts: Optional[int] = None
        self.prev_price: Optional[float] = None
        self.prev_aggressor_side: Optional[str] = None

    def _track_fingerprint(self, fp: str) -> bool:
        if fp in self._fingerprints_set:
            return True
        if len(self.seen_fingerprints) >= 1000:
            removed = self.seen_fingerprints.popleft()
            self._fingerprints_set.discard(removed)
        self.seen_fingerprints.append(fp)
        self._fingerprints_set.add(fp)
        return False

    def process_tick(
        self,
        tick: TradeTick,
        spread_stress_context: Optional[float] = None,
        depth_stress_context: Optional[float] = None,
    ) -> ToxicityObservation:
        now_ms = int(time.time() * 1000)
        fp = tick.fingerprint

        # 1. Duplicate check
        if self._track_fingerprint(fp):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.trades),
                quality_state=QualityState.DUPLICATE,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.COMPLETE,
            )
            return ToxicityObservation(
                provenance=prov,
                flow_intensity=None,
                adverse_price_response=None,
                spread_stress_context=spread_stress_context,
                depth_stress_context=depth_stress_context,
                trade_arrival_stress=None,
                toxicity_metric=None,
                toxicity_state="INSUFFICIENT_SAMPLE",
                sample_count=len(self.trades),
                methodology_version="VPIN_INSPIRED_RESEARCH",
                detail={"reason": "DUPLICATE_TICK_DROPPED", "fingerprint": fp}
            )

        # 2. Future timestamp check
        if tick.event_timestamp > (now_ms + 60000):
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.trades),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.NOT_AVAILABLE,
                missingness_state=MissingnessState.MISSING,
            )
            return ToxicityObservation(
                provenance=prov,
                flow_intensity=None,
                adverse_price_response=None,
                spread_stress_context=spread_stress_context,
                depth_stress_context=depth_stress_context,
                trade_arrival_stress=None,
                toxicity_metric=None,
                toxicity_state="INSUFFICIENT_SAMPLE",
                sample_count=len(self.trades),
                methodology_version="VPIN_INSPIRED_RESEARCH",
                detail={"reason": "FUTURE_TIMESTAMP_REJECTED", "event_ts": tick.event_timestamp}
            )

        # 3. Out-of-order event check
        if self.last_event_ts is not None and tick.event_timestamp < self.last_event_ts:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.trades),
                quality_state=QualityState.OUT_OF_ORDER,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return ToxicityObservation(
                provenance=prov,
                flow_intensity=None,
                adverse_price_response=None,
                spread_stress_context=spread_stress_context,
                depth_stress_context=depth_stress_context,
                trade_arrival_stress=None,
                toxicity_metric=None,
                toxicity_state="INSUFFICIENT_SAMPLE",
                sample_count=len(self.trades),
                methodology_version="VPIN_INSPIRED_RESEARCH",
                detail={"reason": "OUT_OF_ORDER_EVENT", "last_ts": self.last_event_ts, "tick_ts": tick.event_timestamp}
            )

        # 4. Zero / Invalid quantity or price check
        if tick.quantity <= 0.0 or tick.price <= 0.0:
            prov = MicrostructureProvenance(
                instrument=self.instrument,
                venue=self.venue,
                event_timestamp=tick.event_timestamp,
                received_timestamp=tick.received_timestamp or now_ms,
                sample_count=len(self.trades),
                quality_state=QualityState.DEGRADED,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.PARTIAL,
            )
            return ToxicityObservation(
                provenance=prov,
                flow_intensity=None,
                adverse_price_response=None,
                spread_stress_context=spread_stress_context,
                depth_stress_context=depth_stress_context,
                trade_arrival_stress=None,
                toxicity_metric=None,
                toxicity_state="INSUFFICIENT_SAMPLE",
                sample_count=len(self.trades),
                methodology_version="VPIN_INSPIRED_RESEARCH",
                detail={"reason": "INVALID_QUANTITY_OR_PRICE", "qty": tick.quantity, "price": tick.price}
            )

        # 5. Resolve aggressor side
        side = tick.aggressor_side
        if side not in ("BUY", "SELL"):
            if self.prev_price is not None:
                if tick.price > self.prev_price:
                    side = "BUY"
                elif tick.price < self.prev_price:
                    side = "SELL"
                else:
                    side = self.prev_aggressor_side
            else:
                side = "NEUTRAL"

        sign = 1.0 if side == "BUY" else (-1.0 if side == "SELL" else 0.0)
        signed_flow = sign * tick.quantity

        # Record trade
        self.trades.append((tick.event_timestamp, tick.price, tick.quantity, signed_flow, side or "NEUTRAL"))
        self.last_event_ts = tick.event_timestamp
        self.prev_price = tick.price
        if side:
            self.prev_aggressor_side = side

        # Quality & Freshness determination
        staleness_ms = now_ms - tick.event_timestamp
        n_trades = len(self.trades)

        if staleness_ms > self.max_freshness_ms or tick.event_timestamp <= 0:
            freshness = FreshnessState.STALE
            quality = QualityState.STALE
        elif n_trades < self.min_sample_size:
            freshness = FreshnessState.FRESH
            quality = QualityState.INSUFFICIENT_SAMPLE
        else:
            freshness = FreshnessState.FRESH
            quality = QualityState.VALID

        # Submetric calculations
        total_vol = sum(t[2] for t in self.trades)
        net_signed_vol = sum(t[3] for t in self.trades)

        flow_intensity = (net_signed_vol / total_vol) if total_vol > 1e-9 else 0.0

        # Adverse price response:
        # Price change from oldest trade in window to current trade
        p0 = self.trades[0][1]
        p_last = tick.price
        p_ret = (p_last - p0) / p0 if p0 > 0 else 0.0
        # If net flow is positive (buyers), price dropping is adverse (+ move against flow)
        flow_sign = 1.0 if net_signed_vol > 0 else (-1.0 if net_signed_vol < 0 else 0.0)
        adverse_price_response = -flow_sign * p_ret

        # Trade arrival stress: arrival density
        time_span_ms = max(1, tick.event_timestamp - self.trades[0][0])
        trade_rate_per_sec = (n_trades * 1000.0) / time_span_ms
        trade_arrival_stress = max(0.0, min(5.0, trade_rate_per_sec / 2.0))

        # VPIN-inspired Volume Imbalance Fraction:
        if n_trades < self.min_sample_size:
            toxicity_metric = None
            toxicity_state = "INSUFFICIENT_SAMPLE"
        else:
            bucket_size = max(1, n_trades // self.num_buckets)
            bucket_imbalances = []
            bucket_totals = []
            trade_list = list(self.trades)

            for b in range(self.num_buckets):
                chunk = trade_list[b * bucket_size : (b + 1) * bucket_size] if b < self.num_buckets - 1 else trade_list[b * bucket_size :]
                if not chunk:
                    continue
                v_buy = sum(t[2] for t in chunk if t[4] == "BUY")
                v_sell = sum(t[2] for t in chunk if t[4] == "SELL")
                bucket_imbalances.append(abs(v_buy - v_sell))
                bucket_totals.append(v_buy + v_sell)

            sum_imb = sum(bucket_imbalances)
            sum_tot = sum(bucket_totals)

            if sum_tot > 1e-9:
                raw_vpin = sum_imb / sum_tot
                toxicity_metric = max(0.0, min(1.0, raw_vpin))
            else:
                toxicity_metric = 0.0

            if toxicity_metric > 0.70:
                toxicity_state = "TOXIC"
            elif toxicity_metric > 0.45:
                toxicity_state = "ELEVATED"
            elif toxicity_metric > 0.20:
                toxicity_state = "NORMAL"
            else:
                toxicity_state = "LOW"

        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue=self.venue,
            event_timestamp=tick.event_timestamp,
            received_timestamp=tick.received_timestamp or now_ms,
            sample_count=n_trades,
            quality_state=quality,
            freshness_state=freshness,
            missingness_state=MissingnessState.COMPLETE if quality == QualityState.VALID else MissingnessState.PARTIAL,
            calculation_window=self.max_window_size,
            mode="RESEARCH",
        )

        return ToxicityObservation(
            provenance=prov,
            flow_intensity=flow_intensity,
            adverse_price_response=adverse_price_response,
            spread_stress_context=spread_stress_context,
            depth_stress_context=depth_stress_context,
            trade_arrival_stress=trade_arrival_stress,
            toxicity_metric=toxicity_metric,
            toxicity_state=toxicity_state,
            sample_count=n_trades,
            methodology_version="VPIN_INSPIRED_RESEARCH",
            detail={
                "total_volume": round(total_vol, 4),
                "net_signed_volume": round(net_signed_vol, 4),
                "window_trades": n_trades,
                "price_return": round(p_ret, 6)
            }
        )


class MicrostructureService:
    """Singleton service orchestrating microstructure research ingestion and calculation."""

    _instance: Optional[MicrostructureService] = None

    def __init__(self):
        self._flow_engines: Dict[str, TradeFlowInnovationEngine] = {}
        self._duration_engines: Dict[str, TradeDurationEngine] = {}
        self._ob_engines: Dict[str, OrderBookImbalanceEngine] = {}
        self._ls_engines: Dict[str, SpreadLiquidityStressEngine] = {}
        self._impact_engines: Dict[str, PriceImpactEngine] = {}
        self._toxicity_engines: Dict[str, ToxicityEngine] = {}

        self._latest_flow: Dict[str, TradeFlowObservation] = {}
        self._latest_duration: Dict[str, TradeDurationObservation] = {}
        self._latest_ob: Dict[str, OrderBookImbalanceObservation] = {}
        self._latest_ls: Dict[str, SpreadLiquidityStressObservation] = {}
        self._latest_impact: Dict[str, PriceImpactObservation] = {}
        self._latest_toxicity: Dict[str, ToxicityObservation] = {}

        self._last_fetch_ts: Dict[str, float] = {}
        self._last_depth_fetch_ts: Dict[str, float] = {}

    @classmethod
    def get_instance(cls) -> MicrostructureService:
        if cls._instance is None:
            cls._instance = MicrostructureService()
        return cls._instance

    def _get_trade_engines(
        self, instrument: str
    ) -> Tuple[TradeFlowInnovationEngine, TradeDurationEngine, PriceImpactEngine, ToxicityEngine]:
        inst = instrument.upper()
        if inst not in self._flow_engines:
            self._flow_engines[inst] = TradeFlowInnovationEngine(instrument=inst)
            self._duration_engines[inst] = TradeDurationEngine(instrument=inst)
            self._impact_engines[inst] = PriceImpactEngine(instrument=inst)
            self._toxicity_engines[inst] = ToxicityEngine(instrument=inst)
        return (
            self._flow_engines[inst],
            self._duration_engines[inst],
            self._impact_engines[inst],
            self._toxicity_engines[inst],
        )

    def _get_order_book_engines(self, instrument: str) -> Tuple[OrderBookImbalanceEngine, SpreadLiquidityStressEngine]:
        inst = instrument.upper()
        if inst not in self._ob_engines:
            self._ob_engines[inst] = OrderBookImbalanceEngine(instrument=inst)
            self._ls_engines[inst] = SpreadLiquidityStressEngine(instrument=inst)
        return self._ob_engines[inst], self._ls_engines[inst]

    def process_tick(
        self, tick: TradeTick
    ) -> Tuple[TradeFlowObservation, TradeDurationObservation, PriceImpactObservation, ToxicityObservation]:
        """Process an individual tick through Modules 1, 2, 5, and 6."""
        flow_engine, dur_engine, impact_engine, tox_engine = self._get_trade_engines(tick.instrument)
        flow_obs = flow_engine.process_tick(tick)
        dur_obs = dur_engine.process_tick(tick)
        impact_obs = impact_engine.process_tick(tick)

        # Contextual stress from Module 4 if available
        ls_obs = self._latest_ls.get(tick.instrument)
        s_stress = ls_obs.spread_stress if ls_obs else None
        d_stress = ls_obs.depth_stress if ls_obs else None
        tox_obs = tox_engine.process_tick(
            tick,
            spread_stress_context=s_stress,
            depth_stress_context=d_stress,
        )

        self._latest_flow[tick.instrument] = flow_obs
        self._latest_duration[tick.instrument] = dur_obs
        self._latest_impact[tick.instrument] = impact_obs
        self._latest_toxicity[tick.instrument] = tox_obs
        return flow_obs, dur_obs, impact_obs, tox_obs

    def process_order_book(
        self, snapshot: OrderBookSnapshot
    ) -> Tuple[OrderBookImbalanceObservation, SpreadLiquidityStressObservation]:
        """Process an order book snapshot through Module 3 and Module 4."""
        ob_engine, ls_engine = self._get_order_book_engines(snapshot.instrument)
        ob_obs = ob_engine.process_snapshot(snapshot)
        ls_obs = ls_engine.process_snapshot(snapshot)

        self._latest_ob[snapshot.instrument] = ob_obs
        self._latest_ls[snapshot.instrument] = ls_obs
        return ob_obs, ls_obs

    def fetch_live_bingx_trades(
        self,
        instrument: str,
        venue_symbol: str,
        limit: int = 50,
        persist: bool = True
    ) -> Tuple[
        Optional[TradeFlowObservation],
        Optional[TradeDurationObservation],
        Optional[PriceImpactObservation],
        Optional[ToxicityObservation],
    ]:
        """Fetch real recent trades from BingX and run Modules 1, 2, 5, and 6."""
        now = time.time()
        if instrument in self._last_fetch_ts and (now - self._last_fetch_ts[instrument]) < 2.0:
            return (
                self._latest_flow.get(instrument),
                self._latest_duration.get(instrument),
                self._latest_impact.get(instrument),
                self._latest_toxicity.get(instrument),
            )

        self._last_fetch_ts[instrument] = now
        url = f"https://open-api.bingx.com/openApi/swap/v2/quote/trades?symbol={venue_symbol}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-microstructure/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to fetch BingX trades for %s: %s", venue_symbol, e)
            return (
                self._latest_flow.get(instrument),
                self._latest_duration.get(instrument),
                self._latest_impact.get(instrument),
                self._latest_toxicity.get(instrument),
            )

        raw_trades = data.get("data", [])
        if not raw_trades:
            return (
                self._latest_flow.get(instrument),
                self._latest_duration.get(instrument),
                self._latest_impact.get(instrument),
                self._latest_toxicity.get(instrument),
            )

        raw_trades.sort(key=lambda x: int(x.get("time") or x.get("ts") or 0))

        flow_obs = None
        dur_obs = None
        impact_obs = None
        tox_obs = None
        now_ms = int(time.time() * 1000)

        for t in raw_trades:
            ts = int(t.get("time") or t.get("ts") or 0)
            price = float(t.get("price") or 0.0)
            qty = float(t.get("qty") or 0.0)
            trade_id = str(t.get("fillId") or t.get("id") or "")
            is_buyer_maker = t.get("isBuyerMaker")
            if is_buyer_maker is True:
                aggressor = "SELL"
            elif is_buyer_maker is False:
                aggressor = "BUY"
            else:
                aggressor = None

            tick = TradeTick(
                instrument=instrument,
                venue="BINGX",
                event_timestamp=ts,
                received_timestamp=now_ms,
                price=price,
                quantity=qty,
                aggressor_side=aggressor,
                trade_id=trade_id,
            )
            flow_obs, dur_obs, impact_obs, tox_obs = self.process_tick(tick)

        if persist and flow_obs and dur_obs and impact_obs and tox_obs:
            try:
                from control_plane import db
                db.persist_microstructure_flow(flow_obs.to_dict())
                db.persist_microstructure_duration(dur_obs.to_dict())
                db.persist_microstructure_price_impact(impact_obs.to_dict())
                db.persist_microstructure_toxicity(tox_obs.to_dict())
            except Exception as e:
                logger.error("Failed to persist microstructure trade observations: %s", e)

        return flow_obs, dur_obs, impact_obs, tox_obs

    def fetch_live_bingx_depth(
        self,
        instrument: str,
        venue_symbol: str,
        limit: int = 20,
        persist: bool = True
    ) -> Tuple[Optional[OrderBookImbalanceObservation], Optional[SpreadLiquidityStressObservation]]:
        """Fetch real depth snapshot from BingX and run Modules 3 and 4."""
        now = time.time()
        if instrument in self._last_depth_fetch_ts and (now - self._last_depth_fetch_ts[instrument]) < 2.0:
            return self._latest_ob.get(instrument), self._latest_ls.get(instrument)

        self._last_depth_fetch_ts[instrument] = now
        url = f"https://open-api.bingx.com/openApi/swap/v2/quote/depth?symbol={venue_symbol}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-microstructure/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to fetch BingX depth for %s: %s", venue_symbol, e)
            return self._latest_ob.get(instrument), self._latest_ls.get(instrument)

        depth_data = data.get("data", {})
        raw_bids = depth_data.get("bids", [])
        raw_asks = depth_data.get("asks", [])
        ts = int(depth_data.get("T") or depth_data.get("ts") or time.time() * 1000)
        now_ms = int(time.time() * 1000)

        bids = [OrderBookLevel(price=float(b[0]), quantity=float(b[1])) for b in raw_bids if len(b) >= 2]
        asks = [OrderBookLevel(price=float(a[0]), quantity=float(a[1])) for a in raw_asks if len(a) >= 2]

        snapshot = OrderBookSnapshot(
            instrument=instrument,
            venue="BINGX",
            event_timestamp=ts,
            received_timestamp=now_ms,
            bids=bids,
            asks=asks,
            sequence_num=depth_data.get("seq"),
        )
        ob_obs, ls_obs = self.process_order_book(snapshot)

        if persist and ob_obs and ls_obs:
            try:
                from control_plane import db
                db.persist_microstructure_order_book(ob_obs.to_dict())
                db.persist_microstructure_liquidity_stress(ls_obs.to_dict())
            except Exception as e:
                logger.error("Failed to persist order book observations: %s", e)

        return ob_obs, ls_obs

    def get_latest_observations(self, instrument: str) -> Dict[str, Any]:
        """Retrieve latest in-memory or persisted observations across Modules 1-6."""
        flow_obs = self._latest_flow.get(instrument)
        dur_obs = self._latest_duration.get(instrument)
        ob_obs = self._latest_ob.get(instrument)
        ls_obs = self._latest_ls.get(instrument)
        impact_obs = self._latest_impact.get(instrument)
        tox_obs = self._latest_toxicity.get(instrument)

        flow_dict = flow_obs.to_dict() if flow_obs else None
        dur_dict = dur_obs.to_dict() if dur_obs else None
        ob_dict = ob_obs.to_dict() if ob_obs else None
        ls_dict = ls_obs.to_dict() if ls_obs else None
        impact_dict = impact_obs.to_dict() if impact_obs else None
        tox_dict = tox_obs.to_dict() if tox_obs else None

        # Fallback to DB if missing in memory
        try:
            from control_plane import db
            if flow_dict is None:
                flow_dict = db.get_latest_microstructure_flow(instrument)
            if dur_dict is None:
                dur_dict = db.get_latest_microstructure_duration(instrument)
            if ob_dict is None:
                ob_dict = db.get_latest_microstructure_order_book(instrument)
            if ls_dict is None:
                ls_dict = db.get_latest_microstructure_liquidity_stress(instrument)
            if impact_dict is None:
                impact_dict = db.get_latest_microstructure_price_impact(instrument)
            if tox_dict is None:
                tox_dict = db.get_latest_microstructure_toxicity(instrument)
        except Exception:
            pass

        return {
            "instrument": instrument,
            "trade_flow": flow_dict,
            "trade_duration": dur_dict,
            "order_book": ob_dict,
            "liquidity_stress": ls_dict,
            "price_impact": impact_dict,
            "toxicity": tox_dict,
            "has_data": flow_dict is not None and dur_dict is not None
        }


