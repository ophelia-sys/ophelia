"""Execution engine (spec §5-§9): fills, gap handling, STOP-FIRST ambiguity, state machine.

Model A: NEXT_OPEN market entry at the open of the bar following the signal candle.
Model B: TRIGGER intrabar breakout entry (generic API; unused by DS-A acceptance).
Locked semantics D10-D15; invariant checks I2-I6 enforced here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


class ExecutionError(RuntimeError):
    pass


@dataclass
class PolicyOutcome:
    policy: str
    target_price: float
    exit_idx: Optional[int]
    exit_time_ms: Optional[int]
    exit_price: Optional[float]
    reason: str                    # WIN | LOSS | CENSORED
    realized_R: Optional[float]


@dataclass
class CoreTrade:
    intent: object
    entry_idx: int
    entry_time_ms: int
    entry_price_theoretical: float
    entry_price_modeled: float     # SLIP0 basis (= theoretical)
    stop_price: float
    risk_price: float
    risk_frac: float
    primary_policy: str
    primary_outcome: PolicyOutcome
    outcomes: Dict[str, PolicyOutcome]
    mfe_price: float
    mae_price: float
    censored: bool
    regime_at_signal: Optional[str] = None
    ignored_reason: Optional[str] = None   # only used for skipped intents


@dataclass
class SkippedSignal:
    signal_id: str
    reason: str                    # UNFILLED_EOD | POSITION_OPEN | SIGNAL_PENDING
    signal_time_ms: int


def _fill_long_stop(open_, stop):     # -> triggered?, fill
    if open_ <= stop:
        return True, open_            # gapped through at open
    return False, None


def _fill_long_target(open_, high, target):
    if open_ >= target:
        return True, open_
    if high >= target:
        return True, target
    return False, None


def _fill_short_stop(open_, stop):
    if open_ >= stop:
        return True, open_
    return False, None


def _fill_short_target(open_, low, target):
    if open_ <= target:
        return True, open_
    if low <= target:
        return True, target
    return False, None


def resolve_trade(candles_open, candles_high, candles_low, candles_close,
                  candle_times_ms, entry_idx: int, direction: int,
                  stop_price: float, policies: Dict[str, float],
                  primary_policy: str, tf_minutes: int = 5,
                  forced_entry_price: Optional[float] = None) -> CoreTrade:
    """Walk one trade from entry bar to terminal state for ALL policies independently.

    Same-bar resolution order (spec §8/D14/A1-A4):
      1. open-gap beyond a level  -> fill at this bar's OPEN (mutually exclusive sides)
      2. both levels touchable    -> STOP FIRST (conservative)
      3. single level touched     -> fill at level price
    forced_entry_price: Model B fills may differ from the entry-bar open.
    """
    n = len(candles_close)
    if not (0 <= entry_idx < n):
        raise ExecutionError(f"entry_idx {entry_idx} out of range")
    entry_price = float(forced_entry_price) if forced_entry_price is not None \
        else float(candles_open[entry_idx])
    risk_price = abs(entry_price - stop_price)
    if risk_price <= 0 or risk_price / entry_price > 0.05:
        raise ExecutionError(
            f"I3 violated: risk_pct={risk_price/entry_price:.4%} for stop {stop_price}")

    outcomes: Dict[str, PolicyOutcome] = {}
    mfe = entry_price
    mae = entry_price

    def upd_excursions(j):
        nonlocal mfe, mae
        hi, lo = candles_high[j], candles_low[j]
        if direction == 1:
            mfe = max(mfe, hi); mae = min(mae, lo)
        else:
            mfe = min(mfe, lo); mae = max(mae, hi)

    for name, tgt in policies.items():
        exit_j = exit_px = None
        reason = "CENSORED"
        for j in range(entry_idx, n):
            o, h, l = candles_open[j], candles_high[j], candles_low[j]
            if direction == 1:
                # 1. gaps at open
                if o <= stop_price:
                    exit_j, exit_px, reason = j, o, "LOSS"; break
                if o >= tgt:
                    exit_j, exit_px, reason = j, o, "WIN"; break
                stop_touched = l <= stop_price
                tgt_touched = h >= tgt
            else:
                if o >= stop_price:
                    exit_j, exit_px, reason = j, o, "LOSS"; break
                if o <= tgt:
                    exit_j, exit_px, reason = j, o, "WIN"; break
                stop_touched = h >= stop_price
                tgt_touched = l <= tgt
            # 2./3. touches
            if stop_touched and tgt_touched:
                exit_j, exit_px, reason = j, (stop_price), "LOSS"   # A1 STOP FIRST
                break
            if stop_touched:
                exit_j, exit_px, reason = j, stop_price, "LOSS"; break
            if tgt_touched:
                exit_j, exit_px, reason = j, tgt, "WIN"; break
        if exit_j is None:
            exit_j, exit_px = n - 1, float(candles_close[n - 1])
            reason = "CENSORED"
        rr = None
        if reason != "CENSORED":
            move = (exit_px / entry_price - 1.0) * direction
            rr = move / (risk_price / entry_price)
        outcomes[name] = PolicyOutcome(
            policy=name, target_price=tgt, exit_idx=exit_j,
            exit_time_ms=int(candle_times_ms[exit_j] + tf_minutes * 60_000),
            exit_price=float(exit_px), reason=reason, realized_R=rr)

    # excursions over OBSERVED life of the PRIMARY policy path (spec §14)
    prim = outcomes[primary_policy]
    for j in range(entry_idx, prim.exit_idx + 1):
        upd_excursions(j)

    return CoreTrade(
        intent=None, entry_idx=entry_idx,
        entry_time_ms=int(candle_times_ms[entry_idx]),
        entry_price_theoretical=entry_price,
        entry_price_modeled=entry_price,
        stop_price=float(stop_price),
        risk_price=risk_price, risk_frac=risk_price / entry_price,
        primary_policy=primary_policy, primary_outcome=prim,
        outcomes=outcomes, mfe_price=mfe, mae_price=mae,
        censored=(prim.reason == "CENSORED"),
    )


def _trigger_entry_fill(o, h, l, t_idx, trig):
    """Model B intrabar breakout fill (spec prompt §24). Returns (bar_idx, price) or None."""
    start = int(np.searchsorted(t_idx, trig.valid_from_open_time_ms))
    end = int(np.searchsorted(t_idx, trig.valid_to_open_time_ms_exclusive, side="left"))
    for j in range(start, end):
        o_, h_, l_ = o[j], h[j], l[j]
        if trig.direction == 1:                       # break ABOVE
            if o_ >= trig.trigger_price:
                return j, o_
            if h_ >= trig.trigger_price:
                return j, trig.trigger_price
        else:                                          # break BELOW
            if o_ <= trig.trigger_price:
                return j, o_
            if l_ <= trig.trigger_price:
                return j, trig.trigger_price
    return None


def simulate(candles: "pd.DataFrame", intents: List["SignalIntent"], cfg) -> tuple:
    """Run the canonical single-pass simulation. Returns (trades, skipped, unfilled_eod).

    SINGLE_POSITION: intents whose entry bar lies within an open position's life are
    recorded as POSITION_OPEN skips. MULTI_POSITION (ext EX2): everything trades.
    """
    otime = candles["candle_open_time"].to_numpy().astype(np.int64)
    o = candles["open"].to_numpy(float)
    h = candles["high"].to_numpy(float)
    l = candles["low"].to_numpy(float)
    c = candles["close"].to_numpy(float)
    idx_of = {int(t): i for i, t in enumerate(otime)}

    trades: List[CoreTrade] = []
    skipped: List[SkippedSignal] = []
    unfilled_eod = 0

    open_until_bar = -1                    # last bar index occupied by current position
    have_position = False

    ordered = sorted(intents, key=lambda s: (s.signal_time_ms, s.signal_id))
    for it in ordered:
        if it.entry_model == "TRIGGER" and it.trigger is not None:
            got = _trigger_entry_fill(o, h, l, otime, it.trigger)
            if got is None:
                skipped.append(SkippedSignal(it.signal_id, "TRIGGER_EXPIRED",
                                             int(it.signal_time_ms)))
                continue
            e, entry_px = got
        else:
            e = idx_of.get(int(it.entry_reference_open_time_ms), None)
            if e is None:
                unfilled_eod += 1
                skipped.append(SkippedSignal(it.signal_id, "UNFILLED_EOD",
                                             int(it.signal_time_ms)))
                continue
            entry_px = float(o[e])
        if cfg.position_mode == "SINGLE_POSITION" and have_position and e <= open_until_bar:
            skipped.append(SkippedSignal(it.signal_id, "POSITION_OPEN",
                                         int(it.signal_time_ms)))
            continue
        risk_price = abs(entry_px - it.stop_price)
        pol_prices = build_policy_prices_for(cfg, it.direction, entry_px, risk_price)
        tr = resolve_trade(o, h, l, c, otime, e, it.direction, it.stop_price,
                           pol_prices, cfg.primary_exit_policy, cfg.timeframe_minutes,
                           forced_entry_price=(entry_px if it.entry_model == "TRIGGER"
                                               else None))
        tr.intent = it
        tr.regime_at_signal = it.metadata.get("regime_at_signal")
        trades.append(tr)
        prim = tr.outcomes[cfg.primary_exit_policy]
        open_until_bar = int(prim.exit_idx)
        have_position = True
    return trades, skipped, unfilled_eod


def build_policy_prices_for(cfg, direction: int, entry_price: float, risk_price: float):
    """Deterministic target price per policy from frozen entry/risk (D11/D18)."""
    out = {}
    for k in cfg.r_targets:
        name = f"FIXED_R_{int(round(k*100)):03d}"
        out[name] = entry_price + direction * k * risk_price
    for p in cfg.abs_targets_bps:
        name = f"ABS_{int(p):03d}BP"
        out[name] = entry_price * (1 + direction * p * 1e-4)
    return out
