"""Candidate-Level Empirical Utility Study & Multi-Venue Comparative Engine.

Layer: control_plane/candidate_research.py
Contract:
- Authoritative evaluation of candidate trade outcomes post-ENTRY_READY (MFE, MAE, TP/SL barriers, realized R).
- Evaluates Base Strategy alone vs Base Strategy + TimesFM Compatibility.
- Runs comparative analysis: Candidate generation on Binance Data (Mode A) vs BingX Data (Mode B).
- Strict forward causality: Forward outcome evaluation uses ONLY candles strictly after candidate timestamp T.
- Persists all candidate outcome rows to candidate_research_outcomes table.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config, db
from .timesfm_candidate import CandidateForecastContext, CandidateForecastResult, generate_candidate_forecast
from .trade_compatibility import ForecastCompatibilityResult, evaluate_compatibility

logger = logging.getLogger("ophelia.candidate_research")


class CandidateOutcomeTracker:
    """Evaluates causal forward trade outcomes over a fixed forward evaluation horizon (15m to 60m)."""

    @classmethod
    def evaluate_outcome(
        cls,
        candidate: Dict[str, Any],
        future_5m_bars: List[dict]
    ) -> Dict[str, Any]:
        """Trace forward price trajectory over post-T closed 5m bars.
        
        Strict Invariant:
        future_5m_bars MUST only contain candles strictly after candidate timestamp T (ts > T).
        """
        direction = candidate["direction"].upper()
        entry = float(candidate["entry_price"])
        sl = float(candidate["sl_price"])
        tp1 = float(candidate["tp1_price"])
        tp2 = float(candidate["tp2_price"]) if candidate.get("tp2_price") else None
        # Direction-neutral normalized risk amount
        if direction == "LONG":
            risk = entry - sl
        else:
            risk = sl - entry
        if risk <= 0:
            risk = max(0.0001, abs(entry - sl))

        if not future_5m_bars:
            return {
                "mfe": 0.0, "mae": 0.0, "tp1_hit": 0, "tp2_hit": 0, "sl_hit": 0,
                "exit_reason": "NO_FORWARD_DATA", "time_to_exit_min": 0,
                "realized_r_multiple": 0.0, "normalized_realized_r": 0.0,
                "normalized_risk_amount": round(risk, 4),
                "return_15m": 0.0, "return_30m": 0.0,
                "return_45m": 0.0, "return_60m": 0.0,
                "retest_state_at_entry": candidate.get("retest_state", "ENTRY_READY"),
                "breakout_price": candidate.get("breakout_price"),
                "retest_touch_price": candidate.get("retest_touch_price"),
                "rejection_confirm_price": candidate.get("rejection_confirm_price"),
                "retest_elapsed_bars": candidate.get("retest_elapsed_bars", 0)
            }

        # Chronological trajectory evaluation
        sorted_bars = sorted(future_5m_bars, key=lambda x: int(x["ts"]))
        highs = [float(b["high"]) for b in sorted_bars]
        lows = [float(b["low"]) for b in sorted_bars]
        closes = [float(b["close"]) for b in sorted_bars]

        tp1_hit = False
        tp2_hit = False
        sl_hit = False
        exit_reason = "HORIZON_EXPIRED"
        time_to_exit_min = len(sorted_bars) * 5
        exit_price = closes[-1]

        if direction == "LONG":
            mfe = max(highs) - entry
            mae = min(lows) - entry  # Typically negative

            # Candle-by-candle barrier check
            for idx, b in enumerate(sorted_bars):
                bh = float(b["high"])
                bl = float(b["low"])

                # Failsafe same-candle ordering: check SL first to avoid favorable bias
                if bl <= sl:
                    sl_hit = True
                    exit_reason = "SL"
                    time_to_exit_min = (idx + 1) * 5
                    exit_price = sl
                    break
                elif bh >= tp1:
                    tp1_hit = True
                    exit_reason = "TP1"
                    time_to_exit_min = (idx + 1) * 5
                    exit_price = tp1
                    if tp2 and bh >= tp2:
                        tp2_hit = True
                    break
        else:  # SHORT
            mfe = entry - min(lows)
            mae = entry - max(highs)  # Typically negative

            for idx, b in enumerate(sorted_bars):
                bh = float(b["high"])
                bl = float(b["low"])

                if bh >= sl:
                    sl_hit = True
                    exit_reason = "SL"
                    time_to_exit_min = (idx + 1) * 5
                    exit_price = sl
                    break
                elif bl <= tp1:
                    tp1_hit = True
                    exit_reason = "TP1"
                    time_to_exit_min = (idx + 1) * 5
                    exit_price = tp1
                    if tp2 and bl <= tp2:
                        tp2_hit = True
                    break

        # Compute direction-neutral realized R-multiple
        if direction == "LONG":
            raw_pnl = exit_price - entry
        else:
            raw_pnl = entry - exit_price
        r_mult = round(raw_pnl / risk, 2)

        # Returns at specific step horizons (3 bars = 15m, 6 bars = 30m, 9 bars = 45m, 12 bars = 60m)
        def get_ret(idx: int) -> float:
            if idx < len(closes):
                px = closes[idx]
                return round(((px - entry) / entry) * 100.0, 4) if direction == "LONG" else round(((entry - px) / entry) * 100.0, 4)
            return 0.0

        # Pullback depth metrics before continuation or exit (Phase 10.2 Section 14)
        exit_bar_idx = min(len(sorted_bars), time_to_exit_min // 5)
        pre_exit_lows = lows[:max(1, exit_bar_idx)]
        pre_exit_highs = highs[:max(1, exit_bar_idx)]

        if direction == "LONG":
            min_low_val = min(pre_exit_lows)
            min_low_idx = pre_exit_lows.index(min_low_val)
            time_to_min_low = (min_low_idx + 1) * 5
            dist_below_entry = max(0.0, entry - min_low_val)
            retest_touch = float(candidate.get("retest_touch_price") or entry)
            dist_below_retest = max(0.0, retest_touch - min_low_val)
            post_min_highs = highs[min_low_idx:] if min_low_idx < len(highs) else [entry]
            mfe_after_min = max(post_min_highs) - entry
            mae_before_cont = dist_below_entry / risk
            extreme_val = min_low_val
        else:
            max_high_val = max(pre_exit_highs)
            max_high_idx = pre_exit_highs.index(max_high_val)
            time_to_min_low = (max_high_idx + 1) * 5
            dist_below_entry = max(0.0, max_high_val - entry)
            retest_touch = float(candidate.get("retest_touch_price") or entry)
            dist_below_retest = max(0.0, max_high_val - retest_touch)
            post_max_lows = lows[max_high_idx:] if max_high_idx < len(lows) else [entry]
            mfe_after_min = entry - min(post_max_lows)
            mae_before_cont = dist_below_entry / risk
            extreme_val = max_high_val

        return {
            "mfe": round(mfe, 4),
            "mae": round(mae, 4),
            "tp1_hit": 1 if tp1_hit else 0,
            "tp2_hit": 1 if tp2_hit else 0,
            "sl_hit": 1 if sl_hit else 0,
            "exit_reason": exit_reason,
            "time_to_exit_min": time_to_exit_min,
            "realized_r_multiple": r_mult,
            "normalized_realized_r": r_mult,
            "normalized_risk_amount": round(risk, 4),
            "return_15m": get_ret(2),
            "return_30m": get_ret(5),
            "return_45m": get_ret(8),
            "return_60m": get_ret(11),
            "min_low_before_continuation": round(extreme_val, 4),
            "time_to_min_low_min": time_to_min_low,
            "dist_below_entry": round(dist_below_entry, 4),
            "dist_below_retest_zone": round(dist_below_retest, 4),
            "mfe_after_min_low": round(mfe_after_min, 4),
            "mae_before_continuation": round(mae_before_cont, 4),
            "retest_state_at_entry": candidate.get("retest_state", "ENTRY_READY"),
            "breakout_price": candidate.get("breakout_price"),
            "retest_touch_price": candidate.get("retest_touch_price"),
            "rejection_confirm_price": candidate.get("rejection_confirm_price"),
            "retest_elapsed_bars": candidate.get("retest_elapsed_bars", 0)
        }


class ComparativeMarketEngine:
    """Compares candidate generation between Binance (Mode A) and BingX (Mode B)."""

    @classmethod
    def match_candidates(
        cls,
        binance_candidates: List[Dict[str, Any]],
        bingx_candidates: List[Dict[str, Any]],
        window_tolerance_ms: int = 900_000  # 15 minutes
    ) -> List[Dict[str, Any]]:
        """Pair candidates across venues and compute structural and outcome deltas."""
        comparisons: List[Dict[str, Any]] = []

        for bnc in binance_candidates:
            bn_ts = int(bnc["timestamp_ms"])
            bn_sym = bnc["symbol"]

            # Find matching candidate on BingX
            matched_bxc = None
            for bxc in bingx_candidates:
                if bxc["symbol"] == bn_sym and abs(int(bxc["timestamp_ms"]) - bn_ts) <= window_tolerance_ms:
                    matched_bxc = bxc
                    break

            if matched_bxc:
                ts_delta = int(matched_bxc["timestamp_ms"]) - bn_ts
                price_delta = float(matched_bxc["entry_price"]) - float(bnc["entry_price"])
                dir_match = (matched_bxc["direction"] == bnc["direction"])
                comparisons.append({
                    "symbol": bn_sym,
                    "binance_candidate_id": bnc["candidate_id"],
                    "bingx_candidate_id": matched_bxc["candidate_id"],
                    "binance_ts": bn_ts,
                    "bingx_ts": matched_bxc["timestamp_ms"],
                    "timestamp_delta_ms": ts_delta,
                    "direction_match": dir_match,
                    "binance_entry": float(bnc["entry_price"]),
                    "bingx_entry": float(matched_bxc["entry_price"]),
                    "entry_price_delta": round(price_delta, 4),
                    "entry_price_delta_pct": round((price_delta / float(bnc["entry_price"])) * 100.0, 4),
                    "status": "PAIRED"
                })
            else:
                comparisons.append({
                    "symbol": bn_sym,
                    "binance_candidate_id": bnc["candidate_id"],
                    "bingx_candidate_id": None,
                    "binance_ts": bn_ts,
                    "bingx_ts": None,
                    "timestamp_delta_ms": None,
                    "direction_match": False,
                    "binance_entry": float(bnc["entry_price"]),
                    "bingx_entry": None,
                    "entry_price_delta": None,
                    "entry_price_delta_pct": None,
                    "status": "BINANCE_ONLY"
                })

        return comparisons
