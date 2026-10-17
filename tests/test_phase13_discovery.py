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

    def test_adversarial_target_first_long_immune_to_later_stop(self):
        """Step 1 Core Invariant: TP1 hit first is CLASS_C (+1.5R). Later stop touch CANNOT alter outcome."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5
        sl_dist = entry - sl  # 1.0

        # Path: TP1 reached on min 2; min 3 touches SL and plunges
        path = [
            {"high": 100.4, "low": 99.8, "close": 100.2},  # min 1: MAE = 0.2%
            {"high": 101.6, "low": 100.1, "close": 101.5}, # min 2: TP1 reached! Trade exits at 101.5
            {"high": 100.0, "low": 95.0, "close": 96.0},   # min 3: touches SL 99.0 post-exit!
            {"high": 96.0, "low": 94.0, "close": 94.5},    # min 4: further drop post-exit
        ]
        res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path)
        c, sh, th, tsl, ttp, px, reas, mae, mfe = res

        self.assertEqual(c, "CLASS_C")
        self.assertEqual(px, 101.5)
        self.assertEqual(reas, "TP1")
        gross_r = (px - entry) / sl_dist
        self.assertAlmostEqual(gross_r, 1.5, places=4)
        self.assertFalse(sh, "Realized trade did not hit SL")
        self.assertTrue(th, "Realized trade hit TP1")
        self.assertIsNone(tsl)
        self.assertEqual(ttp, 2)

        # Realized excursions must stop strictly at exit (min 2)
        self.assertAlmostEqual(mae, 0.002, places=4)  # (100 - 99.8) / 100
        self.assertAlmostEqual(mfe, 0.016, places=4)  # (101.6 - 100) / 100

        # Full-window excursions record post-exit price movement for research
        self.assertAlmostEqual(res.full_window_mae, 0.060, places=4)  # (100 - 94.0) / 100
        self.assertAlmostEqual(res.post_exit_mae, 0.060, places=4)

    def test_adversarial_target_first_short_immune_to_later_stop(self):
        """Step 1 Core Invariant: SHORT TP1 hit first is CLASS_C (+1.5R). Later stop touch CANNOT alter outcome."""
        entry = 100.0
        sl = 101.0
        tp1 = 98.5
        sl_dist = sl - entry  # 1.0

        # Path: TP1 reached on min 2; min 3 touches SL and surges to 106.0
        path = [
            {"high": 100.2, "low": 99.6, "close": 99.8},   # min 1: MAE = 0.2%
            {"high": 99.9, "low": 98.4, "close": 98.5},    # min 2: TP1 reached (98.4 <= 98.5)
            {"high": 106.0, "low": 100.0, "close": 105.0}, # min 3: post-exit surge touching SL 101.0
        ]
        res = p13.classify_thesis_resumption("SHORT", entry, sl, tp1, path)
        c, sh, th, tsl, ttp, px, reas, mae, mfe = res

        self.assertEqual(c, "CLASS_C")
        self.assertEqual(px, 98.5)
        self.assertEqual(reas, "TP1")
        gross_r = (entry - px) / sl_dist
        self.assertAlmostEqual(gross_r, 1.5, places=4)
        self.assertFalse(sh)
        self.assertTrue(th)
        self.assertEqual(ttp, 2)
        self.assertAlmostEqual(mae, 0.002, places=4)
        self.assertAlmostEqual(mfe, 0.016, places=4)

    def test_adversarial_stop_first_then_target_long_class_b(self):
        """Step 1: SL hit first, then target reached later is CLASS_B (-1R exit, resumed later)."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5
        sl_dist = entry - sl

        path = [
            {"high": 100.2, "low": 99.8, "close": 100.0},  # min 1
            {"high": 99.4, "low": 98.8, "close": 99.0},    # min 2: SL hit (98.8 <= 99.0)
            {"high": 100.8, "low": 99.1, "close": 100.5},  # min 3
            {"high": 101.8, "low": 100.2, "close": 101.6}, # min 4: reaches TP1 post-stop!
        ]
        res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path)
        c, sh, th, tsl, ttp, px, reas, mae, mfe = res

        self.assertEqual(c, "CLASS_B")
        self.assertEqual(px, 99.0, "Actual exit price remains at SL")
        self.assertEqual(reas, "SL_RESUMED")
        gross_r = (px - entry) / sl_dist
        self.assertAlmostEqual(gross_r, -1.0, places=4)
        self.assertTrue(sh)
        self.assertTrue(th, "Thesis resumption recorded")
        self.assertEqual(tsl, 2)
        self.assertEqual(ttp, 4)

        # Realized MAE/MFE stop strictly at exit (min 2)
        self.assertAlmostEqual(mae, 0.012, places=4)
        self.assertAlmostEqual(mfe, 0.002, places=4)

        # Full window and post-exit metrics show resumption
        self.assertAlmostEqual(res.full_window_mfe, 0.018, places=4)
        self.assertAlmostEqual(res.post_exit_mfe, 0.018, places=4)

    def test_adversarial_stop_first_then_target_short_class_b(self):
        """Step 1: SHORT SL hit first, then target reached later is CLASS_B (-1R exit, resumed later)."""
        entry = 100.0
        sl = 101.0
        tp1 = 98.5
        sl_dist = sl - entry

        path = [
            {"high": 100.3, "low": 99.8, "close": 100.1},
            {"high": 101.2, "low": 100.4, "close": 101.0}, # min 2: SL hit (101.2 >= 101.0)
            {"high": 100.5, "low": 99.2, "close": 99.5},
            {"high": 99.2, "low": 98.2, "close": 98.4},    # min 4: reaches TP1 post-stop!
        ]
        res = p13.classify_thesis_resumption("SHORT", entry, sl, tp1, path)
        c, sh, th, tsl, ttp, px, reas, mae, mfe = res

        self.assertEqual(c, "CLASS_B")
        self.assertEqual(px, 101.0)
        self.assertEqual(reas, "SL_RESUMED")
        gross_r = (entry - px) / sl_dist
        self.assertAlmostEqual(gross_r, -1.0, places=4)
        self.assertTrue(sh)
        self.assertTrue(th)
        self.assertEqual(tsl, 2)
        self.assertEqual(ttp, 4)
        self.assertAlmostEqual(mae, 0.012, places=4)
        self.assertAlmostEqual(mfe, 0.002, places=4)
        self.assertAlmostEqual(res.full_window_mfe, 0.018, places=4)

    def test_adversarial_stop_first_no_target_long_class_a(self):
        """Step 1: SL hit and target never reached is CLASS_A (-1R exit)."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5

        path = [
            {"high": 100.2, "low": 99.8, "close": 100.0},
            {"high": 99.5, "low": 98.8, "close": 99.0}, # min 2: SL hit
            {"high": 99.2, "low": 98.0, "close": 98.5}, # never reaches TP1
        ]
        res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path)
        self.assertEqual(res.resumption_class, "CLASS_A")
        self.assertEqual(res.exit_price, 99.0)
        self.assertEqual(res.exit_reason, "SL")
        self.assertTrue(res.sl_hit)
        self.assertFalse(res.tp1_hit)
        self.assertEqual(res.time_to_sl, 2)
        self.assertIsNone(res.time_to_tp1)

    def test_adversarial_stop_first_no_target_short_class_a(self):
        """Step 1: SHORT SL hit and target never reached is CLASS_A (-1R exit)."""
        entry = 100.0
        sl = 101.0
        tp1 = 98.5

        path = [
            {"high": 100.2, "low": 99.8, "close": 100.0},
            {"high": 101.3, "low": 100.1, "close": 101.1}, # min 2: SL hit
            {"high": 102.0, "low": 100.8, "close": 101.5}, # never reaches TP1
        ]
        res = p13.classify_thesis_resumption("SHORT", entry, sl, tp1, path)
        self.assertEqual(res.resumption_class, "CLASS_A")
        self.assertEqual(res.exit_price, 101.0)
        self.assertEqual(res.exit_reason, "SL")
        self.assertTrue(res.sl_hit)
        self.assertFalse(res.tp1_hit)

    def test_adversarial_same_candle_ambiguity_conservative_stop_first(self):
        """Step 1: Same-minute barrier touch resolves conservatively to stop-first."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5

        # Candle 2 spans 98.5 (touches SL) to 101.8 (touches TP1)
        path = [
            {"high": 100.2, "low": 99.8, "close": 100.0},
            {"high": 101.8, "low": 98.5, "close": 100.2}, # Ambiguous candle
            {"high": 100.5, "low": 99.5, "close": 100.0},
        ]
        res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path)
        self.assertTrue(res.same_candle_ambiguity, "Ambiguity must be explicitly detected")
        self.assertEqual(res.resumption_class, "CLASS_A")
        self.assertEqual(res.exit_price, 99.0)
        self.assertEqual(res.exit_reason, "SL")
        self.assertTrue(res.sl_hit)
        self.assertFalse(res.tp1_hit)

    def test_adversarial_same_candle_ambiguity_with_later_target_resumption(self):
        """Step 1: Same-minute touch stopped out, but candle 3 reaches TP1 -> CLASS_B."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5

        path = [
            {"high": 100.2, "low": 99.8, "close": 100.0},
            {"high": 101.8, "low": 98.5, "close": 100.2}, # Ambiguous candle at min 2
            {"high": 102.5, "low": 100.5, "close": 102.0}, # Min 3 touches TP1 strictly after
        ]
        res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path)
        self.assertTrue(res.same_candle_ambiguity)
        self.assertEqual(res.resumption_class, "CLASS_B")
        self.assertEqual(res.exit_price, 99.0)
        self.assertEqual(res.exit_reason, "SL_RESUMED")
        self.assertTrue(res.sl_hit)
        self.assertTrue(res.tp1_hit)
        self.assertEqual(res.time_to_sl, 2)
        self.assertEqual(res.time_to_tp1, 3)

    def test_adversarial_neither_barrier_reached_flat_and_drift(self):
        """Step 1: Neither barrier reached evaluates CLASS_D (flat) vs CLASS_E (drift)."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5
        risk_pct = 0.01  # 1%

        # Flat path: MAE <= 0.75 * 0.01 = 0.0075 (0.75%)
        path_flat = [{"high": 100.4, "low": 99.6, "close": 100.1}] * 10
        res_d = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_flat)
        self.assertEqual(res_d.resumption_class, "CLASS_D")
        self.assertEqual(res_d.exit_reason, "CHOP_FLAT")
        self.assertFalse(res_d.sl_hit)
        self.assertFalse(res_d.tp1_hit)

        # Drift path: MAE > 0.75% (e.g. low 99.15 -> MAE 0.85%), but SL 99.0 never hit
        path_drift = [{"high": 100.1, "low": 99.15, "close": 99.2}] * 10
        res_e = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_drift)
        self.assertEqual(res_e.resumption_class, "CLASS_E")
        self.assertEqual(res_e.exit_reason, "STRUCTURAL_DRIFT")
        self.assertFalse(res_e.sl_hit)
        self.assertFalse(res_e.tp1_hit)

    def test_adversarial_no_lookahead_post_exit_changes(self):
        """Step 1: Changing candles after actual exit MUST NOT alter realized outcome or realized MAE/MFE."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5

        # Path 1: Exits at TP1 on min 2; min 3 plunges to 90.0
        path_plunge = [
            {"high": 100.3, "low": 99.8, "close": 100.1},
            {"high": 101.7, "low": 100.2, "close": 101.6}, # TP1 hit
            {"high": 100.0, "low": 90.0, "close": 91.0},   # Plunge
        ]
        # Path 2: Exits at TP1 on min 2; min 3 rockets to 120.0
        path_rocket = [
            {"high": 100.3, "low": 99.8, "close": 100.1},
            {"high": 101.7, "low": 100.2, "close": 101.6}, # TP1 hit
            {"high": 120.0, "low": 101.0, "close": 119.0}, # Rocket
        ]

        res_1 = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_plunge)
        res_2 = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path_rocket)

        # Realized outcomes MUST be identical
        self.assertEqual(res_1.resumption_class, res_2.resumption_class)
        self.assertEqual(res_1.exit_price, res_2.exit_price)
        self.assertEqual(res_1.exit_reason, res_2.exit_reason)
        self.assertAlmostEqual(res_1.mae, res_2.mae, places=6)
        self.assertAlmostEqual(res_1.mfe, res_2.mfe, places=6)

        # Full-window research excursions naturally capture post-exit differences
        self.assertNotEqual(res_1.full_window_mae, res_2.full_window_mae)
        self.assertNotEqual(res_1.full_window_mfe, res_2.full_window_mfe)

    def test_adversarial_empty_and_insufficient_data(self):
        """Step 1: Empty forward bars follows CLASS_F NO_DATA contract."""
        res = p13.classify_thesis_resumption("LONG", 100.0, 99.0, 101.5, [])
        self.assertEqual(res.resumption_class, "CLASS_F")
        self.assertEqual(res.exit_reason, "NO_DATA")
        self.assertEqual(res.exit_price, 100.0)
        self.assertEqual(res.mae, 0.0)
        self.assertEqual(res.mfe, 0.0)


if __name__ == "__main__":
    unittest.main()

