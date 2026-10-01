"""Authoritative Position Accounting, Mathematical Breakeven, and Dynamic Trailing Logic for Ophelia.

Layer: control_plane/position_math
Invariants:
1. Actual Fill Accounting: No calculations from requested order parameters.
   Fills govern entry price, filled qty, remaining qty, fees, and realized PnL.
2. Mathematically Correct Net Breakeven:
   Stop is NOT raw entry price.
   Calculates the minimum protective price representing the true cost basis
   of the remaining position, incorporating entry fees, TP1 exit fees,
   remaining exit fees, and funding.
3. Monotonic Dynamic Trailing:
   For LONG: new_stop >= previous_stop (never moves down).
   For SHORT: new_stop <= previous_stop (never moves up).
4. Deterministic Tick Precision:
   Stops are rounded to instrument tick size (away from danger).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import time
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class FeeModel:
    """Authoritative fee configuration governance model.
    
    Decouples fee accounting from hidden constants, enabling explicit
    auditability across SHADOW, PAPER, and LIVE execution scopes.
    """
    fee_source: str             # e.g. "SHADOW_CONFIG", "BINGX_STANDARD", "BINGX_VIP", "ACCOUNT_OVERRIDE"
    fee_type: str               # "PERCENTAGE", "FIXED", "TIERED"
    maker_fee: float            # e.g. 0.0002 (0.02%)
    taker_fee: float            # e.g. 0.0005 (0.05%)
    effective_at: int = 0       # timestamp_ms
    instrument_scope: str = "ALL"  # "ALL", "CRYPTO", or specific symbol "BTC-USDT"
    account_scope: str = "ALL"     # "ALL" or specific account_id
    mode: str = "SHADOW"           # "SHADOW", "PAPER", "LIVE"

    def get_taker_fee_rate(self) -> float:
        return self.taker_fee

    def get_maker_fee_rate(self) -> float:
        return self.maker_fee

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


SHADOW_FEE_MODEL = FeeModel(
    fee_source="SHADOW_CONFIG",
    fee_type="PERCENTAGE",
    maker_fee=0.0002,
    taker_fee=0.0005,
    effective_at=0,
    instrument_scope="ALL",
    account_scope="ALL",
    mode="SHADOW"
)

PAPER_FEE_MODEL = FeeModel(
    fee_source="PAPER_SIMULATED",
    fee_type="PERCENTAGE",
    maker_fee=0.0002,
    taker_fee=0.0005,
    effective_at=0,
    instrument_scope="ALL",
    account_scope="ALL",
    mode="PAPER"
)

LIVE_STANDARD_FEE_MODEL = FeeModel(
    fee_source="BINGX_STANDARD",
    fee_type="PERCENTAGE",
    maker_fee=0.0002,
    taker_fee=0.0005,
    effective_at=0,
    instrument_scope="ALL",
    account_scope="ALL",
    mode="LIVE"
)

_active_fee_models: Dict[str, FeeModel] = {
    "SHADOW": SHADOW_FEE_MODEL,
    "PAPER": PAPER_FEE_MODEL,
    "LIVE": LIVE_STANDARD_FEE_MODEL
}


def register_fee_model(model: FeeModel) -> None:
    """Register or override a fee model for a specific mode or instrument scope."""
    key = f"{model.mode.upper()}:{model.instrument_scope.upper()}:{str(model.account_scope).upper()}"
    _active_fee_models[key] = model
    _active_fee_models[model.mode.upper()] = model


def resolve_fee_model(mode: str = "SHADOW", symbol: str = "ALL", account_id: Any = "ALL") -> FeeModel:
    """Resolve the authoritative configured fee model for the given mode, symbol, and account."""
    m = (mode or "SHADOW").upper()
    sym = (symbol or "ALL").upper()
    acc = str(account_id or "ALL").upper()

    k1 = f"{m}:{sym}:{acc}"
    if k1 in _active_fee_models:
        return _active_fee_models[k1]

    k2 = f"{m}:{sym}:ALL"
    if k2 in _active_fee_models:
        return _active_fee_models[k2]

    k3 = f"{m}:ALL:ALL"
    if k3 in _active_fee_models:
        return _active_fee_models[k3]

    if m in _active_fee_models:
        return _active_fee_models[m]

    return SHADOW_FEE_MODEL


DEFAULT_TAKER_FEE_RATE = 0.0005  # 0.05% BingX standard futures taker fee
TAKER_FEE_RATE = DEFAULT_TAKER_FEE_RATE
MAKER_FEE_RATE = 0.0002


def round_to_tick(price: float, tick_size: float, direction: str = "LONG") -> float:
    """Round price to the nearest tick size, protecting the stop (away from danger)."""
    if tick_size <= 0:
        return price
    ticks = price / tick_size
    if direction.upper() == "LONG":
        return round(math.ceil(ticks) * tick_size, 8)
    else:
        return round(math.floor(ticks) * tick_size, 8)


def get_instrument_precision(symbol: str) -> Dict[str, float]:
    """Return tick size and quantity precision for an instrument."""
    s = symbol.upper()
    if "BTC" in s:
        return {"tick_size": 0.1, "qty_precision": 4, "price_precision": 1}
    elif "ETH" in s:
        return {"tick_size": 0.01, "qty_precision": 3, "price_precision": 2}
    elif "SOL" in s:
        return {"tick_size": 0.01, "qty_precision": 2, "price_precision": 2}
    elif "XRP" in s:
        return {"tick_size": 0.0001, "qty_precision": 1, "price_precision": 4}
    elif "GOLD" in s or "XAU" in s:
        return {"tick_size": 0.01, "qty_precision": 2, "price_precision": 2}
    else:
        return {"tick_size": 0.01, "qty_precision": 2, "price_precision": 2}


def calculate_actual_fee(
    price: float,
    qty: float,
    fee_rate: Optional[float] = None,
    fee_model: Optional[FeeModel] = None
) -> float:
    """Calculate actual transaction fee for a fill using explicit FeeModel or rate."""
    if price <= 0 or qty <= 0:
        return 0.0
    if fee_rate is not None:
        rate = fee_rate
    elif fee_model is not None:
        rate = fee_model.get_taker_fee_rate()
    else:
        rate = resolve_fee_model().get_taker_fee_rate()
    return round(price * qty * rate, 8)


def calculate_realized_pnl(
    entry_price: float,
    exit_price: float,
    qty: float,
    direction: str,
    fee: float = 0.0
) -> float:
    """Calculate net realized PnL for a closed portion of a position."""
    if entry_price <= 0 or exit_price <= 0 or qty <= 0:
        return 0.0
    is_long = direction.upper() == "LONG"
    gross_pnl = (exit_price - entry_price) * qty * (1.0 if is_long else -1.0)
    return round(gross_pnl - fee, 6)


def calculate_unrealized_pnl(
    entry_price: float,
    current_price: float,
    qty: float,
    direction: str
) -> float:
    """Calculate gross unrealized PnL based on mark/current price."""
    if entry_price <= 0 or current_price <= 0 or qty <= 0:
        return 0.0
    is_long = direction.upper() == "LONG"
    return round((current_price - entry_price) * qty * (1.0 if is_long else -1.0), 6)


def calculate_net_breakeven_stop(
    entry_price: float,
    initial_qty: float,
    remaining_qty: float,
    direction: str,
    entry_fee: float,
    tp1_realized_pnl: float,
    tp1_fee: float,
    funding_accrued: float = 0.0,
    fee_rate: Optional[float] = None,
    fee_model: Optional[FeeModel] = None,
    tick_size: float = 0.01,
    previous_stop: Optional[float] = None
) -> Dict[str, Any]:
    """Calculate the mathematically correct net breakeven stop for the remaining position.
    
    Invariants:
    1. NEVER raw entry price: accounts for entry fee, partial exit fee, remaining exit fee, funding.
    2. Cost basis of remaining leg:
       LONG:  entry * (1 + fee_rate) / (1 - fee_rate)
       SHORT: entry * (1 - fee_rate) / (1 + fee_rate)
    3. Net trade breakeven: Price at which total trade Net PnL (TP1 profit + remaining PnL - all fees) >= 0.
    4. Monotonicity:
       LONG:  breakeven_stop >= previous_stop
       SHORT: breakeven_stop <= previous_stop
    5. Tick rounding:
       LONG:  ceil to next tick (away from danger)
       SHORT: floor to next tick (away from danger)
    """
    is_long = direction.upper() == "LONG"
    now_ms = int(time.time() * 1000)

    # Resolve effective fee model and rate
    if fee_model is not None:
        effective_fee_model = fee_model
        effective_rate = fee_model.get_taker_fee_rate() if fee_rate is None else fee_rate
    elif fee_rate is not None:
        effective_fee_model = resolve_fee_model()
        effective_rate = fee_rate
    else:
        effective_fee_model = resolve_fee_model()
        effective_rate = effective_fee_model.get_taker_fee_rate()

    if remaining_qty <= 0 or entry_price <= 0:
        return {
            "breakeven_stop": previous_stop or entry_price,
            "calculated_cost_basis": entry_price,
            "calculation_inputs": {},
            "calculated_at_ms": now_ms
        }

    # 1. Cost basis of remaining position covering its roundtrip entry & exit fees
    if is_long:
        cost_basis = entry_price * ((1.0 + effective_rate) / (1.0 - effective_rate))
    else:
        cost_basis = entry_price * ((1.0 - effective_rate) / (1.0 + effective_rate))

    # 2. Total trade breakeven price (accounting for TP1 profit and all fees)
    prior_net_cash = tp1_realized_pnl - (entry_fee + tp1_fee + funding_accrued)
    if is_long:
        # (P_be - P_entry) * remaining_qty - P_be * remaining_qty * effective_rate + prior_net_cash >= 0
        denom = remaining_qty * (1.0 - effective_rate)
        if denom > 0:
            total_be_price = (entry_price * remaining_qty - prior_net_cash) / denom
        else:
            total_be_price = cost_basis
        # Protect at least cost basis to guarantee non-negative remaining leg
        candidate_stop = max(cost_basis, total_be_price)
        # Round UP to tick size (conservative)
        if tick_size > 0:
            candidate_stop = math.ceil(candidate_stop / tick_size) * tick_size
        candidate_stop = round(candidate_stop, 6)
        # Monotonicity: stop only moves UP for LONG
        if previous_stop is not None and previous_stop > 0:
            final_stop = max(previous_stop, candidate_stop)
        else:
            final_stop = candidate_stop
    else:
        # (P_entry - P_be) * remaining_qty - P_be * remaining_qty * effective_rate + prior_net_cash >= 0
        denom = remaining_qty * (1.0 + effective_rate)
        if denom > 0:
            total_be_price = (entry_price * remaining_qty + prior_net_cash) / denom
        else:
            total_be_price = cost_basis
        # Protect at least cost basis
        candidate_stop = min(cost_basis, total_be_price)
        # Round DOWN to tick size (conservative)
        if tick_size > 0:
            candidate_stop = math.floor(candidate_stop / tick_size) * tick_size
        candidate_stop = round(candidate_stop, 6)
        # Monotonicity: stop only moves DOWN for SHORT
        if previous_stop is not None and previous_stop > 0:
            final_stop = min(previous_stop, candidate_stop)
        else:
            final_stop = candidate_stop

    inputs = {
        "entry_price": entry_price,
        "initial_qty": initial_qty,
        "remaining_qty": remaining_qty,
        "direction": direction.upper(),
        "entry_fee": entry_fee,
        "tp1_realized_pnl": tp1_realized_pnl,
        "tp1_fee": tp1_fee,
        "funding_accrued": funding_accrued,
        "fee_rate": effective_rate,
        "fee_model": effective_fee_model.to_dict() if effective_fee_model else None,
        "fee_source": effective_fee_model.fee_source if effective_fee_model else "CUSTOM",
        "tick_size": tick_size,
        "previous_stop": previous_stop,
        "cost_basis_raw": round(cost_basis, 6),
        "total_be_raw": round(total_be_price, 6)
    }

    return {
        "breakeven_stop": final_stop,
        "calculated_cost_basis": round(cost_basis, 6),
        "calculation_inputs": inputs,
        "calculated_at_ms": now_ms
    }


def calculate_dynamic_trailing_stop(
    current_price: float,
    entry_price: float,
    direction: str,
    current_stop: float,
    trailing_ref: float,
    atr: float = 0.0,
    volatility: float = 0.0,
    regime: str = "TREND",
    trailing_pct: float = 1.5,
    tick_size: float = 0.01,
    min_move_pct: float = 0.001
) -> Dict[str, Any]:
    """Calculate server-side dynamic trailing stop with strict monotonicity.
    
    Invariants:
    1. LONG: new_stop >= current_stop (monotonic non-decreasing).
    2. SHORT: new_stop <= current_stop (monotonic non-increasing).
    3. Trailing method incorporates ATR & volatility regime if available, else trailing_pct.
    4. Threshold gating: updates emitted only on meaningful price progress (>= min_move_pct or 2 ticks).
    """
    is_long = direction.upper() == "LONG"
    now_ms = int(time.time() * 1000)

    if current_price <= 0 or entry_price <= 0:
        return {
            "new_stop": current_stop,
            "ref_price": trailing_ref or entry_price,
            "moved": False,
            "reason": "INVALID_PRICE"
        }

    # Reference peak price (high-water mark for LONG, low-water mark for SHORT)
    if is_long:
        ref_price = max(trailing_ref or entry_price, current_price)
    else:
        ref_price = min(trailing_ref or entry_price, current_price) if (trailing_ref and trailing_ref > 0) else current_price

    # Trailing distance calculation
    if atr > 0:
        mult = 2.0 if regime == "TREND" else (1.5 if regime in ("HIGH", "VOLATILE") else 2.5)
        trail_distance = max(mult * atr, ref_price * (trailing_pct / 100.0))
        method = "ATR_DYNAMIC"
    else:
        trail_distance = ref_price * (trailing_pct / 100.0)
        method = "PERCENTAGE_TRAILING"

    # Candidate calculation
    if is_long:
        raw_stop = ref_price - trail_distance
        if tick_size > 0:
            candidate_stop = math.floor(raw_stop / tick_size) * tick_size
        else:
            candidate_stop = raw_stop
        candidate_stop = round(candidate_stop, 6)
        # Monotonicity clamp
        improved_stop = max(current_stop or 0.0, candidate_stop)
        stop_advanced = improved_stop > (current_stop or 0.0)
    else:
        raw_stop = ref_price + trail_distance
        if tick_size > 0:
            candidate_stop = math.ceil(raw_stop / tick_size) * tick_size
        else:
            candidate_stop = raw_stop
        candidate_stop = round(candidate_stop, 6)
        # Monotonicity clamp
        improved_stop = min(current_stop or 999999.0, candidate_stop) if (current_stop and current_stop > 0) else candidate_stop
        stop_advanced = improved_stop < (current_stop or 999999.0)

    # Meaningful movement threshold check
    threshold = max(2.0 * tick_size, (current_stop or entry_price) * min_move_pct)
    meaningful = abs(improved_stop - (current_stop or 0.0)) >= threshold

    profit_distance = (current_price - entry_price) * (1.0 if is_long else -1.0)

    trailing_inputs = {
        "current_price": current_price,
        "entry_price": entry_price,
        "direction": direction.upper(),
        "ref_price": ref_price,
        "atr": atr,
        "volatility": volatility,
        "regime": regime,
        "trailing_pct": trailing_pct,
        "trail_distance": round(trail_distance, 6),
        "tick_size": tick_size,
        "profit_distance": round(profit_distance, 6),
        "method": method
    }

    return {
        "new_stop": improved_stop,
        "ref_price": ref_price,
        "moved": stop_advanced and meaningful,
        "trailing_method": method,
        "trailing_inputs": trailing_inputs,
        "last_update_ms": now_ms,
        "reason": f"TRAILING_ADVANCED_{method}" if stop_advanced else "NO_ADVANCEMENT",
        "profit_at_update": round(profit_distance, 4),
        "regime_at_update": regime
    }
