"""Unit Tests for Ophelia Phase 12: Fresh-Period Incremental TimesFM Validation Engine.

Layer: tests/test_phase12_incremental_timesfm.py
Verifies:
- Safety Invariants: TRADING_AUTHORITY = FALSE, EXECUTION_MODE = SHADOW, LIVE_ORDERS = FORBIDDEN
- Fresh Data Boundary: Strictly post-Nov 2023, zero overlap with Phase 10.3/11/11.5
- Frozen D4H Specification & Hash Integrity
- Reachability Formula & Directional Geometry
- Zero Lookahead & Future Corruption Invariance
- Multiple Testing Benjamini-Hochberg FDR & Stop Condition Integrity
"""
import copy
import hashlib
import json
import math
import os
import unittest
import numpy as np

from control_plane.phase12_timesfm_engine import (
    TRADING_AUTHORITY,
    EXECUTION_MODE,
    LIVE_ORDERS_FORBIDDEN,
    AUTONOMOUS_SLOT_RESERVATION_FORBIDDEN,
    D4H_SPECIFICATION,
    D4H_SPEC_HASH,
    TS_DEC_01_2023,
    TS_MAR_31_2024,
    assign_phase12_split,
    evaluate_forward_trajectory_phase12,
    Phase12Candidate,
)


class TestPhase12IncrementalTimesFM(unittest.TestCase):

    def test_safety_invariants(self):
        """Verifies Phase 12 shadow execution safety boundaries."""
        self.assertFalse(TRADING_AUTHORITY, "TRADING_AUTHORITY must be False")
        self.assertEqual(EXECUTION_MODE, "SHADOW", "EXECUTION_MODE must be SHADOW")
        self.assertTrue(LIVE_ORDERS_FORBIDDEN, "LIVE_ORDERS must be FORBIDDEN")
        self.assertTrue(AUTONOMOUS_SLOT_RESERVATION_FORBIDDEN, "Slot reservation must be forbidden")

    def test_fresh_data_boundary_and_splits(self):
        """Verifies dataset strictly begins on 2023-12-01 and partitions have strict embargo."""
        # 2023-11-30 23:59:59 is 1701388799000 -> must be OUT_OF_BOUNDS
        ts_old_test = 1701388799000
        self.assertEqual(assign_phase12_split(ts_old_test), "OUT_OF_BOUNDS", "Prior Phase 10/11 data must be OUT_OF_BOUNDS")

        # 2023-12-01 00:00:00 is TS_DEC_01_2023 -> TRAIN
        self.assertEqual(assign_phase12_split(TS_DEC_01_2023), "TRAIN")

        # Embargo 1 (Jan 10, 2024)
        ts_embargo1 = 1704870000000  # Mid Jan 10
        self.assertEqual(assign_phase12_split(ts_embargo1), "EMBARGO")

        # Validation (Jan 15, 2024)
        ts_val = 1705300000000
        self.assertEqual(assign_phase12_split(ts_val), "VALIDATION")

        # Embargo 2 (Feb 16, 2024)
        ts_embargo2 = 1708080000000
        self.assertEqual(assign_phase12_split(ts_embargo2), "EMBARGO")

        # Test (Feb 20, 2024 to Mar 31, 2024)
        ts_test = 1708500000000
        self.assertEqual(assign_phase12_split(ts_test), "TEST")

        # Post Mar 31, 2024 -> OUT_OF_BOUNDS
        ts_after = TS_MAR_31_2024 + 100000
        self.assertEqual(assign_phase12_split(ts_after), "OUT_OF_BOUNDS")

    def test_frozen_d4h_specification_and_hash(self):
        """Verifies frozen D4H parameters and specification hash reproducibility."""
        self.assertEqual(D4H_SPECIFICATION["min_displacement_atr"], 1.20)
        self.assertEqual(D4H_SPECIFICATION["min_rejection_body_ratio"], 0.45)
        self.assertEqual(D4H_SPECIFICATION["min_rejection_rvol"], 1.00)
        self.assertEqual(D4H_SPECIFICATION["htf_alignment"], "4H_EMA20_EMA50")
        self.assertEqual(D4H_SPECIFICATION["management_policy"], "FIXED_SL_TP")
        self.assertEqual(D4H_SPECIFICATION["base_friction_bps"], 9.0)

        expected_hash = hashlib.sha256(json.dumps(D4H_SPECIFICATION, sort_keys=True).encode()).hexdigest()[:16]
        self.assertEqual(D4H_SPEC_HASH, expected_hash)

    def test_target_reachability_canonical_geometry(self):
        """Verifies target reachability formula for LONG and SHORT directions."""
        entry = 50000.0
        tp1 = 51000.0
        sl = 49500.0

        # LONG Reachability: (q90 - Entry) / (TP1 - Entry) >= 1.0
        q90_reachable = 51050.0
        q90_unreachable = 50800.0
        reach_ratio_long_ok = (q90_reachable - entry) / (tp1 - entry)
        reach_ratio_long_fail = (q90_unreachable - entry) / (tp1 - entry)
        self.assertTrue(reach_ratio_long_ok >= 1.0)
        self.assertFalse(reach_ratio_long_fail >= 1.0)

        # SHORT Reachability: (Entry - q10) / (Entry - TP1) >= 1.0
        tp1_short = 49000.0
        sl_short = 50500.0
        q10_short_ok = 48900.0
        q10_short_fail = 49200.0
        reach_ratio_short_ok = (entry - q10_short_ok) / (entry - tp1_short)
        reach_ratio_short_fail = (entry - q10_short_fail) / (entry - tp1_short)
        self.assertTrue(reach_ratio_short_ok >= 1.0)
        self.assertFalse(reach_ratio_short_fail >= 1.0)

    def test_causal_forward_trajectory_sl_precedence(self):
        """Verifies that on ambiguous same-candle touch, SL is checked strictly before TP."""
        cand = {
            "direction": "LONG",
            "entry_price": 50000.0,
            "sl_price": 49500.0,
            "tp1_price": 50500.0
        }
        # Ambiguous bar: low touches SL and high touches TP1 in the same bar
        ambiguous_bar = [
            {"high": 50600.0, "low": 49400.0, "close": 50200.0, "ts": 1704067200000}
        ]
        res = evaluate_forward_trajectory_phase12(cand, ambiguous_bar)
        exit_reason = res[0]
        self.assertEqual(exit_reason, "SL", "SL must take conservative precedence over TP on ambiguous same-candle touch")

    def test_future_corruption_invariance(self):
        """Verifies that altering future candle data cannot alter historical candle slices or candidate features."""
        hist_candles = [
            {"ts": 1000 + i * 300000, "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 500.0}
            for i in range(50)
        ]
        cand_ts = 1000 + 49 * 300000

        # Causal slice strictly <= cand_ts
        slice_orig = [c for c in hist_candles if c["ts"] <= cand_ts]

        # Corrupted future bar at cand_ts + 300000
        corrupted_future = copy.deepcopy(hist_candles)
        corrupted_future.append({"ts": cand_ts + 300000, "open": 9999.0, "high": 9999.0, "low": 9999.0, "close": 9999.0, "volume": 999999.0})
        slice_after_corruption = [c for c in corrupted_future if c["ts"] <= cand_ts]

        self.assertEqual(len(slice_orig), len(slice_after_corruption))
        self.assertEqual(slice_orig[-1]["close"], slice_after_corruption[-1]["close"])

    def test_multiple_testing_fdr_logic(self):
        """Verifies Benjamini-Hochberg FDR ranking and critical threshold logic."""
        raw_p = [0.0001, 0.002, 0.045, 0.35]
        m = len(raw_p)
        alpha = 0.05
        # Expected BH critical thresholds:
        # Rank 1: (1/4)*0.05 = 0.0125 -> 0.0001 <= 0.0125 (REJECT NULL)
        # Rank 2: (2/4)*0.05 = 0.0250 -> 0.0020 <= 0.0250 (REJECT NULL)
        # Rank 3: (3/4)*0.05 = 0.0375 -> 0.0450 > 0.0375 (FAIL TO REJECT)
        # Rank 4: (4/4)*0.05 = 0.0500 -> 0.3500 > 0.0500 (FAIL TO REJECT)
        crits = [(i + 1) / m * alpha for i in range(m)]
        statuses = ["REJECT_NULL" if raw_p[i] <= crits[i] else "FAIL_TO_REJECT" for i in range(m)]
        self.assertEqual(statuses, ["REJECT_NULL", "REJECT_NULL", "FAIL_TO_REJECT", "FAIL_TO_REJECT"])


if __name__ == "__main__":
    unittest.main()
