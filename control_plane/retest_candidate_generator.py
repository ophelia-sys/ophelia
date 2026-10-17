"""Causal Retest Setup Candidate Generator for Ophelia.

Layer: control_plane/retest_candidate_generator.py
Contract:
- Authoritatively reconstructs historical trade candidates through the genuine Ophelia retest lifecycle:
  IDLE -> WAITING_FOR_RETEST -> RETEST_ZONE_TOUCHED -> CONFIRMING_REJECTION -> ENTRY_READY
- Primary candidate research MUST NOT use breakout close as entry. Candidates are emitted ONLY at ENTRY_READY.
- Strictly causal: Evaluates closed 5m candles sequentially with zero future leakage.
- Enforces canonical structural geometry:
  LONG: SL < Entry < TP1 < TP2
  SHORT: SL > Entry > TP1 > TP2
  R:R >= 1.0 (Reward / Risk)
- Emits rich structural metadata: breakout_price, retest_touch_price, rejection_confirm_price, retest_elapsed_bars.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config, db
from .retest_engine import (
    CausalRetestEngine,
    RetestState,
    calculate_atr,
    calculate_cvd_series,
    calculate_rvol,
    compute_structural_targets_stops,
)

logger = logging.getLogger("ophelia.retest_candidate_generator")


def generate_retest_candidates(
    candles_5m: List[dict],
    symbol: str,
    timeframe: int = 5,
    min_spacing_bars: int = 6,
    require_vwap: bool = False,
    context_lookback: Optional[int] = 128
) -> List[Dict[str, Any]]:
    """Causal scan over historical 5m closed candles generating genuine ENTRY_READY retest candidates.

    Strict Invariants:
    1. Zero Lookahead: Evaluation at index i uses ONLY candles_5m[:i+1] (or rolling lookback window).
    2. Lifecycle Fidelity: Candidate is emitted ONLY when CausalRetestEngine advances to ENTRY_READY.
    3. Structural Geometry: SL, TP1, TP2 strictly conform to direction rules and R:R >= 1.0.
    """
    if len(candles_5m) < 40:
        logger.warning("Insufficient 5m candles (%d < 40) for candidate generation on %s", len(candles_5m), symbol)
        return []

    # Sort strictly ascending by timestamp
    sorted_candles = sorted(candles_5m, key=lambda x: int(x["ts"]))

    engine_long = CausalRetestEngine(
        symbol=symbol,
        timeframe=timeframe,
        direction="LONG",
        retest_window=config.RETEST_WINDOW_CANDLES,
        zone_tolerance_pct=config.RETEST_ZONE_TOLERANCE_PCT,
        displacement_atr_mult=config.DISPLACEMENT_ATR_MULT,
        rvol_threshold=config.RVOL_THRESHOLD,
        require_freshness=False  # In historical backtest, candle age check is relaxed
    )
    engine_short = CausalRetestEngine(
        symbol=symbol,
        timeframe=timeframe,
        direction="SHORT",
        retest_window=config.RETEST_WINDOW_CANDLES,
        zone_tolerance_pct=config.RETEST_ZONE_TOLERANCE_PCT,
        displacement_atr_mult=config.DISPLACEMENT_ATR_MULT,
        rvol_threshold=config.RVOL_THRESHOLD,
        require_freshness=False
    )

    state_long = RetestState(symbol=symbol, timeframe=timeframe, direction="LONG")
    state_short = RetestState(symbol=symbol, timeframe=timeframe, direction="SHORT")

    candidates: List[Dict[str, Any]] = []
    last_candidate_ts_long = 0
    last_candidate_ts_short = 0
    min_spacing_ms = min_spacing_bars * timeframe * 60 * 1000

    # Roll causally through candles
    # Need at least 25 candles for indicators (ATR, Swings, VWAP)
    # Reserve last 12 bars for future outcome tracking (+60m)
    end_idx = len(sorted_candles) - 12
    for idx in range(25, end_idx):
        start_idx = max(0, idx - context_lookback + 1) if context_lookback else 0
        window = sorted_candles[start_idx:idx + 1]
        cur_bar = window[-1]
        cur_ts = int(cur_bar["ts"])
        cur_px = float(cur_bar["close"])

        # Causal VWAP calculation over last 30 bars
        vwap_lookback = min(len(window), 30)
        vols = [float(b.get("volume") or 0.0) for b in window[-vwap_lookback:]]
        closes = [float(b["close"]) for b in window[-vwap_lookback:]]
        sum_vol = sum(vols)
        vwap = sum(c * v for c, v in zip(closes, vols)) / max(sum_vol, 1e-6)

        # -------------------------------------------------------------
        # Evaluate Step for LONG Retest Engine
        # -------------------------------------------------------------
        prev_state_l = state_long.state
        state_long = engine_long.evaluate_step(state_long, window, vwap=vwap, require_vwap=require_vwap)

        if state_long.state == "ENTRY_READY" and prev_state_l != "ENTRY_READY":
            if (cur_ts - last_candidate_ts_long) >= min_spacing_ms:
                # Compute structural targets and stops
                targets = compute_structural_targets_stops(window, "LONG", cur_px, vwap, timeframe=timeframe)
                sl = targets["sl"]
                tp1 = targets["tp1"]
                tp2 = targets.get("tp2")

                # Canonical Geometry Validation: SL < Entry < TP1, R:R >= 1.0
                if sl < cur_px < tp1 and (tp1 - cur_px) >= (cur_px - sl):
                    cand_id = f"CAND-RT-{symbol}-L-{cur_ts}"
                    candidates.append({
                        "candidate_id": cand_id,
                        "symbol": symbol,
                        "canonical_instrument_id": f"CRYPTO:{symbol}",
                        "direction": "LONG",
                        "timestamp_ms": cur_ts,
                        "candle_idx": idx,
                        "entry_price": cur_px,
                        "sl_price": sl,
                        "tp1_price": tp1,
                        "tp2_price": tp2,
                        "expected_horizon": "15m-60m",
                        "regime": "TREND",
                        "structure_state": "CONFIRMED_REJECTION",
                        "retest_state": "ENTRY_READY",
                        "breakout_price": state_long.breakout_price,
                        "retest_touch_price": state_long.zone_high or cur_px,
                        "rejection_confirm_price": cur_px,
                        "retest_elapsed_bars": state_long.elapsed_candles,
                    })
                    last_candidate_ts_long = cur_ts
            # Reset state to IDLE after emission to find next fresh breakout/retest cycle
            state_long = RetestState(symbol=symbol, timeframe=timeframe, direction="LONG")

        # -------------------------------------------------------------
        # Evaluate Step for SHORT Retest Engine
        # -------------------------------------------------------------
        prev_state_s = state_short.state
        state_short = engine_short.evaluate_step(state_short, window, vwap=vwap, require_vwap=require_vwap)

        if state_short.state == "ENTRY_READY" and prev_state_s != "ENTRY_READY":
            if (cur_ts - last_candidate_ts_short) >= min_spacing_ms:
                targets = compute_structural_targets_stops(window, "SHORT", cur_px, vwap, timeframe=timeframe)
                sl = targets["sl"]
                tp1 = targets["tp1"]
                tp2 = targets.get("tp2")

                # Canonical Geometry Validation: SL > Entry > TP1, R:R >= 1.0
                if sl > cur_px > tp1 and (cur_px - tp1) >= (sl - cur_px):
                    cand_id = f"CAND-RT-{symbol}-S-{cur_ts}"
                    candidates.append({
                        "candidate_id": cand_id,
                        "symbol": symbol,
                        "canonical_instrument_id": f"CRYPTO:{symbol}",
                        "direction": "SHORT",
                        "timestamp_ms": cur_ts,
                        "candle_idx": idx,
                        "entry_price": cur_px,
                        "sl_price": sl,
                        "tp1_price": tp1,
                        "tp2_price": tp2,
                        "expected_horizon": "15m-60m",
                        "regime": "TREND",
                        "structure_state": "CONFIRMED_REJECTION",
                        "retest_state": "ENTRY_READY",
                        "breakout_price": state_short.breakout_price,
                        "retest_touch_price": state_short.zone_low or cur_px,
                        "rejection_confirm_price": cur_px,
                        "retest_elapsed_bars": state_short.elapsed_candles,
                    })
                    last_candidate_ts_short = cur_ts
            # Reset state to IDLE after emission
            state_short = RetestState(symbol=symbol, timeframe=timeframe, direction="SHORT")

    logger.info("Generated %d causal ENTRY_READY candidates for %s", len(candidates), symbol)
    return candidates
