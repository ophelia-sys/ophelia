"""Binance / BingX Cross-Venue Basis Engine and Execution Translation Subsystem.

Layer: control_plane/cross_venue_basis.py
Contract:
- Authoritative calculation of basis divergence between Primary Intelligence (Binance) and Execution (BingX).
- Metrics: basis_abs, basis_pct, basis_zscore, basis_velocity, timestamp_delta_ms, quote_age_ms.
- Explicit states: ALIGNED, NORMAL_BASIS, ELEVATED_BASIS, DISLOCATED, STALE, NOT_AVAILABLE, DEGRADED.
- Strict preflight gate: Execution cannot proceed if basis is DISLOCATED or quote is STALE.
- Signal translation: Maps Binance structural signal prices to BingX contract tick/lot/notional precision.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

from models.instrument import CanonicalInstrument

logger = logging.getLogger("ophelia.cross_venue_basis")

BASIS_ENGINE_VERSION = "CROSS_VENUE_BASIS_V1"
STALE_QUOTE_THRESHOLD_MS = 10_000  # 10 seconds
DISLOCATED_BASIS_PCT = 0.50        # 50 bps divergence
ELEVATED_BASIS_PCT = 0.20          # 20 bps divergence
NORMAL_BASIS_PCT = 0.05            # 5 bps divergence


@dataclass(slots=True)
class CrossVenueBasisSnapshot:
    symbol: str
    canonical_instrument_id: str
    binance_price: float
    bingx_price: float
    basis_abs: float
    basis_pct: float
    basis_zscore: Optional[float]
    basis_velocity: float
    binance_timestamp_ms: int
    bingx_timestamp_ms: int
    timestamp_delta_ms: int
    binance_data_age_ms: int
    bingx_data_age_ms: int
    execution_spread: float
    estimated_slippage_pct: float
    state: str
    version: str = BASIS_ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CrossVenueBasisEngine:
    """Thread-safe engine for tracking cross-venue basis metrics and translating signals."""

    _instance: Optional["CrossVenueBasisEngine"] = None
    _lock = threading.Lock()

    def __init__(self, history_size: int = 120):
        self._history_size = history_size
        self._state_lock = threading.Lock()
        # symbol -> deque of (timestamp_ms, basis_pct)
        self._history: Dict[str, Deque[Tuple[int, float]]] = {}
        # symbol -> latest snapshot
        self._latest_snapshots: Dict[str, CrossVenueBasisSnapshot] = {}

    @classmethod
    def get_instance(cls) -> "CrossVenueBasisEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def compute_basis(
        self,
        symbol: str,
        binance_price: float,
        bingx_price: float,
        binance_ts_ms: int,
        bingx_ts_ms: int,
        canonical_id: Optional[str] = None,
        bingx_bid: Optional[float] = None,
        bingx_ask: Optional[float] = None,
        now_ms: Optional[int] = None
    ) -> CrossVenueBasisSnapshot:
        """Compute real-time basis metrics between Binance and BingX."""
        now = now_ms or int(time.time() * 1000)
        clean_symbol = symbol.upper()
        cid = canonical_id or f"CRYPTO:{clean_symbol}"

        # 1. Check data availability
        if binance_price <= 0 or bingx_price <= 0:
            return CrossVenueBasisSnapshot(
                symbol=clean_symbol,
                canonical_instrument_id=cid,
                binance_price=binance_price,
                bingx_price=bingx_price,
                basis_abs=0.0,
                basis_pct=0.0,
                basis_zscore=None,
                basis_velocity=0.0,
                binance_timestamp_ms=binance_ts_ms,
                bingx_timestamp_ms=bingx_ts_ms,
                timestamp_delta_ms=abs(binance_ts_ms - bingx_ts_ms) if binance_ts_ms and bingx_ts_ms else 0,
                binance_data_age_ms=max(0, now - binance_ts_ms) if binance_ts_ms else 999999,
                bingx_data_age_ms=max(0, now - bingx_ts_ms) if bingx_ts_ms else 999999,
                execution_spread=0.0,
                estimated_slippage_pct=0.0,
                state="NOT_AVAILABLE"
            )

        # 2. Compute absolute and percentage basis
        basis_abs = round(bingx_price - binance_price, 4)
        basis_pct = round((basis_abs / binance_price) * 100.0, 4)
        ts_delta = abs(binance_ts_ms - bingx_ts_ms)
        bn_age = max(0, now - binance_ts_ms)
        bx_age = max(0, now - bingx_ts_ms)

        # 3. Execution spread and slippage
        spread = 0.0
        slippage_pct = 0.02  # base default 2 bps
        if bingx_bid is not None and bingx_ask is not None and bingx_ask >= bingx_bid > 0:
            spread = round(bingx_ask - bingx_bid, 4)
            slippage_pct = round((spread / bingx_price) * 100.0 / 2.0, 4)

        # 4. Rolling z-score & velocity
        with self._state_lock:
            if clean_symbol not in self._history:
                self._history[clean_symbol] = deque(maxlen=self._history_size)
            dq = self._history[clean_symbol]

            velocity = 0.0
            if dq:
                prev_ts, prev_pct = dq[-1]
                dt_sec = max(0.1, (now - prev_ts) / 1000.0)
                velocity = round((basis_pct - prev_pct) / dt_sec, 4)

            dq.append((now, basis_pct))

            zscore: Optional[float] = None
            if len(dq) >= 10:
                values = [p for _, p in dq]
                mean_p = sum(values) / len(values)
                var_p = sum((p - mean_p) ** 2 for p in values) / len(values)
                std_p = math.sqrt(var_p)
                if std_p > 1e-6:
                    zscore = round(max(-5.0, min(5.0, (basis_pct - mean_p) / std_p)), 2)

        # 5. Determine State Machine status
        abs_pct = abs(basis_pct)
        if bn_age > STALE_QUOTE_THRESHOLD_MS or bx_age > STALE_QUOTE_THRESHOLD_MS:
            state = "STALE"
        elif abs_pct > DISLOCATED_BASIS_PCT:
            state = "DISLOCATED"
        elif abs_pct > ELEVATED_BASIS_PCT:
            state = "ELEVATED_BASIS"
        elif abs_pct > NORMAL_BASIS_PCT:
            state = "NORMAL_BASIS"
        else:
            state = "ALIGNED"

        snap = CrossVenueBasisSnapshot(
            symbol=clean_symbol,
            canonical_instrument_id=cid,
            binance_price=binance_price,
            bingx_price=bingx_price,
            basis_abs=basis_abs,
            basis_pct=basis_pct,
            basis_zscore=zscore,
            basis_velocity=velocity,
            binance_timestamp_ms=binance_ts_ms,
            bingx_timestamp_ms=bingx_ts_ms,
            timestamp_delta_ms=ts_delta,
            binance_data_age_ms=bn_age,
            bingx_data_age_ms=bx_age,
            execution_spread=spread,
            estimated_slippage_pct=slippage_pct,
            state=state
        )

        with self._state_lock:
            self._latest_snapshots[clean_symbol] = snap

        return snap

    def get_latest_snapshot(self, symbol: str) -> Optional[CrossVenueBasisSnapshot]:
        with self._state_lock:
            return self._latest_snapshots.get(symbol.upper())

    def get_basis_percentile_and_max(self, symbol: str) -> Dict[str, float]:
        """Compute p99, max, and mean basis from history strictly keeping p99 separate from max."""
        with self._state_lock:
            dq = self._history.get(symbol.upper())
            if not dq:
                return {"p99": 0.0, "max": 0.0, "mean": 0.0}
            vals = [abs(p) for _, p in dq]
            p99 = float(np.percentile(vals, 99))
            max_val = float(np.max(vals))
            mean_val = float(np.mean(vals))
            return {"p99": round(p99, 4), "max": round(max_val, 4), "mean": round(mean_val, 4)}

    def translate_signal_to_execution(
        self,
        signal_price: float,
        canonical_inst: CanonicalInstrument,
        intended_quantity: float,
        side: str = "BUY"
    ) -> Dict[str, Any]:
        """Translate a Binance signal price and size to BingX execution constraints.
        
        Returns a dictionary containing validated execution price, quantity,
        tick/lot precision compliance, notional validation, and basis safety status.
        """
        clean_symbol = canonical_inst.display_symbol
        snap = self.get_latest_snapshot(clean_symbol)

        # Execution pricing
        price_prec = canonical_inst.bingx_precision
        qty_prec = canonical_inst.quantity_precision
        min_qty = canonical_inst.bingx_min_quantity
        min_notional = canonical_inst.bingx_min_notional

        # If basis snapshot available, model hypothetical fill at BingX price with slippage
        if snap and snap.bingx_price > 0:
            exec_ref_price = snap.bingx_price
            basis_state = snap.state
            basis_pct = snap.basis_pct
        else:
            exec_ref_price = signal_price
            basis_state = "UNKNOWN"
            basis_pct = 0.0

        # Round price and quantity to authoritative venue precisions
        exec_price = round(exec_ref_price, price_prec)
        exec_qty = round(intended_quantity, qty_prec)
        notional = round(exec_price * exec_qty, 2)

        # Check safety invariants
        is_valid = True
        reasons: List[str] = []

        if basis_state in ("DISLOCATED", "STALE"):
            is_valid = False
            reasons.append(f"PREFLIGHT_BLOCKED: Cross-venue basis {basis_state} (basis_pct={basis_pct:.2f}%)")

        if exec_qty < min_qty:
            is_valid = False
            reasons.append(f"PREFLIGHT_BLOCKED: Quantity {exec_qty} < BingX minQty {min_qty}")

        if notional < min_notional:
            is_valid = False
            reasons.append(f"PREFLIGHT_BLOCKED: Notional {notional} < BingX minNotional {min_notional}")

        if canonical_inst.bingx_status != "TRADABLE":
            is_valid = False
            reasons.append(f"PREFLIGHT_BLOCKED: BingX instrument status is {canonical_inst.bingx_status}")

        return {
            "is_valid": is_valid,
            "reasons": reasons,
            "canonical_instrument_id": canonical_inst.canonical_instrument_id,
            "bingx_symbol": canonical_inst.bingx_symbol,
            "signal_venue": "BINANCE",
            "execution_venue": "BINGX",
            "binance_signal_price": signal_price,
            "bingx_execution_price": exec_price,
            "bingx_execution_qty": exec_qty,
            "notional": notional,
            "basis_pct": basis_pct,
            "basis_state": basis_state,
            "status": "APPROVED" if is_valid else "REJECTED"
        }
