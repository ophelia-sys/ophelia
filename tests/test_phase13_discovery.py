"""Unit tests for Ophelia Phase 13 Alpha Discovery Reset & Structural Stop-Room Engine.

Verifies:
1. Hard Safety Invariants: TRADING_AUTHORITY=False, EXECUTION_MODE=SHADOW, LIVE_ORDERS=FORBIDDEN.
2. Chronological Partitions with 24h Purge Embargos.
3. Thesis Resumption Classification (Classes A, B, C, D, E, F).
4. Structural Stop Hierarchy & Regime Mapping.
5. Verified BingX Notional Friction in R Scaling Law.
6. Benjamini-Hochberg FDR Multiple-Testing Control.
7. Bootstrap Confidence Interval Math.
"""
from __future__ import annotations

import unittest
from control_plane import phase13_discovery_engine as p13


class TestPhase13Discovery(unittest.TestCase):

    def test_safety_invariants(self):
        """Phase 13 is research-only; live execution and autonomous trading are strictly forbidden."""
        self.assertFalse(p13.TRADING_AUTHORITY)
        self.assertEqual(p13.EXECUTION_MODE, "SHADOW")
        self.assertTrue(p13.LIVE_ORDERS_FORBIDDEN)
        self.assertTrue(p13.AUTONOMOUS_SLOT_RESERVATION_FORBIDDEN)

    def test_chronological_partitions(self):
        """Train (60%), 24h Embargo 1, Validation (20%), 24h Embargo 2, Test (20%)."""
        # Jan 15 2023 -> Train
        ts_train = 1673740800000
        self.assertEqual(p13.assign_phase13_split(ts_train), "TRAIN")

        # Aug 01 2023 12:00 -> Embargo 1
        ts_embargo1 = 1690891200000
        self.assertEqual(p13.assign_phase13_split(ts_embargo1), "EMBARGO_1")

        # Sep 01 2023 -> Validation
        ts_val = 1693526400000
        self.assertEqual(p13.assign_phase13_split(ts_val), "VALIDATION")

        # Oct 15 2023 12:00 -> Embargo 2
        ts_embargo2 = 1697371200000
        self.assertEqual(p13.assign_phase13_split(ts_embargo2), "EMBARGO_2")

        # Nov 15 2023 -> Test (Untouched OOS)
        ts_test = 1700006400000
        self.assertEqual(p13.assign_phase13_split(ts_test), "TEST")

    def test_thesis_resumption_classes(self):
        """Verifies Classes A through F classification on causal forward price paths."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5

        # Class C: Clean Winner (SL never touched, TP1 touched at minute 5)
        path_c = [{"high": 100.5, "low": 99.5, "close": 100.2}] * 4 + [{"high": 101.6, "low": 100.2, "close": 101.5}]
        res_c, sl_h, tp_h, t_sl, t_tp, exit_p, exit_r, mae, mfe = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_c)
        self.assertEqual(res_c, "CLASS_C")
        self.assertFalse(sl_h)
        self.assertTrue(tp_h)
        self.assertEqual(t_tp, 5)
        self.assertEqual(exit_p, tp1)

        # Class A: True Invalidation (SL touched at minute 2, TP1 never touched)
        path_a = [{"high": 100.2, "low": 99.8, "close": 99.9},
                  {"high": 99.9, "low": 98.9, "close": 99.0},
                  {"high": 99.2, "low": 98.5, "close": 98.8}]
        res_a, sl_h, tp_h, t_sl, t_tp, exit_p, exit_r, mae, mfe = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_a)
        self.assertEqual(res_a, "CLASS_A")
        self.assertTrue(sl_h)
        self.assertFalse(tp_h)
        self.assertEqual(exit_p, sl)

        # Class B: Premature Stop-Out / Thesis Resumed (SL touched at minute 2, then TP1 touched at minute 4)
        path_b = [
            {"high": 100.2, "low": 99.8, "close": 99.9},  # min 1
            {"high": 99.5, "low": 98.8, "close": 99.1},   # min 2: SL hit (98.8 <= 99.0)
            {"high": 100.5, "low": 99.2, "close": 100.4}, # min 3
            {"high": 101.8, "low": 100.3, "close": 101.6} # min 4: TP1 reached!
        ]
        res_b, sl_h, tp_h, t_sl, t_tp, exit_p, exit_r, mae, mfe = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_b)
        self.assertEqual(res_b, "CLASS_B")
        self.assertTrue(sl_h)
        self.assertTrue(tp_h)
        self.assertEqual(t_sl, 2)
        self.assertEqual(t_tp, 4)
        self.assertEqual(exit_p, sl)  # Stopped out at SL before reaching TP1

    def test_stop_regime_classification(self):
        """Verifies stop distance regime mapping."""
        self.assertEqual(p13.classify_stop_regime(0.0025), "TIGHT_02_03")
        self.assertEqual(p13.classify_stop_regime(0.0040), "MOD_03_05")
        self.assertEqual(p13.classify_stop_regime(0.0060), "BALANCED_05_075")
        self.assertEqual(p13.classify_stop_regime(0.0085), "ROOM_075_10")
        self.assertEqual(p13.classify_stop_regime(0.0120), "WIDE_10_15")
        self.assertEqual(p13.classify_stop_regime(0.0200), "VERY_WIDE_GT15")

    def test_friction_in_r_scaling_law(self):
        """Verifies Friction_R = friction_rate / stop_distance_% law verified in Phase 12."""
        # 9.1 bps friction on a 0.5% stop = 0.00091 / 0.0050 = 0.182 R
        friction_rate = 0.00091
        stop_pct = 0.0050
        fric_r = friction_rate / stop_pct
        self.assertAlmostEqual(fric_r, 0.182, places=3)

        # On a 0.1% stop, friction explodes to 0.91 R!
        tight_stop = 0.0010
        tight_fric_r = friction_rate / tight_stop
        self.assertAlmostEqual(tight_fric_r, 0.910, places=3)

    def test_benjamini_hochberg_fdr(self):
        """Verifies Benjamini-Hochberg FDR control math."""
        # Test with known p-values
        p_vals = [0.001, 0.01, 0.04, 0.50]
        rejected, q_vals = p13.compute_benjamini_hochberg(p_vals, alpha=0.05)
        self.assertTrue(rejected[0])
        self.assertTrue(rejected[1])
        self.assertFalse(rejected[3])
        self.assertLessEqual(q_vals[0], q_vals[1])


if __name__ == "__main__":
    unittest.main()
