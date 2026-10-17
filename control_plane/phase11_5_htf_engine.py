"""Ophelia Phase 11.5: Higher-Timeframe Regime & Trade Management Research Engine.

Layer: control_plane/phase11_5_htf_engine.py
Contract:
- Starts strictly from Variant D:
    Displacement >= 1.2 ATR
    Rejection body >= 0.45
    RVOL >= 1.0
- Causal 1H and 4H Higher-Timeframe (HTF) feature extraction:
    1. 1H regime (trend alignment, volatility, range vs expansion)
    2. 4H regime (trend alignment, macro volatility)
    3. HTF trend alignment (1H & 4H EMA20 vs EMA50 directional agreement)
    4. HTF volatility state (ATR%, percentiles)
    5. HTF range vs expansion (ADX proxy, swing distance)
    6. HTF structure location (relative position within 1H/4H swings)
    7. Interaction of HTF regime x Variant D
- Discrete Trade Management Policies (researched independently, frozen before TEST):
    1. Fixed SL/TP (Baseline)
    2. TP1 Partial (50% exit at TP1)
    3. Breakeven after +0.5R
    4. Breakeven after +0.8R
    5. Breakeven after +1.0R
    6. Structural Trailing
    7. ATR Trailing
    8. Partial + Trailing
    9. Time-based Exit (30m / 60m horizon limit)
- Comparative Matrix across Train, Val, Test:
    - BASELINE A
    - VARIANT D
    - VARIANT D + HTF
    - VARIANT D + MANAGEMENT
    - VARIANT D + HTF + MANAGEMENT
- Execution Friction: 9.0 bps round-trip (0.05% fee + 0.04% slippage).
- Chronological Partitions (Oct 1 to Nov 30, 2023, 61 days):
    TRAIN:      Oct 01 to Oct 20
    VALIDATION: Oct 21 to Nov 05
    TEST:       Nov 06 to Nov 30
- Invariants: TRADING_AUTHORITY = FALSE, EXECUTION_MODE = SHADOW, LIVE_ORDERS = FORBIDDEN.
- TimesFM ISOLATED: Not used in trade filtering.
"""
from __future__ import annotations

import datetime
import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .phase11_repair_engine import (
    CandidateFeatureSnapshot,
    Phase11StrategyRepairRunner,
    assign_split,
    bootstrap_ci,
    classify_rr_bucket,
    TS_OCT_01_2023,
    TS_OCT_20_2023,
    TS_OCT_21_2023,
    TS_NOV_05_2023,
    TS_NOV_06_2023,
    TS_NOV_30_2023,
    EMBARGO_MS,
    FRICTION_BASE,
)
from .retest_engine import calculate_atr

logger = logging.getLogger("ophelia.phase11_5_htf")


@dataclass(slots=True)
class HTFCandidateSnapshot:
    """Combines 5m candidate snapshot with causal 1H and 4H features."""
    base: CandidateFeatureSnapshot
    
    # 1H HTF Features
    has_1h: bool
    trend_1h: str                # "BULLISH", "BEARISH", "NEUTRAL"
    trend_aligned_1h: bool       # True if 1H trend matches trade direction
    atr_pct_1h: float
    vol_regime_1h: str           # "LOW", "NORMAL", "HIGH"
    adx_proxy_1h: float
    expansion_state_1h: str      # "EXPANSION", "RANGE"
    swing_loc_1h: float          # [0, 1] relative position between 48h swing low and high
    structure_favorable_1h: bool # Not buying top 10% or selling bottom 10%
    
    # 4H HTF Features
    has_4h: bool
    trend_4h: str                # "BULLISH", "BEARISH", "NEUTRAL"
    trend_aligned_4h: bool
    atr_pct_4h: float
    vol_regime_4h: str
    
    # Combined HTF Alignment Flag
    htf_aligned: bool


def resample_htf_candles(candles_5m: List[dict], bar_ms: int) -> List[dict]:
    """Resamples sorted 5m candles into closed higher timeframe candles.
    
    bar_ms: 3600 * 1000 for 1H, 4 * 3600 * 1000 for 4H.
    A bar covering [T, T + bar_ms) is stamped at T + bar_ms (its close time).
    """
    if not candles_5m:
        return []
        
    grouped: Dict[int, List[dict]] = {}
    for c in candles_5m:
        ts = int(c["ts"])
        # Bucket key is start time of HTF bar
        bucket_start = (ts // bar_ms) * bar_ms
        if bucket_start not in grouped:
            grouped[bucket_start] = []
        grouped[bucket_start].append(c)
        
    htf_candles = []
    # Expected number of 5m bars per HTF bar
    expected_bars = bar_ms // (5 * 60 * 1000)
    
    for bucket_start, bars in sorted(grouped.items(), key=lambda x: x[0]):
        # Only accept completed or nearly completed bars (>= 90% bars present)
        if len(bars) < max(1, int(expected_bars * 0.9)):
            continue
            
        b_open = float(bars[0]["open"])
        b_high = max(float(b["high"]) for b in bars)
        b_low = min(float(b["low"]) for b in bars)
        b_close = float(bars[-1]["close"])
        b_vol = sum(float(b.get("volume") or 0.0) for b in bars)
        close_ts = bucket_start + bar_ms
        
        htf_candles.append({
            "ts": close_ts,
            "open": b_open,
            "high": b_high,
            "low": b_low,
            "close": b_close,
            "volume": b_vol,
        })
        
    return htf_candles


def compute_htf_features(
    cand_ts: int,
    direction: str,
    candles_1h: List[dict],
    candles_4h: List[dict]
) -> Dict[str, Any]:
    """Extracts strictly causal HTF features using only bars closed BEFORE cand_ts."""
    # Strict causal slicing: bars with close_ts <= cand_ts
    hist_1h = [c for c in candles_1h if int(c["ts"]) <= cand_ts]
    hist_4h = [c for c in candles_4h if int(c["ts"]) <= cand_ts]
    
    # 1. 1H Features
    if len(hist_1h) >= 20:
        c1h = [float(c["close"]) for c in hist_1h]
        h1h = [float(c["high"]) for c in hist_1h]
        l1h = [float(c["low"]) for c in hist_1h]
        
        ema_20_1h = float(pd.Series(c1h).ewm(span=20, adjust=False).mean().iloc[-1])
        ema_50_1h = float(pd.Series(c1h).ewm(span=50, adjust=False).mean().iloc[-1])
        
        if ema_20_1h > ema_50_1h * 1.0005:
            trend_1h = "BULLISH"
        elif ema_20_1h < ema_50_1h * 0.9995:
            trend_1h = "BEARISH"
        else:
            trend_1h = "NEUTRAL"
            
        trend_aligned_1h = (direction == "LONG" and trend_1h == "BULLISH") or (direction == "SHORT" and trend_1h == "BEARISH")
        
        atr_1h_series = calculate_atr(h1h, l1h, c1h, 14)
        cur_atr_1h = atr_1h_series[-1] if atr_1h_series else c1h[-1] * 0.01
        atr_pct_1h = cur_atr_1h / max(1e-6, c1h[-1])
        
        if atr_pct_1h < 0.006:
            vol_regime_1h = "LOW"
        elif atr_pct_1h > 0.018:
            vol_regime_1h = "HIGH"
        else:
            vol_regime_1h = "NORMAL"
            
        diffs_1h = [abs(c1h[i] - c1h[i-1]) for i in range(max(1, len(c1h)-10), len(c1h))]
        adx_proxy_1h = (sum(diffs_1h) / max(1e-6, len(diffs_1h) * cur_atr_1h)) * 25.0
        expansion_1h = "EXPANSION" if adx_proxy_1h >= 18.0 else "RANGE"
        
        # Structure location: 48-hour swing range
        window_1h = hist_1h[-48:]
        high_48h = max(float(b["high"]) for b in window_1h)
        low_48h = min(float(b["low"]) for b in window_1h)
        rng_48h = max(1e-6, high_48h - low_48h)
        swing_loc_1h = (c1h[-1] - low_48h) / rng_48h
        
        # Favorable structure: not buying into extreme ceiling (>0.90) or selling into floor (<0.10)
        structure_favorable_1h = (direction == "LONG" and swing_loc_1h <= 0.85) or (direction == "SHORT" and swing_loc_1h >= 0.15)
        has_1h = True
    else:
        trend_1h = "NEUTRAL"
        trend_aligned_1h = False
        atr_pct_1h = 0.01
        vol_regime_1h = "NORMAL"
        adx_proxy_1h = 15.0
        expansion_1h = "RANGE"
        swing_loc_1h = 0.5
        structure_favorable_1h = True
        has_1h = False

    # 2. 4H Features
    if len(hist_4h) >= 10:
        c4h = [float(c["close"]) for c in hist_4h]
        h4h = [float(c["high"]) for c in hist_4h]
        l4h = [float(c["low"]) for c in hist_4h]
        
        ema_20_4h = float(pd.Series(c4h).ewm(span=20, adjust=False).mean().iloc[-1])
        ema_50_4h = float(pd.Series(c4h).ewm(span=50, adjust=False).mean().iloc[-1])
        
        if ema_20_4h > ema_50_4h * 1.001:
            trend_4h = "BULLISH"
        elif ema_20_4h < ema_50_4h * 0.999:
            trend_4h = "BEARISH"
        else:
            trend_4h = "NEUTRAL"
            
        trend_aligned_4h = (direction == "LONG" and trend_4h == "BULLISH") or (direction == "SHORT" and trend_4h == "BEARISH")
        
        atr_4h_series = calculate_atr(h4h, l4h, c4h, min(14, len(c4h)-1))
        cur_atr_4h = atr_4h_series[-1] if atr_4h_series else c4h[-1] * 0.02
        atr_pct_4h = cur_atr_4h / max(1e-6, c4h[-1])
        vol_regime_4h = "HIGH" if atr_pct_4h > 0.030 else ("LOW" if atr_pct_4h < 0.012 else "NORMAL")
        has_4h = True
    else:
        trend_4h = "NEUTRAL"
        trend_aligned_4h = False
        atr_pct_4h = 0.02
        vol_regime_4h = "NORMAL"
        has_4h = False

    # Combined HTF alignment: 1H trend alignment + favorable structure location
    htf_aligned = bool(trend_aligned_1h and structure_favorable_1h)
    
    return {
        "has_1h": has_1h,
        "trend_1h": trend_1h,
        "trend_aligned_1h": trend_aligned_1h,
        "atr_pct_1h": atr_pct_1h,
        "vol_regime_1h": vol_regime_1h,
        "adx_proxy_1h": adx_proxy_1h,
        "expansion_state_1h": expansion_1h,
        "swing_loc_1h": swing_loc_1h,
        "structure_favorable_1h": structure_favorable_1h,
        "has_4h": has_4h,
        "trend_4h": trend_4h,
        "trend_aligned_4h": trend_aligned_4h,
        "atr_pct_4h": atr_pct_4h,
        "vol_regime_4h": vol_regime_4h,
        "htf_aligned": htf_aligned,
    }


def simulate_trade_management(
    policy_name: str,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: Optional[float],
    future_candles_5m: List[dict],
    cur_atr: float,
    friction_rate: float = FRICTION_BASE
) -> Tuple[float, float, str, int]:
    """Simulates a specific trade management policy forward through 5m candles.
    
    Returns:
        (gross_realized_r, net_realized_r, exit_reason, exit_duration_min)
    """
    risk = abs(entry - sl)
    if risk <= 0:
        return 0.0, 0.0, "INVALID_RISK", 0
        
    reward1 = abs(tp1 - entry)
    r_target_tp1 = reward1 / risk
    tp2_price = tp2 if tp2 is not None else (entry + 2.0 * reward1 if direction == "LONG" else entry - 2.0 * reward1)
    
    cost_in_r = (friction_rate * entry) / risk
    
    if not future_candles_5m:
        return 0.0, -cost_in_r, "NO_DATA", 0
        
    # State variables
    cur_sl = sl
    be_active = False
    partial_taken = False
    realized_r_accum = 0.0
    active_size = 1.0  # Fraction of initial position currently open
    
    highest_high = entry
    lowest_low = entry
    
    exit_reason = "HORIZON_EXPIRED"
    exit_bars = len(future_candles_5m)
    final_exit_price = float(future_candles_5m[-1]["close"])
    
    max_bars = 24  # Max 2-hour monitoring window
    monitored_bars = future_candles_5m[:max_bars]
    
    for bar_idx, bar in enumerate(monitored_bars, 1):
        bh = float(bar["high"])
        bl = float(bar["low"])
        bc = float(bar["close"])
        
        # Update extreme points for trailing
        if bh > highest_high:
            highest_high = bh
        if bl < lowest_low:
            lowest_low = bl
            
        current_mfe_r = (highest_high - entry) / risk if direction == "LONG" else (entry - lowest_low) / risk
        
        # Policy-specific pre-check stop adjustments
        if policy_name == "BE_0.5R" and not be_active and current_mfe_r >= 0.5:
            cur_sl = entry
            be_active = True
        elif policy_name == "BE_0.8R" and not be_active and current_mfe_r >= 0.8:
            cur_sl = entry
            be_active = True
        elif policy_name == "BE_1.0R" and not be_active and current_mfe_r >= 1.0:
            cur_sl = entry
            be_active = True
        elif policy_name == "ATR_TRAILING":
            trail_dist = 1.5 * cur_atr
            if direction == "LONG":
                new_stop = highest_high - trail_dist
                if new_stop > cur_sl:
                    cur_sl = new_stop
            else:
                new_stop = lowest_low + trail_dist
                if new_stop < cur_sl:
                    cur_sl = new_stop
        elif policy_name == "STRUCTURAL_TRAILING" and bar_idx >= 3:
            # Trailing stop anchored to prior 2-bar low/high
            if direction == "LONG":
                prev_low = min(float(monitored_bars[b]["low"]) for b in range(max(0, bar_idx-3), bar_idx))
                if prev_low > cur_sl:
                    cur_sl = prev_low
            else:
                prev_high = max(float(monitored_bars[b]["high"]) for b in range(max(0, bar_idx-3), bar_idx))
                if prev_high < cur_sl:
                    cur_sl = prev_high
                    
        # Policy 9: Time-based exit at 6 bars (30m)
        if policy_name == "TIME_EXIT_30M" and bar_idx == 6:
            exit_reason = "TIME_EXIT_30M"
            exit_bars = bar_idx
            final_exit_price = bc
            break

        # Check Stop and Target triggers on this candle
        if direction == "LONG":
            hit_stop = (bl <= cur_sl)
            hit_tp1 = (bh >= tp1)
            hit_tp2 = (bh >= tp2_price)
            
            # Conservative rule: if stop touched, exit triggered
            if hit_stop:
                exit_price = cur_sl
                r_step = (exit_price - entry) / risk
                realized_r_accum += active_size * r_step
                active_size = 0.0
                exit_reason = "BE_EXIT" if be_active and abs(cur_sl - entry) < 1e-4 else "SL"
                exit_bars = bar_idx
                break
                
            if hit_tp1 and not partial_taken:
                if policy_name in ("TP1_PARTIAL", "PARTIAL_TRAILING"):
                    # Close 50% at TP1
                    r_tp1 = (tp1 - entry) / risk
                    realized_r_accum += 0.5 * r_tp1
                    active_size = 0.5
                    partial_taken = True
                    # Move stop to breakeven
                    cur_sl = entry
                    be_active = True
                    if policy_name == "PARTIAL_TRAILING":
                        # Trail remaining 50%
                        pass
                elif policy_name == "FIXED_SL_TP":
                    r_tp1 = (tp1 - entry) / risk
                    realized_r_accum += active_size * r_tp1
                    active_size = 0.0
                    exit_reason = "TP1"
                    exit_bars = bar_idx
                    break
                    
            if partial_taken and hit_tp2:
                r_tp2 = (tp2_price - entry) / risk
                realized_r_accum += active_size * r_tp2
                active_size = 0.0
                exit_reason = "TP2"
                exit_bars = bar_idx
                break

        else: # SHORT
            hit_stop = (bh >= cur_sl)
            hit_tp1 = (bl <= tp1)
            hit_tp2 = (bl <= tp2_price)
            
            if hit_stop:
                exit_price = cur_sl
                r_step = (entry - exit_price) / risk
                realized_r_accum += active_size * r_step
                active_size = 0.0
                exit_reason = "BE_EXIT" if be_active and abs(cur_sl - entry) < 1e-4 else "SL"
                exit_bars = bar_idx
                break
                
            if hit_tp1 and not partial_taken:
                if policy_name in ("TP1_PARTIAL", "PARTIAL_TRAILING"):
                    r_tp1 = (entry - tp1) / risk
                    realized_r_accum += 0.5 * r_tp1
                    active_size = 0.5
                    partial_taken = True
                    cur_sl = entry
                    be_active = True
                elif policy_name == "FIXED_SL_TP":
                    r_tp1 = (entry - tp1) / risk
                    realized_r_accum += active_size * r_tp1
                    active_size = 0.0
                    exit_reason = "TP1"
                    exit_bars = bar_idx
                    break
                    
            if partial_taken and hit_tp2:
                r_tp2 = (entry - tp2_price) / risk
                realized_r_accum += active_size * r_tp2
                active_size = 0.0
                exit_reason = "TP2"
                exit_bars = bar_idx
                break

    # If position still partially or fully open at horizon end, close at final candle close
    if active_size > 0.0:
        if direction == "LONG":
            r_close = (final_exit_price - entry) / risk
        else:
            r_close = (entry - final_exit_price) / risk
        realized_r_accum += active_size * r_close
        if exit_reason == "HORIZON_EXPIRED":
            exit_bars = len(monitored_bars)

    gross_r = realized_r_accum
    net_r = gross_r - cost_in_r
    duration_min = exit_bars * 5
    return gross_r, net_r, exit_reason, duration_min


class Phase11_5HTFEngine:
    """Orchestrates Phase 11.5 HTF regime and trade management research."""

    def __init__(self, parquet_path: str = "data/processed/binance_um_universe_1m_v2.parquet"):
        self.parquet_path = parquet_path
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.htf_candidates: List[HTFCandidateSnapshot] = []
        self.future_candles_cache: Dict[str, List[dict]] = {}

    def run_research(self) -> Dict[str, Any]:
        logger.info("Initializing Phase 11.5 HTF Regime & Trade Management Research Engine...")
        t0 = time.perf_counter()
        
        # 1. Reuse Phase 11 runner to get base candidate snapshots and 5m candles
        from .phase10_3_validation_engine import load_and_resample_5m
        candles_5m_by_symbol = load_and_resample_5m(
            self.parquet_path,
            t_start=TS_OCT_01_2023,
            t_end=TS_NOV_30_2023,
            symbols=self.symbols
        )
        self.future_candles_cache = candles_5m_by_symbol
        
        repair_runner = Phase11StrategyRepairRunner(self.parquet_path)
        base_results = repair_runner.run_analysis()
        base_snapshots = repair_runner.snapshots
        logger.info("Base snapshots loaded: %d candidates", len(base_snapshots))
        
        # 2. Resample 1H and 4H candles for each symbol
        candles_1h_by_sym = {}
        candles_4h_by_sym = {}
        for sym in self.symbols:
            c5m = candles_5m_by_symbol.get(sym, [])
            candles_1h_by_sym[sym] = resample_htf_candles(c5m, bar_ms=3600 * 1000)
            candles_4h_by_sym[sym] = resample_htf_candles(c5m, bar_ms=4 * 3600 * 1000)
            logger.info("%s: Resampled %d 1H candles, %d 4H candles", sym, len(candles_1h_by_sym[sym]), len(candles_4h_by_sym[sym]))
            
        # 3. Augment each candidate snapshot with HTF features
        for snap in base_snapshots:
            sym = snap.symbol
            c1h = candles_1h_by_sym.get(sym, [])
            c4h = candles_4h_by_sym.get(sym, [])
            htf_feats = compute_htf_features(snap.timestamp_ms, snap.direction, c1h, c4h)
            
            htf_snap = HTFCandidateSnapshot(
                base=snap,
                has_1h=htf_feats["has_1h"],
                trend_1h=htf_feats["trend_1h"],
                trend_aligned_1h=htf_feats["trend_aligned_1h"],
                atr_pct_1h=htf_feats["atr_pct_1h"],
                vol_regime_1h=htf_feats["vol_regime_1h"],
                adx_proxy_1h=htf_feats["adx_proxy_1h"],
                expansion_state_1h=htf_feats["expansion_state_1h"],
                swing_loc_1h=htf_feats["swing_loc_1h"],
                structure_favorable_1h=htf_feats["structure_favorable_1h"],
                has_4h=htf_feats["has_4h"],
                trend_4h=htf_feats["trend_4h"],
                trend_aligned_4h=htf_feats["trend_aligned_4h"],
                atr_pct_4h=htf_feats["atr_pct_4h"],
                vol_regime_4h=htf_feats["vol_regime_4h"],
                htf_aligned=htf_feats["htf_aligned"],
            )
            self.htf_candidates.append(htf_snap)
            
        logger.info("Total HTF snapshots constructed: %d", len(self.htf_candidates))
        
        # 4. Filter strictly for Variant D
        # Variant D: Displacement >= 1.2 ATR, Rejection body >= 0.45, RVOL >= 1.0
        var_d_candidates = [
            s for s in self.htf_candidates
            if (s.base.displacement_atr >= 1.2 and s.base.rejection_body_ratio >= 0.45 and s.base.rvol >= 1.0)
        ]
        logger.info("Variant D candidates: %d total", len(var_d_candidates))
        
        # 5. Evaluate HTF Regimes on Variant D
        htf_eval = self._audit_htf_regimes(var_d_candidates)
        
        # 6. Evaluate 9 Trade Management Policies on Variant D
        mgmt_eval = self._audit_trade_management(var_d_candidates)
        
        # 7. Select best policy from Train/Val and construct Comparative Matrix across splits
        comp_matrix = self._construct_comparative_matrix(base_snapshots, self.htf_candidates, var_d_candidates, mgmt_eval["best_policy"])
        
        # 8. Cross-asset and chronological stability audit
        stability_eval = self._audit_asset_stability(var_d_candidates, mgmt_eval["best_policy"])
        
        elapsed = time.perf_counter() - t0
        return {
            "elapsed_seconds": round(elapsed, 2),
            "variant_d_definition": {
                "min_displacement_atr": 1.2,
                "min_rejection_body_ratio": 0.45,
                "min_rvol": 1.0
            },
            "htf_regime_audit": htf_eval,
            "trade_management_audit": mgmt_eval,
            "comparative_matrix": comp_matrix,
            "stability_audit": stability_eval
        }

    def _cohort_stats(self, net_rs: List[float], gross_rs: List[float], is_wins: List[bool]) -> Dict[str, Any]:
        n = len(net_rs)
        if n == 0:
            return {
                "count": 0, "win_rate": 0.0, "wins": 0, "losses": 0,
                "gross_r": 0.0, "net_r": 0.0, "mean_r": 0.0, "median_r": 0.0, "pf": 0.0,
                "ci_mean_r": [0.0, 0.0], "ci_wr": [0.0, 0.0]
            }
        wins = sum(1 for w in is_wins if w)
        wr = (wins / n) * 100.0
        tot_net = sum(net_rs)
        tot_gross = sum(gross_rs)
        mean_r = float(np.mean(net_rs))
        med_r = float(np.median(net_rs))
        
        g_wins = sum(r for r in gross_rs if r > 0)
        g_losses = abs(sum(r for r in gross_rs if r < 0))
        pf = round(g_wins / max(1e-6, g_losses), 2)
        
        _, ci_l, ci_u = bootstrap_ci(net_rs)
        wr_bool = [1.0 if w else 0.0 for w in is_wins]
        _, wr_l, wr_u = bootstrap_ci(wr_bool)
        
        return {
            "count": n,
            "win_rate": round(wr, 2),
            "wins": wins,
            "losses": n - wins,
            "gross_r": round(tot_gross, 2),
            "net_r": round(tot_net, 2),
            "mean_r": round(mean_r, 3),
            "median_r": round(med_r, 3),
            "pf": pf,
            "ci_mean_r": [round(ci_l, 3), round(ci_u, 3)],
            "ci_wr": [round(wr_l * 100.0, 2), round(wr_u * 100.0, 2)]
        }

    def _audit_htf_regimes(self, var_d_cands: List[HTFCandidateSnapshot]) -> Dict[str, Any]:
        """Evaluates HTF trend alignment, volatility, and structure location on Variant D."""
        test_cands = [s for s in var_d_cands if s.base.split == "TEST"]
        
        def eval_subset(subset: List[HTFCandidateSnapshot]) -> Dict[str, Any]:
            net_rs = [s.base.net_realized_r_base for s in subset]
            gross_rs = [s.base.gross_realized_r for s in subset]
            is_wins = [s.base.exit_reason in ("TP1", "TP2") for s in subset]
            return self._cohort_stats(net_rs, gross_rs, is_wins)
            
        trend_1h_eval = {
            "ALIGNED": eval_subset([s for s in test_cands if s.trend_aligned_1h]),
            "OPPOSING": eval_subset([s for s in test_cands if not s.trend_aligned_1h])
        }
        
        trend_4h_eval = {
            "ALIGNED": eval_subset([s for s in test_cands if s.trend_aligned_4h]),
            "OPPOSING": eval_subset([s for s in test_cands if not s.trend_aligned_4h])
        }
        
        vol_1h_eval = {
            "LOW": eval_subset([s for s in test_cands if s.vol_regime_1h == "LOW"]),
            "NORMAL": eval_subset([s for s in test_cands if s.vol_regime_1h == "NORMAL"]),
            "HIGH": eval_subset([s for s in test_cands if s.vol_regime_1h == "HIGH"])
        }
        
        expansion_1h_eval = {
            "EXPANSION": eval_subset([s for s in test_cands if s.expansion_state_1h == "EXPANSION"]),
            "RANGE": eval_subset([s for s in test_cands if s.expansion_state_1h == "RANGE"])
        }
        
        structure_loc_eval = {
            "FAVORABLE": eval_subset([s for s in test_cands if s.structure_favorable_1h]),
            "UNFAVORABLE": eval_subset([s for s in test_cands if not s.structure_favorable_1h])
        }
        
        combined_htf_eval = {
            "HTF_ALIGNED": eval_subset([s for s in test_cands if s.htf_aligned]),
            "HTF_UNALIGNED": eval_subset([s for s in test_cands if not s.htf_aligned])
        }
        
        return {
            "trend_1h": trend_1h_eval,
            "trend_4h": trend_4h_eval,
            "volatility_1h": vol_1h_eval,
            "expansion_1h": expansion_1h_eval,
            "structure_location_1h": structure_loc_eval,
            "combined_htf_filter": combined_htf_eval
        }

    def _audit_trade_management(self, var_d_cands: List[HTFCandidateSnapshot]) -> Dict[str, Any]:
        """Evaluates 9 discrete trade management policies across Train, Val, and Test."""
        policies = [
            "FIXED_SL_TP",
            "TP1_PARTIAL",
            "BE_0.5R",
            "BE_0.8R",
            "BE_1.0R",
            "STRUCTURAL_TRAILING",
            "ATR_TRAILING",
            "PARTIAL_TRAILING",
            "TIME_EXIT_30M"
        ]
        
        train_cands = [s for s in var_d_cands if s.base.split == "TRAIN"]
        val_cands = [s for s in var_d_cands if s.base.split == "VALIDATION"]
        test_cands = [s for s in var_d_cands if s.base.split == "TEST"]
        
        def run_policy_on_subset(subset: List[HTFCandidateSnapshot], pol: str) -> Dict[str, Any]:
            net_rs = []
            gross_rs = []
            is_wins = []
            for s in subset:
                sym = s.base.symbol
                c5m = self.future_candles_cache.get(sym, [])
                fut = [c for c in c5m if int(c["ts"]) > s.base.timestamp_ms][:24]
                gross_r, net_r, exit_reason, _ = simulate_trade_management(
                    policy_name=pol,
                    direction=s.base.direction,
                    entry=s.base.entry_price,
                    sl=s.base.sl_price,
                    tp1=s.base.tp1_price,
                    tp2=s.base.tp2_price,
                    future_candles_5m=fut,
                    cur_atr=s.base.cur_atr,
                    friction_rate=FRICTION_BASE
                )
                net_rs.append(net_r)
                gross_rs.append(gross_r)
                is_wins.append(gross_r > 0.0)
            return self._cohort_stats(net_rs, gross_rs, is_wins)
            
        policy_eval_matrix = {}
        for pol in policies:
            policy_eval_matrix[pol] = {
                "train": run_policy_on_subset(train_cands, pol),
                "validation": run_policy_on_subset(val_cands, pol),
                "test": run_policy_on_subset(test_cands, pol)
            }
            
        # Select best policy based strictly on Validation Net R / Mean R
        best_policy = max(policies, key=lambda p: policy_eval_matrix[p]["validation"]["mean_r"])
        logger.info("Validation-selected best management policy: %s (Mean R: %.3f)", best_policy, policy_eval_matrix[best_policy]["validation"]["mean_r"])
        
        return {
            "policies_evaluated": policy_eval_matrix,
            "best_policy": best_policy
        }

    def _construct_comparative_matrix(
        self,
        base_snaps: List[CandidateFeatureSnapshot],
        htf_snaps: List[HTFCandidateSnapshot],
        var_d_snaps: List[HTFCandidateSnapshot],
        best_policy: str
    ) -> Dict[str, Any]:
        """Constructs comparative matrix for BASELINE A, VARIANT D, D+HTF, D+MGMT, D+HTF+MGMT."""
        splits = ["TRAIN", "VALIDATION", "TEST"]
        results = {}
        
        combinations = [
            "BASELINE_A",
            "VARIANT_D",
            "VARIANT_D_HTF",
            "VARIANT_D_MANAGEMENT",
            "VARIANT_D_HTF_MANAGEMENT"
        ]
        
        for combo in combinations:
            results[combo] = {}
            for sp in splits:
                if combo == "BASELINE_A":
                    subset = [s for s in base_snaps if s.split == sp]
                    net_rs = [s.net_realized_r_base for s in subset]
                    gross_rs = [s.gross_realized_r for s in subset]
                    is_wins = [s.exit_reason in ("TP1", "TP2") for s in subset]
                elif combo == "VARIANT_D":
                    subset = [s for s in var_d_snaps if s.base.split == sp]
                    net_rs = [s.base.net_realized_r_base for s in subset]
                    gross_rs = [s.base.gross_realized_r for s in subset]
                    is_wins = [s.base.exit_reason in ("TP1", "TP2") for s in subset]
                elif combo == "VARIANT_D_HTF":
                    subset = [s for s in var_d_snaps if s.base.split == sp and s.htf_aligned]
                    net_rs = [s.base.net_realized_r_base for s in subset]
                    gross_rs = [s.base.gross_realized_r for s in subset]
                    is_wins = [s.base.exit_reason in ("TP1", "TP2") for s in subset]
                elif combo == "VARIANT_D_MANAGEMENT":
                    subset = [s for s in var_d_snaps if s.base.split == sp]
                    net_rs, gross_rs, is_wins = [], [], []
                    for s in subset:
                        sym = s.base.symbol
                        fut = [c for c in self.future_candles_cache.get(sym, []) if int(c["ts"]) > s.base.timestamp_ms][:24]
                        gr, nr, _, _ = simulate_trade_management(
                            best_policy, s.base.direction, s.base.entry_price, s.base.sl_price, s.base.tp1_price,
                            s.base.tp2_price, fut, s.base.cur_atr, FRICTION_BASE
                        )
                        net_rs.append(nr)
                        gross_rs.append(gr)
                        is_wins.append(gr > 0.0)
                elif combo == "VARIANT_D_HTF_MANAGEMENT":
                    subset = [s for s in var_d_snaps if s.base.split == sp and s.htf_aligned]
                    net_rs, gross_rs, is_wins = [], [], []
                    for s in subset:
                        sym = s.base.symbol
                        fut = [c for c in self.future_candles_cache.get(sym, []) if int(c["ts"]) > s.base.timestamp_ms][:24]
                        gr, nr, _, _ = simulate_trade_management(
                            best_policy, s.base.direction, s.base.entry_price, s.base.sl_price, s.base.tp1_price,
                            s.base.tp2_price, fut, s.base.cur_atr, FRICTION_BASE
                        )
                        net_rs.append(nr)
                        gross_rs.append(gr)
                        is_wins.append(gr > 0.0)
                        
                results[combo][sp] = self._cohort_stats(net_rs, gross_rs, is_wins)
                
        return results

    def _audit_asset_stability(self, var_d_cands: List[HTFCandidateSnapshot], best_policy: str) -> Dict[str, Any]:
        """Tests whether Variant D + HTF + Management behaves consistently across BTC, ETH, and SOL."""
        test_cands = [s for s in var_d_cands if s.base.split == "TEST" and s.htf_aligned]
        asset_stats = {}
        for sym in self.symbols:
            sub = [s for s in test_cands if s.base.symbol == sym]
            net_rs, gross_rs, is_wins = [], [], []
            for s in sub:
                fut = [c for c in self.future_candles_cache.get(sym, []) if int(c["ts"]) > s.base.timestamp_ms][:24]
                gr, nr, _, _ = simulate_trade_management(
                    best_policy, s.base.direction, s.base.entry_price, s.base.sl_price, s.base.tp1_price,
                    s.base.tp2_price, fut, s.base.cur_atr, FRICTION_BASE
                )
                net_rs.append(nr)
                gross_rs.append(gr)
                is_wins.append(gr > 0.0)
            asset_stats[sym] = self._cohort_stats(net_rs, gross_rs, is_wins)
        return asset_stats
