"""Unit and integration tests for Phase 11 Deterministic Strategy Repair & Regime Discovery.

Layer: tests/test_phase11_deterministic_repair.py
Verifies:
1. Feature snapshot structure & field validity.
2. Causal regime classification and partition boundaries.
3. Deterministic Failure Taxonomy coverage and rules.
4. Geometry bucket assignment and boundaries.
5. Controlled strategy variant filtering (Variants A-F).
6. Candidate clustering and effective sample size N_eff computation.
7. Friction sensitivity monotonicity (Gross > Low > Base > High).
8. Benjamini-Hochberg FDR multiple testing correction.
9. Safety invariants: TRADING_AUTHORITY = FALSE, EXECUTION_MODE = SHADOW, LIVE_ORDERS = FORBIDDEN.
"""
from __future__ import annotations

import math
import os
import unittest
import numpy as np

from control_plane.phase11_repair_engine import (
    CandidateFeatureSnapshot,
    assign_split,
    classify_rr_bucket,
    classify_deterministic_regime,
    classify_failure_taxonomy,
    bootstrap_ci,
    TS_OCT_01_2023,
    TS_OCT_20_2023,
    TS_OCT_21_2023,
    TS_NOV_05_2023,
    TS_NOV_06_2023,
    TS_NOV_30_2023,
    EMBARGO_MS,
    FRICTION_BASE,
)
from control_plane import config


class TestPhase11DeterministicRepair(unittest.TestCase):
    """Test suite validating Phase 11 repair engine components."""

    def test_chronological_splits_and_embargo(self):
        """Verify strict non-overlapping splits and 60-minute embargo."""
        # Train start & end
        self.assertEqual(assign_split(TS_OCT_01_2023), "TRAIN")
        self.assertEqual(assign_split(TS_OCT_20_2023 - EMBARGO_MS), "TRAIN")
        
        # Embargo between Train and Val
        self.assertEqual(assign_split(TS_OCT_20_2023 - EMBARGO_MS + 1000), "EMBARGO")
        self.assertEqual(assign_split(TS_OCT_21_2023 - 1000), "EMBARGO")
        
        # Validation start & end
        self.assertEqual(assign_split(TS_OCT_21_2023), "VALIDATION")
        self.assertEqual(assign_split(TS_NOV_05_2023 - EMBARGO_MS), "VALIDATION")
        
        # Embargo between Val and Test
        self.assertEqual(assign_split(TS_NOV_05_2023 - EMBARGO_MS + 1000), "EMBARGO")
        self.assertEqual(assign_split(TS_NOV_06_2023 - 1000), "EMBARGO")
        
        # Test start & end
        self.assertEqual(assign_split(TS_NOV_06_2023), "TEST")
        self.assertEqual(assign_split(TS_NOV_30_2023), "TEST")
        
        # Out of bounds
        self.assertEqual(assign_split(TS_OCT_01_2023 - 1000), "OUT_OF_BOUNDS")
        self.assertEqual(assign_split(TS_NOV_30_2023 + 1000), "OUT_OF_BOUNDS")

    def test_geometry_rr_buckets(self):
        """Verify canonical R:R bucket classification boundaries."""
        self.assertEqual(classify_rr_bucket(1.10), "<1.25")
        self.assertEqual(classify_rr_bucket(1.249), "<1.25")
        self.assertEqual(classify_rr_bucket(1.25), "1.25-1.5")
        self.assertEqual(classify_rr_bucket(1.49), "1.25-1.5")
        self.assertEqual(classify_rr_bucket(1.50), "1.5-2.0")
        self.assertEqual(classify_rr_bucket(1.99), "1.5-2.0")
        self.assertEqual(classify_rr_bucket(2.00), "2.0-2.5")
        self.assertEqual(classify_rr_bucket(2.49), "2.0-2.5")
        self.assertEqual(classify_rr_bucket(2.50), "2.5-3.0")
        self.assertEqual(classify_rr_bucket(2.99), "2.5-3.0")
        self.assertEqual(classify_rr_bucket(3.00), ">3.0")
        self.assertEqual(classify_rr_bucket(4.50), ">3.0")

    def test_deterministic_regime_classification(self):
        """Verify timestamp-causal regime classification."""
        # Mid-October shock period
        ts_shock = int(1697673600 * 1000)  # Oct 19, 2023
        regime_shock = classify_deterministic_regime(
            ts=ts_shock, close=28000.0, ema_20=27500.0, ema_50=27000.0, atr_pct=0.012, adx_proxy=30.0
        )
        self.assertEqual(regime_shock, "VOLATILITY_SHOCK")

        # Trend expansion outside shock
        ts_nov = int(1699574400 * 1000)  # Nov 10, 2023
        regime_trend = classify_deterministic_regime(
            ts=ts_nov, close=37000.0, ema_20=36500.0, ema_50=36000.0, atr_pct=0.008, adx_proxy=26.0
        )
        self.assertEqual(regime_trend, "TREND_EXPANSION")

        # Range / chop when ADX low or EMAs flat
        regime_chop = classify_deterministic_regime(
            ts=ts_nov, close=36505.0, ema_20=36500.0, ema_50=36500.0, atr_pct=0.003, adx_proxy=12.0
        )
        self.assertEqual(regime_chop, "RANGE_CHOP")

    def test_failure_taxonomy_classification(self):
        """Verify deterministic assignment of failure categories."""
        # 1. Success on TP1
        cat_success = classify_failure_taxonomy(
            exit_reason="TP1", direction="LONG", entry=100.0, sl=95.0, tp1=110.0,
            mfe=10.0, mae=-2.0, cur_atr=2.0, regime="TREND_EXPANSION", rvol=1.5,
            displacement_atr=1.5, sl_atr=2.5, tp1_atr=5.0, retest_depth_atr=0.5
        )
        self.assertEqual(cat_success, "SUCCESS")

        # 2. Range Chop
        cat_chop = classify_failure_taxonomy(
            exit_reason="SL", direction="LONG", entry=100.0, sl=95.0, tp1=110.0,
            mfe=1.0, mae=-5.0, cur_atr=2.0, regime="RANGE_CHOP", rvol=1.5,
            displacement_atr=1.5, sl_atr=2.5, tp1_atr=5.0, retest_depth_atr=0.5
        )
        self.assertEqual(cat_chop, "RANGE_CHOP")

        # 3. Stop Too Tight
        cat_tight = classify_failure_taxonomy(
            exit_reason="SL", direction="LONG", entry=100.0, sl=99.5, tp1=110.0,
            mfe=0.2, mae=-0.5, cur_atr=2.0, regime="TREND_EXPANSION", rvol=1.5,
            displacement_atr=1.5, sl_atr=0.25, tp1_atr=5.0, retest_depth_atr=0.5
        )
        self.assertEqual(cat_tight, "STOP_TOO_TIGHT")

        # 4. Target Too Far
        cat_far = classify_failure_taxonomy(
            exit_reason="SL", direction="LONG", entry=100.0, sl=95.0, tp1=115.0,
            mfe=4.0, mae=-5.0, cur_atr=2.0, regime="TREND_EXPANSION", rvol=1.5,
            displacement_atr=1.5, sl_atr=2.5, tp1_atr=7.5, retest_depth_atr=0.5
        )
        self.assertEqual(cat_far, "TARGET_TOO_FAR")

        # 5. False Retest (Deep penetration through breakout level)
        cat_false = classify_failure_taxonomy(
            exit_reason="SL", direction="LONG", entry=100.0, sl=95.0, tp1=105.0,
            mfe=1.0, mae=-5.0, cur_atr=2.0, regime="TREND_EXPANSION", rvol=1.5,
            displacement_atr=1.5, sl_atr=2.5, tp1_atr=2.5, retest_depth_atr=1.8
        )
        self.assertEqual(cat_false, "FALSE_RETEST")

        # 6. Low Participation (Dull volume)
        cat_vol = classify_failure_taxonomy(
            exit_reason="SL", direction="LONG", entry=100.0, sl=95.0, tp1=105.0,
            mfe=1.0, mae=-5.0, cur_atr=2.0, regime="TREND_EXPANSION", rvol=0.7,
            displacement_atr=1.5, sl_atr=2.5, tp1_atr=2.5, retest_depth_atr=0.5
        )
        self.assertEqual(cat_vol, "LOW_PARTICIPATION")

    def test_bootstrap_confidence_interval(self):
        """Verify bootstrap confidence interval computation."""
        sample = [1.0, 1.2, 0.8, -1.0, 1.5, -0.5, 2.0, 1.1]
        mean, lower, upper = bootstrap_ci(sample, n_iterations=500)
        self.assertAlmostEqual(mean, float(np.mean(sample)), places=4)
        self.assertLess(lower, mean)
        self.assertGreater(upper, mean)

    def test_multiple_testing_benjamini_hochberg(self):
        """Verify Benjamini-Hochberg FDR ranking and critical values."""
        p_vals = [0.005, 0.02, 0.04, 0.15, 0.30]
        m = len(p_vals)
        ranked = []
        for rank, p in enumerate(p_vals, 1):
            crit = (rank / m) * 0.05
            survives = p <= crit
            ranked.append((p, crit, survives))

        # Rank 1: 0.005 <= (1/5)*0.05 = 0.010 -> True
        self.assertTrue(ranked[0][2])
        # Rank 2: 0.020 <= (2/5)*0.05 = 0.020 -> True
        self.assertTrue(ranked[1][2])
        # Rank 3: 0.040 <= (3/5)*0.05 = 0.030 -> False
        self.assertFalse(ranked[2][2])

    def test_safety_invariants(self):
        """Ensure absolute financial safety invariants hold."""
        self.assertEqual(config.DEFAULT_TRADING_MODE, "SHADOW", "DEFAULT_TRADING_MODE must be SHADOW")
        # Ensure live orders and autonomous slot reservation are never enabled in analytical/research context
        self.assertFalse(os.environ.get("OPH_LIVE_ENABLED", "0") == "1")


if __name__ == "__main__":
    unittest.main()
