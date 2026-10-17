"""Ophelia Phase 6A: Microstructure Research Engine.

Modules:
- Module 1: Trade-Flow Innovation
- Module 2: Trade Duration / Arrival Pressure (Dufour-Engle Style)

Strictly RESEARCH ONLY. Zero direct execution authority.
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from models.microstructure import (
    AggressorSource,
    FlowDirection,
    FreshnessState,
    HasbrouckVarObservation,
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
    VecmObservation,
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


# =====================================================================
# PHASE 6D: HASBROUCK-STYLE VAR & VECM MATHEMATICAL UTILITIES
# =====================================================================

def _calculate_adf(series: Any, max_lags: int = 1) -> Tuple[float, float]:
    """Augmented Dickey-Fuller t-statistic with constant.
    Returns (t_stat, approximate_p_value).
    MacKinnon approximate critical values with constant:
    1%: -3.43, 5%: -2.86, 10%: -2.57
    """
    y = np.asarray(series, dtype=float)
    n = len(y)
    if n < 15:
        return 0.0, 1.0
    dy = np.diff(y)
    y_lag = y[:-1]

    t_len = len(dy) - max_lags
    if t_len < 5:
        return 0.0, 1.0

    y_dep = dy[max_lags:]
    X_mat = [np.ones(t_len), y_lag[max_lags:]]
    for lag in range(1, max_lags + 1):
        X_mat.append(dy[max_lags - lag : -lag])
    X = np.column_stack(X_mat)

    try:
        beta, residuals, rank, s = np.linalg.lstsq(X, y_dep, rcond=None)
        res = y_dep - X @ beta
        s2 = np.sum(res ** 2) / max(1, t_len - X.shape[1])
        cov = s2 * np.linalg.pinv(X.T @ X)
        gamma = beta[1]
        se_gamma = np.sqrt(max(1e-12, cov[1, 1]))
        t_stat = float(gamma / se_gamma)
        if t_stat < -3.43:
            p_val = 0.01
        elif t_stat < -2.86:
            p_val = 0.05
        elif t_stat < -2.57:
            p_val = 0.10
        else:
            p_val = 0.50
        return t_stat, p_val
    except Exception:
        return 0.0, 1.0


def _ljung_box(res_series: Any, m: int = 10) -> Tuple[float, float]:
    """Ljung-Box Q-statistic for residual autocorrelation at lag m.
    Returns (Q_stat, approximate_p_value).
    Approximate critical values for Chi-Square(df=10):
    1%: 23.21, 5%: 18.31, 10%: 15.99
    """
    e = np.asarray(res_series, dtype=float)
    e = e - np.mean(e)
    n = len(e)
    if n <= m + 2:
        return 0.0, 1.0
    denom = np.sum(e ** 2)
    if denom < 1e-12:
        return 0.0, 1.0
    q_stat = 0.0
    for k_lag in range(1, m + 1):
        gamma_k = np.sum(e[k_lag:] * e[:-k_lag])
        rho_k = gamma_k / denom
        q_stat += (rho_k ** 2) / (n - k_lag)
    q_stat *= n * (n + 2)
    if q_stat > 23.21:
        p_val = 0.001
    elif q_stat > 18.31:
        p_val = 0.04
    elif q_stat > 15.99:
        p_val = 0.09
    else:
        p_val = 0.50
    return float(q_stat), float(p_val)


class HasbrouckVarEngine:
    """Module 7: Hasbrouck-Style Bivariate Price Discovery VAR (Research Only).
    
    Estimates a bivariate VAR on [r_t, x_t]' where:
      r_t = price log return
      x_t = signed trade flow / order flow
      
    Cholesky identification ordering: [x_t, r_t]' (trade flow innovation affects
    returns contemporaneously, return innovation does not affect trade flow contemporaneously).
    Strictly RESEARCH ONLY. Zero execution authority.
    """

    def __init__(
        self,
        instrument: str = "BTC-USDT",
        max_candidate_lags: int = 5,
        min_sample_size: int = 60,
        calculation_window_ms: int = 300000,
        sampling_method: str = "EVENT_TIME",
    ):
        self.instrument = instrument.upper()
        self.max_candidate_lags = max_candidate_lags
        self.min_sample_size = min_sample_size
        self.calculation_window_ms = calculation_window_ms
        self.sampling_method = sampling_method
        
        # Buffer of raw ticks: list of (timestamp_ms, price, signed_volume)
        self._raw_ticks: collections.deque[Tuple[int, float, float]] = collections.deque(maxlen=2000)
        # Buffer of parsed observations: list of (timestamp_ms, r_t, x_t)
        self._observations: collections.deque[Tuple[int, float, float]] = collections.deque(maxlen=1000)
        self._last_price: Optional[float] = None
        self._last_fit_observation: Optional[HasbrouckVarObservation] = None

    def add_tick(self, tick: TradeTick) -> None:
        """Process incoming trade tick into Hasbrouck observation buffer."""
        vol = getattr(tick, "quantity", getattr(tick, "volume", 0.0))
        side = getattr(tick, "aggressor_side", None)
        if side in ("BUY", "BUYER", FlowDirection.BUY, 1, AggressorSource.DIRECT):
            signed_vol = float(vol)
        elif side in ("SELL", "SELLER", FlowDirection.SELL, -1):
            signed_vol = -float(vol)
        else:
            signed_vol = 0.0
        self.add_observation(tick.price, signed_vol, tick.event_timestamp)

    def add_observation(self, price: float, signed_flow: float, timestamp_ms: int) -> None:
        """Add an observation directly."""
        self._raw_ticks.append((timestamp_ms, float(price), float(signed_flow)))
        if self._last_price is not None and self._last_price > 0:
            # r_t = ln(P_t / P_{t-1})
            r_t = math.log(max(1e-12, price / self._last_price))
            # x_t = signed order flow (signed log volume or normalized flow)
            sign = 1.0 if signed_flow > 0 else (-1.0 if signed_flow < 0 else 0.0)
            x_primary = sign
            x_robust = sign * math.sqrt(abs(signed_flow))
            self._observations.append((timestamp_ms, r_t, x_primary, x_robust))
        self._last_price = float(price)

    def fit(self, timestamp_ms: Optional[int] = None) -> HasbrouckVarObservation:
        """Estimate the Hasbrouck-style VAR system deterministically."""
        now_ms = timestamp_ms or int(time.time() * 1000)
        
        # Filter observations strictly by window
        window_start = now_ms - self.calculation_window_ms
        window_obs = [obs for obs in self._observations if window_start <= obs[0] <= now_ms]
        
        n_obs = len(window_obs)
        prov = MicrostructureProvenance(
            instrument=self.instrument,
            venue="BINGX",
            event_timestamp=now_ms,
            received_timestamp=now_ms,
            feature_version="1.0.0",
            schema_version="v1",
            source_data_type="TRADE_TICKS" if self.sampling_method == "EVENT_TIME" else "TIME_BAR",
            sample_count=n_obs,
            quality_state=QualityState.VALID,
            freshness_state=FreshnessState.FRESH,
            missingness_state=MissingnessState.COMPLETE,
            calculation_window=self.calculation_window_ms,
            mode="RESEARCH"
        )
        
        # Gate 1: Insufficient Sample
        if n_obs < self.min_sample_size:
            run_id = hashlib.sha256(f"VAR_{self.instrument}_{now_ms}_{n_obs}_INSUFFICIENT".encode()).hexdigest()[:16]
            obs = HasbrouckVarObservation(
                provenance=prov,
                run_id=run_id,
                status="INSUFFICIENT_SAMPLE",
                sample_count=n_obs,
                window_start=window_start,
                window_end=now_ms,
                sampling_method=self.sampling_method,
                sampling_interval_ms=0,
                methodology_version="HASBROUCK_STYLE_V1.1",
                detail={"reason": f"Sample size {n_obs} < minimum {self.min_sample_size}"}
            )
            self._last_fit_observation = obs
            return obs

        # Extract returns and flow series (handling both 3-tuple legacy and 4-tuple robust)
        r_series = np.array([o[1] for o in window_obs], dtype=float)
        x_series = np.array([o[2] for o in window_obs], dtype=float)
        x_robust_series = np.array([
            o[3] if len(o) > 3 else (1.0 if o[2] > 0 else (-1.0 if o[2] < 0 else 0.0))
            for o in window_obs
        ], dtype=float)

        # Gate 2: Stationarity Test (ADF)
        adf_r_stat, adf_r_p = _calculate_adf(r_series, max_lags=1)
        adf_x_stat, adf_x_p = _calculate_adf(x_series, max_lags=1)

        # Null hypothesis of ADF is unit root. We must reject unit root (stat < -2.86 at 5% CV).
        if adf_r_stat > -2.86 or adf_x_stat > -2.86:
            run_id = hashlib.sha256(f"VAR_{self.instrument}_{now_ms}_{n_obs}_NON_STATIONARY".encode()).hexdigest()[:16]
            obs = HasbrouckVarObservation(
                provenance=prov,
                run_id=run_id,
                status="NON_STATIONARY",
                sample_count=n_obs,
                window_start=window_start,
                window_end=now_ms,
                sampling_method=self.sampling_method,
                sampling_interval_ms=0,
                methodology_version="HASBROUCK_STYLE_V1.1",
                diagnostics={
                    "adf_return_stat": round(adf_r_stat, 4),
                    "adf_return_p": round(adf_r_p, 4),
                    "adf_flow_stat": round(adf_x_stat, 4),
                    "adf_flow_p": round(adf_x_p, 4),
                    "critical_value_5pct": -2.86
                },
                detail={"reason": "Series non-stationary; transformation required"}
            )
            self._last_fit_observation = obs
            return obs

        # Gate 3: Deterministic Lag Selection (BIC)
        Y_all = np.column_stack([r_series, x_series])
        max_p = min(self.max_candidate_lags, max(1, (n_obs - 10) // 4))
        candidate_lags = list(range(1, max_p + 1))
        
        best_bic = float("inf")
        best_p = 1
        bic_scores = {}

        for p_cand in candidate_lags:
            T_eff = n_obs - p_cand
            Y_dep = Y_all[p_cand:]
            X_parts = [np.ones((T_eff, 1))]
            for lag in range(1, p_cand + 1):
                X_parts.append(Y_all[p_cand - lag : -lag])
            X_mat = np.hstack(X_parts)
            
            try:
                B_cand = np.linalg.pinv(X_mat) @ Y_dep
                res_cand = Y_dep - X_mat @ B_cand
                K_params = X_mat.shape[1]
                Sigma_cand = (res_cand.T @ res_cand) / max(1, T_eff - K_params)
                det_sigma = np.linalg.det(Sigma_cand)
                if det_sigma <= 0:
                    det_sigma = 1e-18
                k_eq = 2
                bic_val = math.log(det_sigma) + ((k_eq * k_eq * p_cand + k_eq) * math.log(T_eff)) / T_eff
                bic_scores[p_cand] = float(bic_val)
                if bic_val < best_bic:
                    best_bic = bic_val
                    best_p = p_cand
            except Exception:
                bic_scores[p_cand] = 999.0

        p = best_p

        # Fit VAR(p) with selected lag
        T_eff = n_obs - p
        Y_dep = Y_all[p:]
        X_parts = [np.ones((T_eff, 1))]
        for lag in range(1, p + 1):
            X_parts.append(Y_all[p - lag : -lag])
        X_mat = np.hstack(X_parts)

        B = np.linalg.pinv(X_mat) @ Y_dep
        residuals = Y_dep - X_mat @ B
        K_params = X_mat.shape[1]
        Sigma = (residuals.T @ residuals) / max(1, T_eff - K_params)

        # R^2 for return equation and flow equation
        SS_tot = np.sum((Y_dep - np.mean(Y_dep, axis=0)) ** 2, axis=0)
        SS_res = np.sum(residuals ** 2, axis=0)
        r2_vec = 1.0 - (SS_res / np.maximum(SS_tot, 1e-12))
        r2_r = float(r2_vec[0])
        r2_x = float(r2_vec[1])

        # Gate 4: Companion Matrix Stability
        k_vars = 2
        A_mats = []
        for lag in range(p):
            A_lag = B[1 + lag * k_vars : 1 + (lag + 1) * k_vars, :].T
            A_mats.append(A_lag)

        F_comp = np.zeros((k_vars * p, k_vars * p))
        for i, A in enumerate(A_mats):
            F_comp[:k_vars, i * k_vars : (i + 1) * k_vars] = A
        if p > 1:
            F_comp[k_vars:, : k_vars * (p - 1)] = np.eye(k_vars * (p - 1))

        eigvals = np.linalg.eigvals(F_comp)
        max_mod = float(np.max(np.abs(eigvals)))
        is_stable = bool(max_mod < 1.0)

        if not is_stable:
            run_id = hashlib.sha256(f"VAR_{self.instrument}_{now_ms}_{n_obs}_{p}_UNSTABLE".encode()).hexdigest()[:16]
            obs = HasbrouckVarObservation(
                provenance=prov,
                run_id=run_id,
                status="UNSTABLE_SYSTEM",
                selected_lag=p,
                lag_selection_method="BIC",
                candidate_lags=candidate_lags,
                sample_count=n_obs,
                window_start=window_start,
                window_end=now_ms,
                sampling_method=self.sampling_method,
                sampling_interval_ms=0,
                is_stable=False,
                max_eigenvalue_modulus=max_mod,
                methodology_version="HASBROUCK_STYLE_V1.1",
                diagnostics={
                    "eigenvalues": [round(float(np.abs(e)), 6) for e in eigvals],
                    "max_modulus": round(max_mod, 6),
                    "stability_criterion": "max_modulus < 1.0"
                },
                detail={"reason": f"Companion matrix eigenvalue modulus {max_mod:.4f} >= 1.0"}
            )
            self._last_fit_observation = obs
            return obs

        # Gate 5: Residual Diagnostics (Ljung-Box)
        lb_lag = min(10, max(2, T_eff // 5))
        lb_r_q, lb_r_p = _ljung_box(residuals[:, 0], m=lb_lag)
        lb_x_q, lb_x_p = _ljung_box(residuals[:, 1], m=lb_lag)
        
        quality_state = QualityState.VALID
        if lb_r_p < 0.01 or lb_x_p < 0.01:
            quality_state = QualityState.DEGRADED

        # Gate 6: Structural Impulse Response & Cumulative Impact H20 / Permanent Impact
        # Cholesky ordering [x_t, r_t]' -> flow first, return second
        Sigma_xf = np.array([
            [Sigma[1, 1], Sigma[1, 0]],
            [Sigma[0, 1], Sigma[0, 0]]
        ])
        try:
            P_xf = np.linalg.cholesky(Sigma_xf)
        except np.linalg.LinAlgError:
            P_xf = np.diag(np.sqrt(np.maximum(1e-12, np.diag(Sigma_xf))))

        # VMA representation Phi_s out to H_eval=50
        H_report = 20
        H_eval = 50
        Phi = [np.eye(k_vars)]
        for s in range(1, H_eval + 1):
            Phi_s = np.zeros((k_vars, k_vars))
            for j in range(1, min(s, p) + 1):
                Phi_s += Phi[s - j] @ A_mats[j - 1]
            Phi.append(Phi_s)

        # Flow shock: [P_xf[1, 0], P_xf[0, 0]] in (r, x) coordinates
        flow_shock_vec = np.array([P_xf[1, 0], P_xf[0, 0]])
        # Return shock: [P_xf[1, 1], 0] in (r, x) coordinates
        ret_shock_vec = np.array([P_xf[1, 1], 0.0])

        irf_return_from_flow = []
        irf_return_from_ret = []
        for s in range(H_eval + 1):
            resp_flow = Phi[s] @ flow_shock_vec
            resp_ret = Phi[s] @ ret_shock_vec
            irf_return_from_flow.append(float(resp_flow[0]))
            irf_return_from_ret.append(float(resp_ret[0]))

        # 20-step cumulative impulse response of trade flow on return
        cum_impact_H20 = float(np.sum(irf_return_from_flow[:H_report + 1]))

        # Convergence test for mathematical permanent impact:
        conv_tol = 1e-6
        tail_diffs = [abs(irf_return_from_flow[s]) for s in range(H_eval - 4, H_eval + 1)]
        is_converged = bool(
            max_mod < 0.999 and 
            all(d < conv_tol for d in tail_diffs) and 
            (max_mod ** H_eval) < 1e-4
        )
        if is_converged:
            permanent_impact = float(np.sum(irf_return_from_flow))
            convergence_status = "CONVERGED"
        else:
            permanent_impact = None
            convergence_status = "NOT_CONVERGED"

        # Variance decomposition of return at horizon H_report=20
        var_flow = float(np.sum(np.array(irf_return_from_flow[:H_report + 1]) ** 2))
        var_ret = float(np.sum(np.array(irf_return_from_ret[:H_report + 1]) ** 2))
        total_var = var_flow + var_ret
        variance_share_flow = float(var_flow / max(1e-12, total_var))

        # Hasbrouck Flow-Specification Robustness: secondary VAR on [r, x_robust]
        robust_diags = {}
        try:
            Y_rob = np.column_stack([r_series, x_robust_series])
            T_eff_rob = n_obs - p
            Y_dep_rob = Y_rob[p:]
            X_parts_rob = [np.ones((T_eff_rob, 1))]
            for lag in range(1, p + 1):
                X_parts_rob.append(Y_rob[p - lag : -lag])
            X_mat_rob = np.hstack(X_parts_rob)
            B_rob = np.linalg.pinv(X_mat_rob) @ Y_dep_rob
            res_rob = Y_dep_rob - X_mat_rob @ B_rob
            Sigma_rob = (res_rob.T @ res_rob) / max(1, T_eff_rob - X_mat_rob.shape[1])
            
            A_mats_rob = []
            for lag in range(p):
                A_mats_rob.append(B_rob[1 + lag * k_vars : 1 + (lag + 1) * k_vars, :].T)
            F_comp_rob = np.zeros((k_vars * p, k_vars * p))
            for i, A in enumerate(A_mats_rob):
                F_comp_rob[:k_vars, i * k_vars : (i + 1) * k_vars] = A
            if p > 1:
                F_comp_rob[k_vars:, : k_vars * (p - 1)] = np.eye(k_vars * (p - 1))
            max_mod_rob = float(np.max(np.abs(np.linalg.eigvals(F_comp_rob))))
            
            Sigma_xf_rob = np.array([
                [Sigma_rob[1, 1], Sigma_rob[1, 0]],
                [Sigma_rob[0, 1], Sigma_rob[0, 0]]
            ])
            try:
                P_xf_rob = np.linalg.cholesky(Sigma_xf_rob)
            except np.linalg.LinAlgError:
                P_xf_rob = np.diag(np.sqrt(np.maximum(1e-12, np.diag(Sigma_xf_rob))))
            flow_shock_rob = np.array([P_xf_rob[1, 0], P_xf_rob[0, 0]])
            
            Phi_rob = [np.eye(k_vars)]
            irf_rob = [float((Phi_rob[0] @ flow_shock_rob)[0])]
            for s in range(1, H_report + 1):
                Phi_s_rob = np.zeros((k_vars, k_vars))
                for j in range(1, min(s, p) + 1):
                    Phi_s_rob += Phi_rob[s - j] @ A_mats_rob[j - 1]
                Phi_rob.append(Phi_s_rob)
                irf_rob.append(float((Phi_s_rob @ flow_shock_rob)[0]))
            
            cum_impact_rob = float(np.sum(irf_rob))
            var_flow_rob = float(np.sum(np.array(irf_rob) ** 2))
            var_ret_rob = float(np.sum([(Phi_rob[s] @ np.array([P_xf_rob[1, 1], 0.0]))[0] ** 2 for s in range(H_report + 1)]))
            var_share_rob = float(var_flow_rob / max(1e-12, var_flow_rob + var_ret_rob))
            
            robust_diags = {
                "primary_x_definition": "SIGNED_INDICATOR",
                "robustness_x_definition": "SIGNED_SQRT_VOLUME",
                "robustness_status": "ESTIMATED",
                "robustness_cum_impact_H20": round(cum_impact_rob, 8),
                "robustness_variance_share": round(var_share_rob, 4),
                "robustness_max_modulus": round(max_mod_rob, 6),
                "is_stable": bool(max_mod_rob < 1.0),
                "coefficient_direction_concordant": bool(np.sign(cum_impact_H20) == np.sign(cum_impact_rob))
            }
        except Exception as e_rob:
            robust_diags = {
                "primary_x_definition": "SIGNED_INDICATOR",
                "robustness_x_definition": "SIGNED_SQRT_VOLUME",
                "robustness_status": f"FAILED: {e_rob}"
            }

        coeffs_dict = {
            "constant": [float(B[0, 0]), float(B[0, 1])],
            "lags": {}
        }
        for lag in range(1, p + 1):
            coeffs_dict["lags"][f"lag_{lag}"] = {
                "A": [[float(A_mats[lag - 1][i, j]) for j in range(k_vars)] for i in range(k_vars)]
            }

        run_id = hashlib.sha256(
            f"VAR_{self.instrument}_{now_ms}_{n_obs}_{p}_{round(cum_impact_H20, 6)}".encode()
        ).hexdigest()[:16]

        obs = HasbrouckVarObservation(
            provenance=MicrostructureProvenance(
                instrument=self.instrument,
                venue="BINGX",
                event_timestamp=now_ms,
                received_timestamp=now_ms,
                feature_version="1.0.0",
                schema_version="v1",
                source_data_type="TRADE_TICKS" if self.sampling_method == "EVENT_TIME" else "TIME_BAR",
                sample_count=n_obs,
                quality_state=quality_state,
                freshness_state=FreshnessState.FRESH,
                missingness_state=MissingnessState.COMPLETE,
                calculation_window=self.calculation_window_ms,
                mode="RESEARCH"
            ),
            run_id=run_id,
            status="VALID",
            selected_lag=p,
            lag_selection_method="BIC",
            candidate_lags=candidate_lags,
            sample_count=n_obs,
            window_start=window_start,
            window_end=now_ms,
            sampling_method=self.sampling_method,
            sampling_interval_ms=0,
            is_stable=True,
            max_eigenvalue_modulus=max_mod,
            cumulative_impact_H20=cum_impact_H20,
            permanent_impact=permanent_impact,
            convergence_status=convergence_status,
            convergence_tolerance=conv_tol,
            primary_x_definition="SIGNED_INDICATOR",
            robustness_x_definition="SIGNED_SQRT_VOLUME",
            variance_share_flow=variance_share_flow,
            coefficients=coeffs_dict,
            diagnostics={
                "bic_scores": {str(k): round(v, 4) for k, v in bic_scores.items()},
                "r2_return": round(r2_r, 4),
                "r2_flow": round(r2_x, 4),
                "residual_covariance": [[float(Sigma[i, j]) for j in range(k_vars)] for i in range(k_vars)],
                "ljung_box_return": {"q_stat": round(lb_r_q, 4), "p_val": round(lb_r_p, 4)},
                "ljung_box_flow": {"q_stat": round(lb_x_q, 4), "p_val": round(lb_x_p, 4)},
                "irf_return_from_flow": [round(v, 8) for v in irf_return_from_flow[:10]],
                "max_modulus": round(max_mod, 6),
                "cholesky_ordering": ["flow", "return"],
                "robustness": robust_diags
            },
            methodology_version="HASBROUCK_STYLE_V1.1",
            detail={
                "cumulative_impact_H20": round(cum_impact_H20, 8),
                "permanent_impact": round(permanent_impact, 8) if permanent_impact is not None else "NOT_CONVERGED",
                "flow_variance_share_pct": round(variance_share_flow * 100.0, 2),
                "selected_lag": p
            }
        )
        self._last_fit_observation = obs
        return obs


class VecmEngine:
    """Module 8: Bivariate Vector Error Correction Model (VECM) Research.
    
    Estimates cointegration and price discovery dynamics between paired instruments:
      Series 1 = Spot Price (e.g. BTC-USDT-SPOT)
      Series 2 = Perpetual Futures Price (e.g. BTC-USDT-PERP)
      
    Alignment: Deterministic NEAREST_PRIOR (no forward-fill lookahead).
    Cointegration Procedure: Johansen Case 3 (unrestricted constant).
    Gonzalo-Granger Price Discovery Shares: GG_1, GG_2.
    Secondary Robustness: Engle-Granger 2-step procedure.
    Strictly RESEARCH ONLY. Zero execution authority.
    """

    def __init__(
        self,
        series_1: str = "BTC-USDT-SPOT",
        series_2: str = "BTC-USDT-PERP",
        p_lags: int = 2,
        min_sample_size: int = 300,
        max_alignment_gap_ms: int = 5000,
        sampling_interval_ms: int = 1000,
        calculation_window_ms: int = 600000,
    ):
        self.series_1 = series_1.upper()
        self.series_2 = series_2.upper()
        self.p_lags = p_lags
        self.min_sample_size = min_sample_size
        self.max_alignment_gap_ms = max_alignment_gap_ms
        self.sampling_interval_ms = sampling_interval_ms
        self.calculation_window_ms = calculation_window_ms

        self._series1_buffer: collections.deque[Tuple[int, float]] = collections.deque(maxlen=2000)
        self._series2_buffer: collections.deque[Tuple[int, float]] = collections.deque(maxlen=2000)
        self._last_fit_observation: Optional[VecmObservation] = None

    def add_series_1_price(self, timestamp_ms: int, price: float) -> None:
        self._series1_buffer.append((timestamp_ms, float(price)))

    def add_series_2_price(self, timestamp_ms: int, price: float) -> None:
        self._series2_buffer.append((timestamp_ms, float(price)))

    def add_observation_pair(self, timestamp_ms: int, price_1: float, price_2: float) -> None:
        """Add directly aligned observation pair (useful for tests and synchronized feeds)."""
        self._series1_buffer.append((timestamp_ms, float(price_1)))
        self._series2_buffer.append((timestamp_ms, float(price_2)))

    def _align_series(self, window_start: int, window_end: int) -> Tuple[np.ndarray, int, int, float]:
        """Deterministic timestamp alignment via NEAREST_PRIOR."""
        s1 = [(ts, p) for ts, p in self._series1_buffer if window_start <= ts <= window_end]
        s2 = [(ts, p) for ts, p in self._series2_buffer if window_start <= ts <= window_end]

        if not s1 or not s2:
            return np.empty((0, 2)), 0, len(s1) + len(s2), 1.0

        s1.sort(key=lambda x: x[0])
        s2.sort(key=lambda x: x[0])

        aligned = []
        dropped = 0
        idx1 = 0
        len1 = len(s1)

        for ts2, p2 in s2:
            while idx1 + 1 < len1 and s1[idx1 + 1][0] <= ts2:
                idx1 += 1
            ts1, p1 = s1[idx1]
            if ts1 <= ts2 and (ts2 - ts1) <= self.max_alignment_gap_ms:
                aligned.append([p1, p2])
            else:
                dropped += 1

        aligned_arr = np.array(aligned, dtype=float)
        total = len(aligned) + dropped
        missingness = float(dropped / max(1, total))
        return aligned_arr, len(aligned), dropped, missingness

    def fit(self, timestamp_ms: Optional[int] = None) -> VecmObservation:
        """Estimate the VECM system deterministically."""
        now_ms = timestamp_ms or int(time.time() * 1000)
        calc_window_ms = self.calculation_window_ms
        window_start = now_ms - calc_window_ms

        aligned_arr, aligned_count, dropped_count, missingness = self._align_series(window_start, now_ms)
        
        prov = MicrostructureProvenance(
            instrument=self.series_2.replace("-PERP", ""),
            venue="BINGX",
            event_timestamp=now_ms,
            received_timestamp=now_ms,
            feature_version="1.0.0",
            schema_version="v1",
            source_data_type="PRICE_SERIES",
            sample_count=aligned_count,
            quality_state=QualityState.VALID,
            freshness_state=FreshnessState.FRESH,
            missingness_state=MissingnessState.COMPLETE if missingness < 0.10 else MissingnessState.PARTIAL,
            calculation_window=calc_window_ms,
            mode="RESEARCH"
        )

        sample_justification = (
            "Degrees of freedom asymptotic requirement for Johansen trace test "
            f"(K=2 variables, p={self.p_lags} lags, unrestricted constant requires T >= {self.min_sample_size} "
            "for reliable cointegration rank determination)"
        )

        # Gate 1: Insufficient Sample Governance
        if aligned_count < self.min_sample_size:
            run_id = hashlib.sha256(f"VECM_{self.series_1}_{self.series_2}_{now_ms}_{aligned_count}_INSUFFICIENT".encode()).hexdigest()[:16]
            obs = VecmObservation(
                provenance=prov,
                run_id=run_id,
                status="INSUFFICIENT_SAMPLE",
                series_1=self.series_1,
                series_2=self.series_2,
                sample_count=aligned_count,
                minimum_required_sample=self.min_sample_size,
                actual_sample=aligned_count,
                sample_status="INSUFFICIENT_SAMPLE",
                window_start=window_start,
                window_end=now_ms,
                sampling_interval_ms=self.sampling_interval_ms,
                alignment_method="NEAREST_PRIOR",
                methodology_version="VECM_STYLE_V1.1",
                justification=sample_justification,
                detail={
                    "reason": f"Aligned sample size {aligned_count} < minimum required {self.min_sample_size}",
                    "minimum_required_sample": self.min_sample_size,
                    "actual_sample": aligned_count,
                    "sample_status": "INSUFFICIENT_SAMPLE",
                    "dropped_observations": dropped_count,
                    "missingness_ratio": round(missingness, 4)
                }
            )
            self._last_fit_observation = obs
            return obs

        # Log prices: y1 = ln(Spot), y2 = ln(Perp)
        y_levels = np.log(np.maximum(1e-12, aligned_arr))
        y1 = y_levels[:, 0]
        y2 = y_levels[:, 1]
        dy1 = np.diff(y1)
        dy2 = np.diff(y2)

        # Gate 2: Unit Root Tests (Integration Order Verification)
        adf_y1_stat, adf_y1_p = _calculate_adf(y1, max_lags=1)
        adf_y2_stat, adf_y2_p = _calculate_adf(y2, max_lags=1)
        adf_dy1_stat, adf_dy1_p = _calculate_adf(dy1, max_lags=1)
        adf_dy2_stat, adf_dy2_p = _calculate_adf(dy2, max_lags=1)

        is_i1 = (adf_y1_stat > -2.86 and adf_y2_stat > -2.86 and adf_dy1_stat < -2.86 and adf_dy2_stat < -2.86)
        if not is_i1:
            run_id = hashlib.sha256(f"VECM_{self.series_1}_{self.series_2}_{now_ms}_{aligned_count}_NOT_I1".encode()).hexdigest()[:16]
            obs = VecmObservation(
                provenance=prov,
                run_id=run_id,
                status="NOT_I1",
                series_1=self.series_1,
                series_2=self.series_2,
                sample_count=aligned_count,
                minimum_required_sample=self.min_sample_size,
                actual_sample=aligned_count,
                sample_status="VALID",
                window_start=window_start,
                window_end=now_ms,
                sampling_interval_ms=self.sampling_interval_ms,
                alignment_method="NEAREST_PRIOR",
                methodology_version="VECM_STYLE_V1.1",
                justification=sample_justification,
                diagnostics={
                    "level_adf_series_1": {"stat": round(adf_y1_stat, 4), "p_val": round(adf_y1_p, 4)},
                    "level_adf_series_2": {"stat": round(adf_y2_stat, 4), "p_val": round(adf_y2_p, 4)},
                    "diff_adf_series_1": {"stat": round(adf_dy1_stat, 4), "p_val": round(adf_dy1_p, 4)},
                    "diff_adf_series_2": {"stat": round(adf_dy2_stat, 4), "p_val": round(adf_dy2_p, 4)},
                    "critical_value_5pct": -2.86
                },
                detail={"reason": "Series do not satisfy I(1) integration order prerequisite"}
            )
            self._last_fit_observation = obs
            return obs

        # Gate 3: Johansen Cointegration Procedure (Case 3: Unrestricted Constant)
        p = max(1, self.p_lags)
        dY = np.diff(y_levels, axis=0)
        Y_lag1 = y_levels[:-1, :]
        p_diff = p - 1
        T = len(dY) - p_diff

        dY_curr = dY[p_diff:]
        Y_lag1_curr = Y_lag1[p_diff:]

        Z_parts = [np.ones((T, 1))]
        for lag in range(1, p_diff + 1):
            Z_parts.append(dY[p_diff - lag : -lag])
        Z = np.hstack(Z_parts)

        beta_0 = np.linalg.pinv(Z) @ dY_curr
        R0 = dY_curr - Z @ beta_0
        beta_1 = np.linalg.pinv(Z) @ Y_lag1_curr
        R1 = Y_lag1_curr - Z @ beta_1

        S00 = (R0.T @ R0) / T
        S01 = (R0.T @ R1) / T
        S10 = S01.T
        S11 = (R1.T @ R1) / T

        inv_S00 = np.linalg.pinv(S00)
        inv_S11 = np.linalg.pinv(S11)
        M_mat = inv_S11 @ S10 @ inv_S00 @ S01

        eigvals, eigvecs = np.linalg.eig(M_mat)
        sort_idx = np.argsort(np.real(eigvals))[::-1]
        lam = np.real(eigvals)[sort_idx]
        V_mat = np.real(eigvecs)[:, sort_idx]
        lam = np.clip(lam, 0.0, 0.9999)

        trace_0 = float(-T * (np.log(1.0 - lam[0]) + np.log(1.0 - lam[1])))
        trace_1 = float(-T * np.log(1.0 - lam[1]))
        max_eigen_0 = float(-T * np.log(1.0 - lam[0]))
        max_eigen_1 = float(-T * np.log(1.0 - lam[1]))

        cv_trace_0 = 15.49
        cv_trace_1 = 3.84

        if trace_0 <= cv_trace_0:
            rank = 0
        else:
            rank = 1

        if rank == 0:
            run_id = hashlib.sha256(f"VECM_{self.series_1}_{self.series_2}_{now_ms}_{aligned_count}_NO_COINT".encode()).hexdigest()[:16]
            obs = VecmObservation(
                provenance=prov,
                run_id=run_id,
                status="NO_COINTEGRATION",
                series_1=self.series_1,
                series_2=self.series_2,
                sample_count=aligned_count,
                minimum_required_sample=self.min_sample_size,
                actual_sample=aligned_count,
                sample_status="VALID",
                window_start=window_start,
                window_end=now_ms,
                sampling_interval_ms=self.sampling_interval_ms,
                alignment_method="NEAREST_PRIOR",
                selected_lag=p,
                cointegration_rank=0,
                trace_stat=trace_0,
                max_eigen_stat=max_eigen_0,
                methodology_version="VECM_STYLE_V1.1",
                justification=sample_justification,
                diagnostics={
                    "trace_stat_r0": round(trace_0, 4),
                    "trace_cv_5pct": cv_trace_0,
                    "max_eigen_stat_r0": round(max_eigen_0, 4),
                    "max_eigen_cv_5pct": 14.26,
                    "decision": "Fail to reject r=0 (no cointegration)"
                },
                detail={"reason": f"Trace statistic {trace_0:.2f} <= critical value {cv_trace_0:.2f}"}
            )
            self._last_fit_observation = obs
            return obs

        # Cointegrating vector beta = [1, -beta_2]'
        v1 = V_mat[:, 0]
        if abs(v1[0]) > 1e-12:
            beta = v1 / v1[0]
        else:
            beta = v1
        beta_2 = float(beta[1])

        # Adjustment speed alpha = [alpha_1, alpha_2]'
        denom = beta.T @ S11 @ beta
        if abs(denom) > 1e-12:
            alpha = (S01 @ beta) / denom
        else:
            alpha = np.zeros(2)
        alpha_1 = float(alpha[0])
        alpha_2 = float(alpha[1])

        # Gonzalo-Granger price discovery shares governance
        denom_gg = alpha_2 - alpha_1
        if abs(denom_gg) > 1e-8:
            gg_1_raw = float(alpha_2 / denom_gg)
            gg_2_raw = float(-alpha_1 / denom_gg)
        else:
            gg_1_raw = 0.5
            gg_2_raw = 0.5

        # Check bounds [0, 1] without clipping
        gg_in_range = bool(0.0 <= gg_1_raw <= 1.0 and 0.0 <= gg_2_raw <= 1.0)
        gg_1 = gg_1_raw if gg_in_range else None
        gg_2 = gg_2_raw if gg_in_range else None

        # Bounded speed of adjustment share: |alpha_2| / (|alpha_1| + |alpha_2|)
        abs_a1 = abs(alpha_1)
        abs_a2 = abs(alpha_2)
        sum_abs_a = abs_a1 + abs_a2
        if sum_abs_a > 1e-12:
            bounded_speed_1 = float(abs_a2 / sum_abs_a)
            bounded_speed_2 = float(abs_a1 / sum_abs_a)
        else:
            bounded_speed_1 = 0.5
            bounded_speed_2 = 0.5

        # Gate 4: Stability & Contracting Dynamics
        is_contracting = (alpha_1 <= 0.05 or alpha_2 >= -0.05) and (alpha_1 - alpha_2 < 0.10)
        is_stable = is_contracting

        if not is_stable:
            run_id = hashlib.sha256(f"VECM_{self.series_1}_{self.series_2}_{now_ms}_{aligned_count}_UNSTABLE".encode()).hexdigest()[:16]
            obs = VecmObservation(
                provenance=prov,
                run_id=run_id,
                status="UNSTABLE_SYSTEM",
                series_1=self.series_1,
                series_2=self.series_2,
                sample_count=aligned_count,
                minimum_required_sample=self.min_sample_size,
                actual_sample=aligned_count,
                sample_status="VALID",
                window_start=window_start,
                window_end=now_ms,
                sampling_interval_ms=self.sampling_interval_ms,
                alignment_method="NEAREST_PRIOR",
                selected_lag=p,
                cointegration_rank=rank,
                trace_stat=trace_0,
                max_eigen_stat=max_eigen_0,
                beta_coeff=beta_2,
                alpha_1=alpha_1,
                alpha_2=alpha_2,
                gg_share_1_raw=gg_1_raw,
                gg_share_2_raw=gg_2_raw,
                gg_share_in_range=gg_in_range,
                gg_share_1=gg_1,
                gg_share_2=gg_2,
                bounded_speed_share_1=bounded_speed_1,
                bounded_speed_share_2=bounded_speed_2,
                is_stable=False,
                methodology_version="VECM_STYLE_V1.1",
                justification=sample_justification,
                diagnostics={
                    "alpha_1": round(alpha_1, 6),
                    "alpha_2": round(alpha_2, 6),
                    "contracting_criterion": "alpha_1 <= 0.05 or alpha_2 >= -0.05",
                    "decision": "System exhibits explosive non-contracting basis dynamics"
                },
                detail={"reason": "Non-contracting adjustment speeds; unstable VECM"}
            )
            self._last_fit_observation = obs
            return obs

        # Gate 5: Secondary Robustness Check (Engle-Granger 2-step)
        X_eg = np.column_stack([np.ones(len(y2)), y2])
        try:
            beta_eg_all = np.linalg.pinv(X_eg) @ y1
            res_eg = y1 - X_eg @ beta_eg_all
            stat_eg, p_eg = _calculate_adf(res_eg, max_lags=1)
            eg_cointegrated = bool(stat_eg < -3.37)
        except Exception:
            stat_eg, p_eg, eg_cointegrated = 0.0, 1.0, False

        run_id = hashlib.sha256(
            f"VECM_{self.series_1}_{self.series_2}_{now_ms}_{aligned_count}_{rank}_{round(beta_2, 4)}_{round(alpha_1, 4)}".encode()
        ).hexdigest()[:16]

        obs = VecmObservation(
            provenance=prov,
            run_id=run_id,
            status="VALID",
            series_1=self.series_1,
            series_2=self.series_2,
            sample_count=aligned_count,
            minimum_required_sample=self.min_sample_size,
            actual_sample=aligned_count,
            sample_status="VALID",
            window_start=window_start,
            window_end=now_ms,
            sampling_interval_ms=self.sampling_interval_ms,
            alignment_method="NEAREST_PRIOR",
            selected_lag=p,
            cointegration_rank=rank,
            trace_stat=trace_0,
            max_eigen_stat=max_eigen_0,
            beta_coeff=beta_2,
            alpha_1=alpha_1,
            alpha_2=alpha_2,
            gg_share_1_raw=gg_1_raw,
            gg_share_2_raw=gg_2_raw,
            gg_share_in_range=gg_in_range,
            gg_share_1=gg_1,
            gg_share_2=gg_2,
            bounded_speed_share_1=bounded_speed_1,
            bounded_speed_share_2=bounded_speed_2,
            is_stable=True,
            diagnostics={
                "johansen": {
                    "trace_stat_r0": round(trace_0, 4),
                    "trace_cv_5pct": cv_trace_0,
                    "trace_stat_r1": round(trace_1, 4),
                    "trace_cv_r1_5pct": cv_trace_1,
                    "max_eigen_stat_r0": round(max_eigen_0, 4),
                    "cointegrating_vector": [1.0, round(beta_2, 6)],
                    "eigenvalues": [round(float(l), 6) for l in lam]
                },
                "gonzalo_granger": {
                    "gg_share_1_raw": round(gg_1_raw, 4),
                    "gg_share_2_raw": round(gg_2_raw, 4),
                    "gg_share_in_range": gg_in_range,
                    "gg_share_1": round(gg_1, 4) if gg_1 is not None else None,
                    "gg_share_2": round(gg_2, 4) if gg_2 is not None else None,
                    "bounded_speed_share_1": round(bounded_speed_1, 4),
                    "bounded_speed_share_2": round(bounded_speed_2, 4),
                    "denominator": round(denom_gg, 6),
                    "interpretation": "Standard GG discovery share valid" if gg_in_range else "GG shares out of [0, 1] bounds due to identical alpha signs; bounded_speed_share provides monotonic adjustment attribution"
                },
                "engle_granger_check": {
                    "t_statistic": round(stat_eg, 4),
                    "critical_value_5pct": -3.37,
                    "p_value": round(p_eg, 4),
                    "cointegration_confirmed": eg_cointegrated
                },
                "alignment": {
                    "aligned_observations": aligned_count,
                    "dropped_observations": dropped_count,
                    "missingness_ratio": round(missingness, 4),
                    "max_gap_ms": self.max_alignment_gap_ms
                }
            },
            methodology_version="VECM_STYLE_V1.1",
            justification=sample_justification,
            detail={
                "beta_normalized": f"[1.0, {round(beta_2, 4)}]",
                "adjustment_speeds": f"alpha_spot={round(alpha_1, 4)}, alpha_perp={round(alpha_2, 4)}",
                "gg_share_1_raw": round(gg_1_raw, 4),
                "gg_share_2_raw": round(gg_2_raw, 4),
                "gg_share_in_range": gg_in_range,
                "bounded_speed_shares": f"spot={round(bounded_speed_1 * 100, 1)}%, perp={round(bounded_speed_2 * 100, 1)}%"
            }
        )
        self._last_fit_observation = obs
        return obs


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
        self._var_engines: Dict[str, HasbrouckVarEngine] = {}
        self._vecm_engines: Dict[str, VecmEngine] = {}

        self._latest_flow: Dict[str, TradeFlowObservation] = {}
        self._latest_duration: Dict[str, TradeDurationObservation] = {}
        self._latest_ob: Dict[str, OrderBookImbalanceObservation] = {}
        self._latest_ls: Dict[str, SpreadLiquidityStressObservation] = {}
        self._latest_impact: Dict[str, PriceImpactObservation] = {}
        self._latest_toxicity: Dict[str, ToxicityObservation] = {}
        self._latest_var: Dict[str, HasbrouckVarObservation] = {}
        self._latest_vecm: Dict[str, VecmObservation] = {}

        self._last_fetch_ts: Dict[str, float] = {}
        self._last_depth_fetch_ts: Dict[str, float] = {}
        self._last_spot_perp_fetch_ts: Dict[str, float] = {}

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

    def _get_var_engine(self, instrument: str) -> HasbrouckVarEngine:
        inst = instrument.upper()
        if inst not in self._var_engines:
            self._var_engines[inst] = HasbrouckVarEngine(instrument=inst)
        return self._var_engines[inst]

    def _get_vecm_engine(self, series_1: str = "BTC-USDT-SPOT", series_2: str = "BTC-USDT-PERP") -> VecmEngine:
        key = f"{series_1.upper()}_{series_2.upper()}"
        if key not in self._vecm_engines:
            self._vecm_engines[key] = VecmEngine(series_1=series_1, series_2=series_2)
        return self._vecm_engines[key]

    def _get_order_book_engines(self, instrument: str) -> Tuple[OrderBookImbalanceEngine, SpreadLiquidityStressEngine]:
        inst = instrument.upper()
        if inst not in self._ob_engines:
            self._ob_engines[inst] = OrderBookImbalanceEngine(instrument=inst)
            self._ls_engines[inst] = SpreadLiquidityStressEngine(instrument=inst)
        return self._ob_engines[inst], self._ls_engines[inst]

    def process_tick(
        self, tick: TradeTick
    ) -> Tuple[TradeFlowObservation, TradeDurationObservation, PriceImpactObservation, ToxicityObservation]:
        """Process an individual tick through Modules 1, 2, 5, 6, 7 (VAR), and 8 (VECM)."""
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

        # Ingest into Phase 6D Hasbrouck VAR Engine
        var_engine = self._get_var_engine(tick.instrument)
        var_engine.add_tick(tick)

        # Ingest into Phase 6D VECM Engine (Perp series)
        base_inst = tick.instrument.upper().replace("-PERP", "")
        vecm_engine = self._get_vecm_engine(f"{base_inst}-SPOT", f"{base_inst}-PERP")
        vecm_engine.add_series_2_price(tick.event_timestamp, tick.price)

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

    def run_hasbrouck_fit(self, instrument: str = "BTC-USDT", persist: bool = True) -> HasbrouckVarObservation:
        """Run Hasbrouck VAR fit for instrument."""
        inst = instrument.upper()
        engine = self._get_var_engine(inst)
        obs = engine.fit()
        self._latest_var[inst] = obs
        if persist and obs:
            try:
                from control_plane import db
                db.persist_microstructure_var(obs.to_dict())
            except Exception as e:
                logger.error("Failed to persist Hasbrouck VAR observation: %s", e)
        return obs

    def run_vecm_fit(
        self,
        series_1: str = "BTC-USDT-SPOT",
        series_2: str = "BTC-USDT-PERP",
        persist: bool = True
    ) -> VecmObservation:
        """Run VECM fit for paired series."""
        engine = self._get_vecm_engine(series_1, series_2)
        obs = engine.fit()
        key = f"{series_1.upper()}_{series_2.upper()}"
        self._latest_vecm[key] = obs
        if persist and obs:
            try:
                from control_plane import db
                db.persist_microstructure_vecm(obs.to_dict())
            except Exception as e:
                logger.error("Failed to persist VECM observation: %s", e)
        return obs

    def fetch_live_bingx_spot_and_perp(
        self,
        instrument: str = "BTC-USDT",
        persist: bool = True
    ) -> Tuple[Optional[HasbrouckVarObservation], Optional[VecmObservation]]:
        """Fetch live BingX Spot and Perp trades, feed VAR and VECM, and run fits."""
        now = time.time()
        inst = instrument.upper()
        if inst in self._last_spot_perp_fetch_ts and (now - self._last_spot_perp_fetch_ts[inst]) < 2.0:
            var_cached = self._latest_var.get(inst)
            vecm_cached = self._latest_vecm.get(f"{inst}-SPOT_{inst}-PERP")
            return var_cached, vecm_cached

        self._last_spot_perp_fetch_ts[inst] = now
        spot_sym = inst
        perp_sym = inst
        
        vecm_engine = self._get_vecm_engine(f"{inst}-SPOT", f"{inst}-PERP")
        var_engine = self._get_var_engine(inst)

        perp_url = f"https://open-api.bingx.com/openApi/swap/v2/quote/trades?symbol={perp_sym}&limit=100"
        spot_url = f"https://open-api.bingx.com/openApi/spot/v1/market/trades?symbol={spot_sym}&limit=100"

        try:
            req_perp = urllib.request.Request(perp_url, headers={"User-Agent": "ophelia-microstructure/1.0"})
            with urllib.request.urlopen(req_perp, timeout=5) as resp:
                perp_data = json.loads(resp.read().decode("utf-8")).get("data", [])
        except Exception as e:
            logger.warning("Failed to fetch BingX perp trades for %s: %s", perp_sym, e)
            perp_data = []

        try:
            req_spot = urllib.request.Request(spot_url, headers={"User-Agent": "ophelia-microstructure/1.0"})
            with urllib.request.urlopen(req_spot, timeout=5) as resp:
                spot_data = json.loads(resp.read().decode("utf-8")).get("data", [])
        except Exception as e:
            logger.warning("Failed to fetch BingX spot trades for %s: %s", spot_sym, e)
            spot_data = []

        if isinstance(perp_data, list):
            perp_data.sort(key=lambda t: int(t.get("time") or t.get("T") or 0))
            for t in perp_data:
                ts = int(t.get("time") or t.get("T") or 0)
                p = float(t.get("price") or t.get("p") or 0.0)
                v = float(t.get("qty") or t.get("v") or 0.0)
                is_buyer_maker = t.get("isBuyerMaker")
                aggressor = "SELL" if is_buyer_maker else "BUY"
                tick = TradeTick(
                    instrument=inst,
                    venue="BINGX",
                    event_timestamp=ts,
                    received_timestamp=int(time.time() * 1000),
                    price=p,
                    quantity=v,
                    aggressor_side=aggressor
                )
                var_engine.add_tick(tick)
                vecm_engine.add_series_2_price(ts, p)

        if isinstance(spot_data, list):
            spot_data.sort(key=lambda t: int(t.get("time") or t.get("T") or 0))
            for t in spot_data:
                ts = int(t.get("time") or t.get("T") or 0)
                p = float(t.get("price") or t.get("p") or 0.0)
                vecm_engine.add_series_1_price(ts, p)

        var_obs = self.run_hasbrouck_fit(inst, persist=persist)
        vecm_obs = self.run_vecm_fit(f"{inst}-SPOT", f"{inst}-PERP", persist=persist)
        return var_obs, vecm_obs

    def get_latest_observations(self, instrument: str) -> Dict[str, Any]:
        """Retrieve latest in-memory or persisted observations across Modules 1-8."""
        flow_obs = self._latest_flow.get(instrument)
        dur_obs = self._latest_duration.get(instrument)
        ob_obs = self._latest_ob.get(instrument)
        ls_obs = self._latest_ls.get(instrument)
        impact_obs = self._latest_impact.get(instrument)
        tox_obs = self._latest_toxicity.get(instrument)
        var_obs = self._latest_var.get(instrument)
        vecm_key = f"{instrument.upper()}-SPOT_{instrument.upper()}-PERP"
        vecm_obs = self._latest_vecm.get(vecm_key) or self._latest_vecm.get("BTC-USDT-SPOT_BTC-USDT-PERP")

        flow_dict = flow_obs.to_dict() if flow_obs else None
        dur_dict = dur_obs.to_dict() if dur_obs else None
        ob_dict = ob_obs.to_dict() if ob_obs else None
        ls_dict = ls_obs.to_dict() if ls_obs else None
        impact_dict = impact_obs.to_dict() if impact_obs else None
        tox_dict = tox_obs.to_dict() if tox_obs else None
        var_dict = var_obs.to_dict() if var_obs else None
        vecm_dict = vecm_obs.to_dict() if vecm_obs else None

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
            if var_dict is None:
                var_dict = db.get_latest_microstructure_var(instrument)
            if vecm_dict is None:
                vecm_dict = db.get_latest_microstructure_vecm(f"{instrument.upper()}-SPOT", f"{instrument.upper()}-PERP")
                if vecm_dict is None:
                    vecm_dict = db.get_latest_microstructure_vecm("BTC-USDT-SPOT", "BTC-USDT-PERP")
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
            "hasbrouck": var_dict,
            "vecm": vecm_dict,
            "has_data": flow_dict is not None and dur_dict is not None
        }


