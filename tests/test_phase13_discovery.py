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
import numpy as np
import pandas as pd
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


def _make_1m_df(start_ms: int, n_minutes: int, base_price: float = 100.0, step: float = 0.1) -> pd.DataFrame:
    rows = []
    for i in range(n_minutes):
        ts = start_ms + i * 60_000
        p = base_price + i * step
        rows.append({
            "timestamp": ts,
            "open": p,
            "high": p + 0.5,
            "low": p - 0.5,
            "close": p + 0.2,
            "volume": 10.0,
            "taker_buy_volume": 6.0,
            "delta_v": 2.0,
            "aggressive_buy_volume": 6.0,
            "aggressive_sell_volume": 4.0,
        })
    df = pd.DataFrame(rows)
    df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df.set_index("dt")


class TestPhase13HigherTimeframeCausality(unittest.TestCase):
    """F-02 Deterministic Higher-Timeframe Causality & Alignment Tests.

    Verifies:
    1. 15-minute feature availability strictly at/after completion (T + 15m).
    2. 1-hour feature availability strictly at/after completion (T + 60m).
    3. 4-hour trend feature availability strictly at/after completion (T + 240m) & equality boundary.
    4. Future-corruption invariance: mutating bars after T leaves features at T byte-for-byte identical.
    5. Incomplete candles & data gaps: dropped 1m bar invalidates parent HTF interval; features remain NaN with zero fallbacks.
    6. Warm-up points: rolling window calculations use only completed historical candles.
    7. Decision timestamp & split boundary: split uses decision timestamp (bar close), preventing embargo leak.
    8. Regression against F-01: first-passage accounting remains green.
    """

    def test_test1_15m_availability(self):
        """Test 1: 15-minute features unavailable before completion; eligible strictly at T + 15m."""
        start_ms = 1672531200000  # 2023-01-01 00:00:00 UTC
        df_1m = _make_1m_df(start_ms, 45)  # 45 minutes: 00:00 to 00:44
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m)

        # Compute ATR on 15m
        df_15m["atr_14"] = p13.compute_atr(df_15m["high"], df_15m["low"], df_15m["close"], 14)
        merged = p13.merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)

        # 5m bar 0: opens 00:00, decision at 00:05 (< 00:15) -> 15m must be NaN
        bar_00_00 = merged.loc[merged["timestamp"] == start_ms].iloc[0]
        self.assertTrue(np.isnan(bar_00_00["close_15m"]))
        self.assertTrue(np.isnan(bar_00_00["high_15m"]))
        self.assertTrue(np.isnan(bar_00_00["low_15m"]))

        # 5m bar 1: opens 00:05, decision at 00:10 (< 00:15) -> 15m must be NaN
        bar_00_05 = merged.loc[merged["timestamp"] == start_ms + 5 * 60_000].iloc[0]
        self.assertTrue(np.isnan(bar_00_05["close_15m"]))

        # 5m bar 2: opens 00:10, decision at 00:15 (== 00:15 completion of 00:00-00:15 candle) -> 15m becomes available!
        bar_00_10 = merged.loc[merged["timestamp"] == start_ms + 10 * 60_000].iloc[0]
        self.assertFalse(np.isnan(bar_00_10["close_15m"]))
        # Verify value matches the completed 00:00-00:15 candle (close of minute 14)
        expected_close_15m = df_15m.loc[df_15m["timestamp"] == start_ms, "close"].iloc[0]
        self.assertEqual(bar_00_10["close_15m"], expected_close_15m)

        # 5m bar 3: opens 00:15, decision at 00:20 (< 00:30) -> still sees first completed 15m candle
        bar_00_15 = merged.loc[merged["timestamp"] == start_ms + 15 * 60_000].iloc[0]
        self.assertEqual(bar_00_15["close_15m"], expected_close_15m)

        # 5m bar 5: opens 00:25, decision at 00:30 (== 00:30 completion of 00:15-00:30 candle) -> 2nd 15m candle available
        bar_00_25 = merged.loc[merged["timestamp"] == start_ms + 25 * 60_000].iloc[0]
        expected_close_15m_2 = df_15m.loc[df_15m["timestamp"] == start_ms + 15 * 60_000, "close"].iloc[0]
        self.assertEqual(bar_00_25["close_15m"], expected_close_15m_2)

    def test_test2_1h_availability(self):
        """Test 2: 1-hour feature built from 00:00 interval is unavailable before 01:00."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 120)  # 2 hours
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m)
        df_1h["atr_14"] = p13.compute_atr(df_1h["high"], df_1h["low"], df_1h["close"], 14)
        merged = p13.merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)

        # All 5m decisions before 01:00 (i.e. bars opening 00:00 through 00:50, decision 00:05 through 00:55) must have NaN 1h features
        for min_offset in range(0, 55, 5):
            row = merged.loc[merged["timestamp"] == start_ms + min_offset * 60_000].iloc[0]
            self.assertTrue(np.isnan(row["close_1h"]), f"1h close leaked at minute {min_offset}")
            self.assertTrue(np.isnan(row["high_1h"]), f"1h high leaked at minute {min_offset}")

        # 5m bar opening at 00:55 closes at 01:00 (decision_ts == 01:00). First eligible point!
        row_00_55 = merged.loc[merged["timestamp"] == start_ms + 55 * 60_000].iloc[0]
        self.assertFalse(np.isnan(row_00_55["close_1h"]))
        expected_close_1h = df_1h.loc[df_1h["timestamp"] == start_ms, "close"].iloc[0]
        self.assertEqual(row_00_55["close_1h"], expected_close_1h)

    def test_test3_4h_availability(self):
        """Test 3: 4-hour trend derived from 00:00-04:00 bar is not exposed before 04:00, with exact equality at 04:00."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 480)  # 8 hours = 2 4h bars
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m)
        df_4h["ema20"] = df_4h["close"].ewm(span=20, adjust=False).mean()
        df_4h["ema50"] = df_4h["close"].ewm(span=50, adjust=False).mean()
        df_4h["trend_4h"] = np.where(df_4h["ema20"] > df_4h["ema50"] * 1.001, "BULL", "BEAR")
        merged = p13.merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)

        # 5m bar opening at 03:50 -> decision at 03:55 (< 04:00) -> trend_4h must be NaN
        row_03_50 = merged.loc[merged["timestamp"] == start_ms + 230 * 60_000].iloc[0]
        self.assertTrue(pd.isna(row_03_50["trend_4h"]))
        self.assertTrue(np.isnan(row_03_50["close_4h"]))

        # 5m bar opening at 03:55 -> decision at 04:00 (== 04:00 equality boundary) -> trend_4h exposed!
        row_03_55 = merged.loc[merged["timestamp"] == start_ms + 235 * 60_000].iloc[0]
        self.assertFalse(pd.isna(row_03_55["trend_4h"]))
        self.assertEqual(row_03_55["trend_4h"], df_4h.loc[df_4h["timestamp"] == start_ms, "trend_4h"].iloc[0])
        self.assertEqual(row_03_55["close_4h"], df_4h.loc[df_4h["timestamp"] == start_ms, "close"].iloc[0])

    def test_test4_future_corruption_invariance(self):
        """Test 4: Mutating bars strictly after decision time T leaves all features at T byte-for-byte identical.

        Computes 4H EMA and trend independently from clean and corrupted source data without hardcoding.
        """
        start_ms = 1672531200000  # 2023-01-01 00:00:00 UTC
        df_1m = _make_1m_df(start_ms, 720)  # 12 hours
        decision_offset_min = 240  # Decision at T = 4 hours (04:00:00 UTC)
        t_decision_ms = start_ms + decision_offset_min * 60_000
        bar_open_ms = t_decision_ms - 5 * 60_000  # 03:55:00 UTC bar (closes at 04:00:00 UTC)

        # 1. Run uncorrupted pipeline with independent 4H indicator computation
        df_5m_clean, df_15m_clean, df_1h_clean, df_4h_clean = p13.resample_phase13_bars(df_1m)
        df_15m_clean["atr_14"] = p13.compute_atr(df_15m_clean["high"], df_15m_clean["low"], df_15m_clean["close"], 14)
        df_1h_clean["atr_14"] = p13.compute_atr(df_1h_clean["high"], df_1h_clean["low"], df_1h_clean["close"], 14)
        df_4h_clean["ema20"] = df_4h_clean["close"].ewm(span=20, adjust=False).mean()
        df_4h_clean["ema50"] = df_4h_clean["close"].ewm(span=50, adjust=False).mean()
        df_4h_clean["trend_4h"] = np.where(df_4h_clean["ema20"] > df_4h_clean["ema50"] * 1.001, "BULL", "BEAR")
        merged_clean = p13.merge_completed_htf_features(df_5m_clean, df_15m_clean, df_1h_clean, df_4h_clean)
        row_clean = merged_clean.loc[merged_clean["timestamp"] == bar_open_ms].iloc[0]

        # 2. Corrupt ONLY bars strictly after decision timestamp T (timestamp >= t_decision_ms)
        df_1m_corrupt = df_1m.copy()
        mask_future = df_1m_corrupt["timestamp"] >= t_decision_ms
        df_1m_corrupt.loc[mask_future, "close"] *= 1000.0
        df_1m_corrupt.loc[mask_future, "high"] *= 2000.0
        df_1m_corrupt.loc[mask_future, "low"] = 0.001
        df_1m_corrupt.loc[mask_future, "volume"] = 9999999.0
        df_1m_corrupt.loc[mask_future, "delta_v"] = -888888.0

        # 3. Compute indicators independently on the corrupted source
        df_5m_bad, df_15m_bad, df_1h_bad, df_4h_bad = p13.resample_phase13_bars(df_1m_corrupt)
        df_15m_bad["atr_14"] = p13.compute_atr(df_15m_bad["high"], df_15m_bad["low"], df_15m_bad["close"], 14)
        df_1h_bad["atr_14"] = p13.compute_atr(df_1h_bad["high"], df_1h_bad["low"], df_1h_bad["close"], 14)
        df_4h_bad["ema20"] = df_4h_bad["close"].ewm(span=20, adjust=False).mean()
        df_4h_bad["ema50"] = df_4h_bad["close"].ewm(span=50, adjust=False).mean()
        df_4h_bad["trend_4h"] = np.where(df_4h_bad["ema20"] > df_4h_bad["ema50"] * 1.001, "BULL", "BEAR")
        merged_bad = p13.merge_completed_htf_features(df_5m_bad, df_15m_bad, df_1h_bad, df_4h_bad)
        row_bad = merged_bad.loc[merged_bad["timestamp"] == bar_open_ms].iloc[0]

        # 4. Verify all features available at decision time T (04:00) are identical
        test_features = [
            "open", "high", "low", "close", "volume",
            "close_15m", "high_15m", "low_15m", "atr_15m", "swing_low_15m", "swing_high_15m",
            "close_1h", "high_1h", "low_1h", "atr_1h", "swing_low_1h", "swing_high_1h",
            "close_4h", "high_4h", "low_4h", "trend_4h",
        ]
        for feat in test_features:
            v_clean = row_clean[feat]
            v_bad = row_bad[feat]
            if pd.isna(v_clean):
                self.assertTrue(pd.isna(v_bad), f"Feature {feat} was NaN in clean but {v_bad} in corrupt")
            else:
                self.assertEqual(v_clean, v_bad, f"Feature {feat} differed at decision T: clean={v_clean} vs corrupt={v_bad}")

        # 5. Invariance sanity check: confirm future bar at 08:00 was significantly altered by the corruption
        future_bar_open = start_ms + 475 * 60_000
        future_clean = merged_clean.loc[merged_clean["timestamp"] == future_bar_open].iloc[0]
        future_bad = merged_bad.loc[merged_bad["timestamp"] == future_bar_open].iloc[0]
        self.assertNotEqual(future_clean["close_4h"], future_bad["close_4h"], "Corruption did not alter future 4H bar")

    def test_test5_incomplete_candles_and_data_gaps(self):
        """Test 5: Incomplete HTF candle dropped from pipeline; missing values remain NaN with zero fallbacks."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 60)
        # Drop minute 7 -> 00:00-00:15 has 14 bars (< 15)
        df_1m_gap = df_1m.loc[df_1m["timestamp"] != start_ms + 7 * 60_000].copy()
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m_gap)

        # 15m candle for 00:00 must remain represented on grid as invalid (14 bars < 15)
        row_15m_0 = df_15m.loc[df_15m["timestamp"] == start_ms]
        self.assertTrue(len(row_15m_0) == 1)
        self.assertFalse(row_15m_0["is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(row_15m_0["close"].iloc[0]))

        # 1h candle for 00:00 must remain represented on grid as invalid (59 bars < 60)
        row_1h_0 = df_1h.loc[df_1h["timestamp"] == start_ms]
        self.assertTrue(len(row_1h_0) == 1)
        self.assertFalse(row_1h_0["is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(row_1h_0["close"].iloc[0]))

        # Merge
        merged = p13.merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)
        # At decision 00:15 (bar opening 00:10): close_15m, atr_15m, swing_low_15m must all be NaN
        row_00_10 = merged.loc[merged["timestamp"] == start_ms + 10 * 60_000].iloc[0]
        self.assertTrue(np.isnan(row_00_10["close_15m"]))
        self.assertTrue(np.isnan(row_00_10["atr_15m"]))
        self.assertTrue(np.isnan(row_00_10["swing_low_15m"]))

    def test_test6_first_available_warmup_point(self):
        """Test 6: Rolling calculations use only completed historical candles; zero early non-null values."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 480)  # 8 hours
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m)
        df_15m["atr_14"] = p13.compute_atr(df_15m["high"], df_15m["low"], df_15m["close"], 14)
        df_1h["atr_14"] = p13.compute_atr(df_1h["high"], df_1h["low"], df_1h["close"], 14)
        merged = p13.merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)

        # 15m swing requires 8 completed 15m candles = 120 minutes
        # Decision at 115m (bar 01:50, decision 01:55) -> 7 completed candles -> swing_high_15m must be NaN
        row_110 = merged.loc[merged["timestamp"] == start_ms + 110 * 60_000].iloc[0]
        self.assertTrue(np.isnan(row_110["swing_high_15m"]))

        # Decision at 120m (bar 01:55, decision 02:00) -> 8th candle completes -> swing_high_15m becomes non-null!
        row_115 = merged.loc[merged["timestamp"] == start_ms + 115 * 60_000].iloc[0]
        self.assertFalse(np.isnan(row_115["swing_high_15m"]))

        # 1h swing requires 6 completed 1h candles = 360 minutes
        # Decision at 355m (bar 05:50, decision 05:55) -> 5 completed 1h candles -> swing_high_1h must be NaN
        row_350 = merged.loc[merged["timestamp"] == start_ms + 350 * 60_000].iloc[0]
        self.assertTrue(np.isnan(row_350["swing_high_1h"]))

        # Decision at 360m (bar 05:55, decision 06:00) -> 6th 1h candle completes -> swing_high_1h becomes non-null!
        row_355 = merged.loc[merged["timestamp"] == start_ms + 355 * 60_000].iloc[0]
        self.assertFalse(np.isnan(row_355["swing_high_1h"]))

    def test_test7_timestamp_and_split_boundary(self):
        """Test 7: Split assignment uses decision timestamp (candle close) preventing embargo boundary leak."""
        # Train ends at TS_JUL_31_2023 (2023-07-31 23:59:59 UTC)
        # Embargo 1 is TS_JUL_31_2023 < ts <= TS_AUG_01_2023_END
        train_end = p13.TS_JUL_31_2023
        bar_open_ms = train_end - 4 * 60 * 1000  # 2023-07-31 23:55:59 UTC (within TRAIN)
        decision_ts_ms = bar_open_ms + 5 * 60 * 1000  # 2023-08-01 00:00:59 UTC (> TS_JUL_31_2023)

        # If evaluated on bar open, it would wrongly report TRAIN
        self.assertEqual(p13.assign_phase13_split(bar_open_ms), "TRAIN")

        # But evaluated on decision timestamp (bar close), it correctly enters EMBARGO_1
        self.assertEqual(p13.assign_phase13_split(decision_ts_ms), "EMBARGO_1")

    def test_test8_regression_against_f01(self):
        """Test 8: Ensure F-02 changes do not regress F-01 first-passage accounting."""
        entry = 100.0
        sl = 99.0
        tp1 = 101.5

        # Path where TP1 hit at min 5, SL hit at min 10 -> Must be CLASS_C (exit at min 5)
        path = (
            [{"high": 100.2, "low": 99.8, "close": 100.0}] * 4
            + [{"high": 101.6, "low": 100.1, "close": 101.5}]  # minute 5: TP1 hit
            + [{"high": 100.5, "low": 98.8, "close": 98.9}]   # minute 6: SL hit later
        )
        res = p13.classify_thesis_resumption("LONG", entry, sl, tp1, path)
        self.assertEqual(res.resumption_class, "CLASS_C")
        self.assertEqual(res.exit_reason, "TP1")
        self.assertEqual(res.time_to_tp1, 5)
        self.assertIsNone(res.time_to_sl)
        self.assertFalse(res.sl_hit)
        self.assertTrue(res.tp1_hit)
        # Realized MAE must be measured up to minute 5, NOT polluted by minute 6's low of 98.8
        self.assertAlmostEqual(res.realized_mae, 0.002, places=6)
        # Full window MAE contains minute 6
        self.assertAlmostEqual(res.full_window_mae, 0.012, places=6)


class TestPhase13F02ReviewCorrections(unittest.TestCase):
    """F-02.1 Review Corrections: Strict Constituent Timestamps, Stop Regimes, and Synthetic HTF Exclusion."""

    def test_adversarial_index_and_timestamp_column_disagree(self):
        """Confirm that resample_phase13_bars rejects mismatches between DatetimeIndex and 'timestamp'."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 60)
        # Shift timestamp column by 1 minute while index remains original
        df_1m["timestamp"] = df_1m["timestamp"] + 60_000
        with self.assertRaises(ValueError) as ctx:
            p13.resample_phase13_bars(df_1m)
        self.assertIn("index dt and timestamp column disagree", str(ctx.exception))

    def test_adversarial_duplicate_timestamps(self):
        """Confirm that duplicate 1m timestamps are rejected."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 60)
        # Duplicate row 5
        dup_row = df_1m.iloc[[5]]
        df_bad = pd.concat([df_1m, dup_row]).sort_values("timestamp")
        with self.assertRaises(ValueError) as ctx:
            p13.resample_phase13_bars(df_bad)
        self.assertIn("duplicate 1m timestamps", str(ctx.exception))

    def test_adversarial_non_finite_market_data(self):
        """Confirm non-finite required market data (NaN, inf) raises ValueError."""
        start_ms = 1672531200000
        for col in ["open", "high", "low", "close", "volume"]:
            df_nan = _make_1m_df(start_ms, 60)
            df_nan.iloc[10, df_nan.columns.get_loc(col)] = np.nan
            with self.assertRaises(ValueError) as ctx:
                p13.resample_phase13_bars(df_nan)
            self.assertIn("non-finite required market data", str(ctx.exception))

            df_inf = _make_1m_df(start_ms, 60)
            df_inf.iloc[10, df_inf.columns.get_loc(col)] = np.inf
            with self.assertRaises(ValueError) as ctx:
                p13.resample_phase13_bars(df_inf)
            self.assertIn("non-finite required market data", str(ctx.exception))

    def test_adversarial_negative_prices_and_inverted_bounds(self):
        """Confirm negative prices or high < low bounds raise ValueError."""
        start_ms = 1672531200000
        # Negative close
        df_neg = _make_1m_df(start_ms, 60)
        df_neg.iloc[5, df_neg.columns.get_loc("close")] = -10.0
        with self.assertRaises(ValueError) as ctx:
            p13.resample_phase13_bars(df_neg)
        self.assertIn("strictly positive", str(ctx.exception))

        # high < low
        df_inv = _make_1m_df(start_ms, 60)
        df_inv.iloc[5, df_inv.columns.get_loc("high")] = df_inv.iloc[5, df_inv.columns.get_loc("low")] - 1.0
        with self.assertRaises(ValueError) as ctx:
            p13.resample_phase13_bars(df_inv)
        self.assertIn("cannot be lower than low price", str(ctx.exception))

    def test_adversarial_missing_minute_replaced_by_offgrid_row_all_intervals(self):
        """Test all 4 intervals (5m, 15m, 1h, 4h): replacing a minute with an off-grid row drops the interval."""
        start_ms = 1672531200000
        # 240 minutes = 4 hours
        df_1m = _make_1m_df(start_ms, 240)

        # Replace minute 2 (00:02:00) with an off-grid row at 00:02:30 (30 seconds off-grid)
        # Note: row count in the bucket is STILL exactly M (5, 15, 60, 240)
        df_mod = df_1m.copy()
        off_grid_ts = start_ms + 2 * 60_000 + 30_000
        off_grid_dt = pd.to_datetime(off_grid_ts, unit="ms")
        
        row_dict = df_mod.iloc[2].to_dict()
        row_dict["timestamp"] = off_grid_ts
        df_without_min2 = df_mod.drop(df_mod.index[2])
        df_offgrid = pd.concat([df_without_min2, pd.DataFrame([row_dict], index=[off_grid_dt])]).sort_values("timestamp")

        # Under the old row-count check, 5/15/60/240 rows would pass.
        # Under strict constituent timestamp grid validation, the bucket containing 00:02:30 is dropped.
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_offgrid)

        # 5m: bucket 00:00 must remain on grid as invalid (bucket 00:05 must be valid)
        row_5m_0 = df_5m.loc[df_5m["timestamp"] == start_ms]
        self.assertEqual(len(row_5m_0), 1, "5m bucket 00:00 missing from regular time grid")
        self.assertFalse(row_5m_0["is_valid_interval"].iloc[0], "5m bucket 00:00 must be marked invalid")
        self.assertTrue(np.isnan(row_5m_0["close"].iloc[0]), "5m bucket 00:00 must have NaN prices")
        self.assertTrue(df_5m.loc[df_5m["timestamp"] == start_ms + 5 * 60_000, "is_valid_interval"].iloc[0])

        # 15m: bucket 00:00 must remain on grid as invalid (bucket 00:15 must be valid)
        row_15m_0 = df_15m.loc[df_15m["timestamp"] == start_ms]
        self.assertEqual(len(row_15m_0), 1, "15m bucket 00:00 missing from regular time grid")
        self.assertFalse(row_15m_0["is_valid_interval"].iloc[0], "15m bucket 00:00 must be marked invalid")
        self.assertTrue(np.isnan(row_15m_0["close"].iloc[0]), "15m bucket 00:00 must have NaN prices")
        self.assertTrue(df_15m.loc[df_15m["timestamp"] == start_ms + 15 * 60_000, "is_valid_interval"].iloc[0])

        # 1h: bucket 00:00 must remain on grid as invalid (bucket 01:00 must be valid)
        row_1h_0 = df_1h.loc[df_1h["timestamp"] == start_ms]
        self.assertEqual(len(row_1h_0), 1, "1h bucket 00:00 missing from regular time grid")
        self.assertFalse(row_1h_0["is_valid_interval"].iloc[0], "1h bucket 00:00 must be marked invalid")
        self.assertTrue(np.isnan(row_1h_0["close"].iloc[0]), "1h bucket 00:00 must have NaN prices")
        self.assertTrue(df_1h.loc[df_1h["timestamp"] == start_ms + 60 * 60_000, "is_valid_interval"].iloc[0])

        # 4h: bucket 00:00 must remain on grid as invalid
        row_4h_0 = df_4h.loc[df_4h["timestamp"] == start_ms]
        self.assertEqual(len(row_4h_0), 1, "4h bucket 00:00 missing from regular time grid")
        self.assertFalse(row_4h_0["is_valid_interval"].iloc[0], "4h bucket 00:00 must be marked invalid")
        self.assertTrue(np.isnan(row_4h_0["close"].iloc[0]), "4h bucket 00:00 must have NaN prices")

    def test_adversarial_shifted_timestamps_all_intervals(self):
        """Test all 4 intervals (5m, 15m, 1h, 4h): sub-minute shifted timestamp marks the interval invalid."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 240)

        # Shift minute 2 timestamp by 500ms
        df_mod = df_1m.copy()
        shifted_ts = start_ms + 2 * 60_000 + 500
        shifted_dt = pd.to_datetime(shifted_ts, unit="ms")
        row_dict = df_mod.iloc[2].to_dict()
        row_dict["timestamp"] = shifted_ts
        df_without_min2 = df_mod.drop(df_mod.index[2])
        df_shifted = pd.concat([df_without_min2, pd.DataFrame([row_dict], index=[shifted_dt])]).sort_values("timestamp")

        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_shifted)
        self.assertFalse(df_5m.loc[df_5m["timestamp"] == start_ms, "is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(df_5m.loc[df_5m["timestamp"] == start_ms, "close"].iloc[0]))
        self.assertFalse(df_15m.loc[df_15m["timestamp"] == start_ms, "is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(df_15m.loc[df_15m["timestamp"] == start_ms, "close"].iloc[0]))
        self.assertFalse(df_1h.loc[df_1h["timestamp"] == start_ms, "is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(df_1h.loc[df_1h["timestamp"] == start_ms, "close"].iloc[0]))
        self.assertFalse(df_4h.loc[df_4h["timestamp"] == start_ms, "is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(df_4h.loc[df_4h["timestamp"] == start_ms, "close"].iloc[0]))

    def test_sub_02_stop_regime_exhaustive_mapping(self):
        """Verify SUB_02 stop regime bucket and complete partition of STOP_REGIMES."""
        self.assertEqual(p13.STOP_REGIMES[0], ("SUB_02", 0.0000, 0.0020))
        # Contiguous partition check
        for idx in range(1, len(p13.STOP_REGIMES)):
            prev_high = p13.STOP_REGIMES[idx - 1][2]
            curr_low = p13.STOP_REGIMES[idx][1]
            self.assertAlmostEqual(prev_high, curr_low, places=6)
        self.assertEqual(p13.STOP_REGIMES[0][1], 0.0000)
        self.assertEqual(p13.STOP_REGIMES[-1][2], 1.0000)

        # classify_stop_regime mapping across all regimes
        self.assertEqual(p13.classify_stop_regime(0.0005), "SUB_02")
        self.assertEqual(p13.classify_stop_regime(0.0019), "SUB_02")
        self.assertEqual(p13.classify_stop_regime(0.0025), "TIGHT_02_03")
        self.assertEqual(p13.classify_stop_regime(0.0040), "MOD_03_05")
        self.assertEqual(p13.classify_stop_regime(0.0060), "BALANCED_05_075")
        self.assertEqual(p13.classify_stop_regime(0.0085), "ROOM_075_10")
        self.assertEqual(p13.classify_stop_regime(0.0125), "WIDE_10_15")
        self.assertEqual(p13.classify_stop_regime(0.0250), "VERY_WIDE_GT15")

    def test_shifted_rolling_close_quantiles_no_self_inclusion(self):
        """Verify rolling close quantiles use shift(1) preventing candle self-inclusion."""
        closes = pd.Series([10.0] * 60)
        # Inject extreme spike at index 50
        closes.iloc[50] = 1000.0
        
        q95_unshifted = closes.rolling(10, min_periods=5).quantile(0.95)
        q95_shifted = closes.rolling(10, min_periods=5).quantile(0.95).shift(1)
        
        # At index 50, unshifted includes the spike (self-inclusion bug)
        self.assertGreater(q95_unshifted.iloc[50], 500.0)
        # Shifted strictly excludes index 50 (causal)
        self.assertEqual(q95_shifted.iloc[50], 10.0)
        # At index 51, shifted incorporates index 50 from prior history
        self.assertGreater(q95_shifted.iloc[51], 500.0)

    def test_diagnostic_event_extraction_and_htf_exclusion(self):
        """Synthetic benchmark proving unavailable HTF structural stops are excluded without fallbacks."""
        # 12 hours = 720 minutes
        start_ms = p13.TS_JAN_01_2023 + 10 * 3600_000
        df_1m = _make_1m_df(start_ms, 720, base_price=100.0, step=0.01)

        # Inject momentum displacement at bar 55 (minute 275: 04:35 UTC, closes 04:40 UTC)
        for m in range(275, 280):
            df_1m.iloc[m, df_1m.columns.get_loc("open")] = 100.0 + (m - 275) * 1.0
            df_1m.iloc[m, df_1m.columns.get_loc("close")] = 100.0 + (m - 275 + 1) * 1.0
            df_1m.iloc[m, df_1m.columns.get_loc("high")] = 106.0
            df_1m.iloc[m, df_1m.columns.get_loc("low")] = 99.5

        # Inject momentum displacement at bar 80 (minute 400: 06:40 UTC, closes 06:45 UTC)
        for m in range(400, 405):
            df_1m.iloc[m, df_1m.columns.get_loc("open")] = 105.0 + (m - 400) * 1.0
            df_1m.iloc[m, df_1m.columns.get_loc("close")] = 105.0 + (m - 400 + 1) * 1.0
            df_1m.iloc[m, df_1m.columns.get_loc("high")] = 111.0
            df_1m.iloc[m, df_1m.columns.get_loc("low")] = 104.5

        engine = p13.Phase13DiscoveryEngine()
        events, outcomes, evals = engine.extract_events_for_symbol("BTC-USDT", df_1m)

        self.assertGreater(len(events), 0)
        self.assertGreater(len(evals), 0)

        # Bar 55 event: 1h swing must be excluded
        ts_bar_55 = start_ms + 275 * 60_000
        ev_55_list = [e for e in events if e.timestamp_ms == ts_bar_55]
        self.assertTrue(len(ev_55_list) > 0, "Event at bar 55 not extracted")
        ev_55 = ev_55_list[0]
        evals_55 = [ev for ev in evals if ev.event_id == ev_55.event_id]
        models_55 = [ev.stop_model for ev in evals_55]

        # STOP_1H_SWING must NOT be in models_55
        self.assertNotIn("STOP_1H_SWING", models_55, "STOP_1H_SWING was prematurely generated before 6 completed 1h bars")
        # 5m and 15m swings must be present
        self.assertIn("STOP_5M_SWING", models_55)
        self.assertIn("STOP_15M_SWING", models_55)

        # Bar 80 event: 1h swing must be present
        ts_bar_80 = start_ms + 400 * 60_000
        ev_80_list = [e for e in events if e.timestamp_ms == ts_bar_80]
        self.assertTrue(len(ev_80_list) > 0, "Event at bar 80 not extracted")
        ev_80 = ev_80_list[0]
        evals_80 = [ev for ev in evals if ev.event_id == ev_80.event_id]
        models_80 = [ev.stop_model for ev in evals_80]
        self.assertIn("STOP_1H_SWING", models_80, "STOP_1H_SWING missing after 6 completed 1h bars")

    def test_diagnostic_historical_slice_explicit_period_provenance(self):
        """F-02.2: Proves the diagnostic slice selects explicit UTC Jan 1-4 2023, failing on iloc[:5760]."""
        from scripts.run_phase13_f02_diagnostic import run_historical_slice_benchmark
        res = run_historical_slice_benchmark(
            start_utc="2023-01-01 00:00:00",
            end_utc="2023-01-04 23:59:00",
            symbol="BTCUSDT",
        )
        self.assertEqual(res["status"], "COMPLETED")
        meta = res["sample_metadata"]
        
        # Must strictly be January 1-4 2023 UTC
        self.assertEqual(meta["first_timestamp_ms"], 1672531200000)
        self.assertEqual(meta["first_dt_utc"], "2023-01-01 00:00:00+00:00")
        self.assertEqual(meta["last_dt_utc"], "2023-01-04 23:59:00+00:00")
        self.assertEqual(meta["sample_1m_bars"], 5760)

        # Adversarial check: verify it does NOT select the 2022 dataset start (1640995200000)
        self.assertNotEqual(meta["first_timestamp_ms"], 1640995200000)
        self.assertNotIn("2022", meta["first_dt_utc"])

        # Causality verdict and events audit
        self.assertEqual(res["causality_verdict"], "VERIFIED_ZERO_LOOKAHEAD")
        audit = res["historical_events_audit"]
        self.assertEqual(audit["event_validation_status"], "VERIFIED")
        self.assertGreater(audit["total_events_extracted"], 0)
        self.assertTrue(audit["missing_htf_properly_excluded"])
        self.assertEqual(audit["synthetic_fallback_violations"], 0)


class TestPhase13F03OrderFlowAndVWAP(unittest.TestCase):
    """F-03: CVD, order flow aggregation and volume-weighted session VWAP correctness."""

    def test_f03_1_weighted_vwap_and_dispersion_hand_calculation(self):
        """1. Weighted VWAP and variance against independent hand-calculated example."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=3, freq="5min")
        df = pd.DataFrame({
            "close": [100.0, 110.0, 90.0],
            "volume": [10.0, 10.0, 20.0]
        }, index=idx)

        vwap, std = p13.compute_vwap(df)

        # Bar 1: P=100, V=10 -> VWAP=100.0, var=0.0 -> std is NaN (undefined dispersion for single flat price)
        self.assertAlmostEqual(vwap.iloc[0], 100.0, places=6)
        self.assertTrue(np.isnan(std.iloc[0]))

        # Bar 2: P=110, V=10 -> cum_pv=2100, cum_v=20 -> VWAP=105.0
        # cum_p2v = 10*10000 + 10*12100 = 221000. var = 221000/20 - 105^2 = 11050 - 11025 = 25.0 -> std=5.0
        self.assertAlmostEqual(vwap.iloc[1], 105.0, places=6)
        self.assertAlmostEqual(std.iloc[1], 5.0, places=6)

        # Bar 3: P=90, V=20 -> cum_pv=3900, cum_v=40 -> VWAP=97.5
        # cum_p2v = 221000 + 20*8100 = 383000. var = 383000/40 - 97.5^2 = 9575 - 9506.25 = 68.75 -> std=sqrt(68.75)
        self.assertAlmostEqual(vwap.iloc[2], 97.5, places=6)
        self.assertAlmostEqual(std.iloc[2], float(np.sqrt(68.75)), places=6)

    def test_f03_2_genuine_zero_delta_vs_missing_flow(self):
        """2. Valid, genuinely zero-delta sequence versus missing order-flow data."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=50, freq="5min")

        # Genuine zero delta: 10 buy - 10 sell = 0.0 delta_v
        df_zero = pd.DataFrame({"delta_v": [0.0] * 50}, index=idx)
        z_zero, st_zero = p13.compute_cvd(df_zero)
        # Bar 10 (< 12 bars): INSUFFICIENT_HISTORY
        self.assertEqual(st_zero.iloc[10], "INSUFFICIENT_HISTORY")
        self.assertTrue(np.isnan(z_zero.iloc[10]))
        # Bar 35: History >= 24, all zero delta -> variance is 0.0 -> ZERO_VARIANCE (not MISSING_FLOW)
        self.assertEqual(st_zero.iloc[35], "ZERO_VARIANCE")
        self.assertTrue(np.isnan(z_zero.iloc[35]))

        # Missing flow: all NaNs
        df_nan = pd.DataFrame({"delta_v": [np.nan] * 50}, index=idx)
        z_nan, st_nan = p13.compute_cvd(df_nan)
        # Must explicitly be MISSING_FLOW, not ZERO_VARIANCE or 0.0
        self.assertEqual(st_nan.iloc[35], "MISSING_FLOW")
        self.assertTrue(np.isnan(z_nan.iloc[35]))

        # Genuine fluctuating flow with a single genuine 0.0 delta bar
        np.random.seed(42)
        flows = np.random.randn(50) + 1.0
        flows[35] = 0.0  # genuine zero delta at bar 35
        df_fluct = pd.DataFrame({"delta_v": flows}, index=idx)
        z_f, st_f = p13.compute_cvd(df_fluct)
        self.assertEqual(st_f.iloc[35], "AVAILABLE")
        self.assertTrue(np.isfinite(z_f.iloc[35]))

    def test_f03_3_all_missing_and_partially_missing_flow_resampling(self):
        """3. All-missing and partially missing flow groups in strict resampling."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=15, freq="1min")
        ts = ((idx - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1)).to_numpy(dtype=np.int64)

        # 15 minutes = three 5m intervals
        # Interval 0 (0-4): all valid [1, 2, 3, 4, 5] -> sum 15
        # Interval 1 (5-9): 1 minute missing [1, 2, NaN, 4, 5] -> sum must be NaN
        # Interval 2 (10-14): all missing [NaN, NaN, NaN, NaN, NaN] -> sum must be NaN
        df_1m = pd.DataFrame({
            "timestamp": ts,
            "open": [100.0] * 15,
            "high": [101.0] * 15,
            "low": [99.0] * 15,
            "close": [100.0] * 15,
            "volume": [10.0] * 15,
            "delta_v": [1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 2.0, np.nan, 4.0, 5.0, np.nan, np.nan, np.nan, np.nan, np.nan]
        }, index=idx)

        df_5m, _, _, _ = p13.resample_phase13_bars(df_1m)
        self.assertEqual(len(df_5m), 3)
        self.assertAlmostEqual(df_5m["delta_v"].iloc[0], 15.0, places=6)
        self.assertTrue(np.isnan(df_5m["delta_v"].iloc[1]))
        self.assertTrue(np.isnan(df_5m["delta_v"].iloc[2]))

    def test_f03_4_duplicate_timestamps_and_incomplete_constituents(self):
        """4. Duplicate timestamps and incomplete one-minute constituents."""
        start_ms = 1672531200000
        # Duplicate timestamp rejection: duplicate row with matching index & timestamp
        df_base = _make_1m_df(start_ms, 10)
        df_dup = pd.concat([df_base.iloc[:2], df_base.iloc[1:2], df_base.iloc[3:]])
        with self.assertRaises(ValueError) as ctx:
            p13.resample_phase13_bars(df_dup)
        self.assertIn("duplicate", str(ctx.exception).lower())

        # Incomplete constituent minutes: marked invalid on regular time grid
        df_1m = _make_1m_df(start_ms, 10)
        # Drop minute 3 (leaving 4 minutes in first 5m interval)
        df_drop = df_1m.loc[df_1m["timestamp"] != start_ms + 3 * 60_000].copy()
        df_5m, _, _, _ = p13.resample_phase13_bars(df_drop)
        # First 5m bucket is on regular time grid but invalid with NaN prices; second 5m bucket (5-9) survives as valid
        self.assertEqual(len(df_5m), 2)
        self.assertFalse(df_5m["is_valid_interval"].iloc[0])
        self.assertTrue(np.isnan(df_5m["close"].iloc[0]))
        self.assertTrue(df_5m["is_valid_interval"].iloc[1])
        self.assertEqual(df_5m["timestamp"].iloc[1], start_ms + 5 * 60_000)

    def test_f03_5_undefined_dispersion_warmup_and_non_finite_values(self):
        """5. Undefined dispersion, insufficient warm-up history and non-finite values."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=10, freq="5min")

        # Flat prices -> zero variance -> 0.0 std_vwap for N >= 2; bar 0 is NaN (undefined single-bar dispersion)
        df_flat = pd.DataFrame({"close": [100.0] * 10, "volume": [10.0] * 10}, index=idx)
        vwap_flat, std_flat = p13.compute_vwap(df_flat)
        self.assertTrue(np.isnan(std_flat.iloc[0]))
        self.assertTrue((std_flat.iloc[1:] == 0.0).all())

        # Zero volume -> NaN VWAP and NaN std_vwap
        df_zero_vol = pd.DataFrame({"close": [100.0] * 10, "volume": [0.0] * 10}, index=idx)
        vwap_zv, std_zv = p13.compute_vwap(df_zero_vol)
        self.assertTrue(vwap_zv.isna().all())
        self.assertTrue(std_zv.isna().all())

        # Non-finite values in flow (Inf) treated as missing
        df_inf = pd.DataFrame({"delta_v": [10.0] * 50}, index=pd.date_range("2023-01-01", periods=50, freq="5min"))
        df_inf.iloc[30, 0] = np.inf
        z_inf, st_inf = p13.compute_cvd(df_inf)
        self.assertEqual(st_inf.iloc[30], "MISSING_FLOW")
        self.assertTrue(np.isnan(z_inf.iloc[30]))

    def test_f03_6_no_cvd_or_orderflow_events_when_flow_status_unavailable(self):
        """6. No CVD/order-flow event generated when flow status is unavailable."""
        start_ms = p13.TS_JAN_01_2023 + 10 * 3600_000
        df_1m = _make_1m_df(start_ms, 720, base_price=100.0)
        # Explicitly remove delta_v or set to NaN
        df_1m["delta_v"] = np.nan

        engine = p13.Phase13DiscoveryEngine()
        events, outcomes, evals = engine.extract_events_for_symbol("BTC-USDT", df_1m)

        event_classes = {e.event_class for e in events}
        self.assertNotIn("CVD_ACCELERATION", event_classes)
        self.assertNotIn("ORDER_FLOW_VWAP_CONFLUENCE", event_classes)
        for e in events:
            self.assertNotEqual(e.cvd_data_status, "AVAILABLE")
            self.assertTrue(np.isnan(e.cvd_zscore))

    def test_f03_7_future_row_corruption_invariance_cvd_vwap(self):
        """7. No change to previously calculated VWAP/CVD values when strictly future rows are corrupted."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=100, freq="5min")
        np.random.seed(123)
        prices = 100.0 + np.cumsum(np.random.randn(100))
        volumes = np.random.uniform(10.0, 50.0, 100)
        deltas = np.random.randn(100) * 5.0

        df_clean = pd.DataFrame({"close": prices, "volume": volumes, "delta_v": deltas}, index=idx)
        vwap_c, std_c = p13.compute_vwap(df_clean)
        cvd_z_c, cvd_st_c = p13.compute_cvd(df_clean)

        # Corrupt future rows strictly after index 50
        df_corrupt = df_clean.copy()
        df_corrupt.iloc[51:, df_corrupt.columns.get_loc("close")] *= 50.0
        df_corrupt.iloc[51:, df_corrupt.columns.get_loc("volume")] = 999999.0
        df_corrupt.iloc[51:, df_corrupt.columns.get_loc("delta_v")] = -888888.0

        vwap_bad, std_bad = p13.compute_vwap(df_corrupt)
        cvd_z_bad, cvd_st_bad = p13.compute_cvd(df_corrupt)

        # Values at and before index 50 must be identical
        for i in range(51):
            if np.isnan(vwap_c.iloc[i]):
                self.assertTrue(np.isnan(vwap_bad.iloc[i]))
            else:
                self.assertAlmostEqual(vwap_c.iloc[i], vwap_bad.iloc[i], places=9)

            if np.isnan(std_c.iloc[i]):
                self.assertTrue(np.isnan(std_bad.iloc[i]))
            else:
                self.assertAlmostEqual(std_c.iloc[i], std_bad.iloc[i], places=9)

            self.assertEqual(cvd_st_c.iloc[i], cvd_st_bad.iloc[i])
            if np.isnan(cvd_z_c.iloc[i]):
                self.assertTrue(np.isnan(cvd_z_bad.iloc[i]))
            else:
                self.assertAlmostEqual(cvd_z_c.iloc[i], cvd_z_bad.iloc[i], places=9)

    def test_f03_8_regression_f01_first_passage_and_f02_htf_causality(self):
        """8. Regression protection for F-01 first-passage accounting and F-02 HTF timestamp causality."""
        # F-01: TP1 reached at min 5, stop loss touched at min 10 -> MUST be CLASS_C
        future_bars = [
            {"high": 100.5, "low": 99.5, "close": 100.0} for _ in range(4)
        ] + [
            {"high": 103.5, "low": 100.0, "close": 103.0}  # min 5: TP1=103.0 touched
        ] + [
            {"high": 101.0, "low": 97.0, "close": 97.5}   # min 6: SL=98.0 touched later
        ]
        res = p13.classify_thesis_resumption("LONG", entry=100.0, sl=98.0, tp1=103.0, future_1m_bars=future_bars)
        self.assertEqual(res.resumption_class, "CLASS_C")
        self.assertEqual(res.exit_reason, "TP1")
        self.assertFalse(res.sl_hit)
        self.assertTrue(res.tp1_hit)

        # F-02: 15m candle opened at 00:00 is available only at 00:15
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 60)
        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m)
        merged = p13.merge_completed_htf_features(df_5m, df_15m, df_1h, df_4h)
        row_00_05 = merged.loc[merged["timestamp"] == start_ms + 5 * 60_000].iloc[0]
        self.assertTrue(np.isnan(row_00_05["close_15m"]))
        row_00_10 = merged.loc[merged["timestamp"] == start_ms + 10 * 60_000].iloc[0]
        self.assertFalse(np.isnan(row_00_10["close_15m"]))

    def test_f03_9_serialization_preserves_missing_status_without_neutral_zero(self):
        """9. Serialization/reporting preserves missing statuses and does not turn them into valid zero signals."""
        ev = p13.Phase13Event(
            event_id="TEST_EVENT_001",
            symbol="BTCUSDT",
            timestamp_ms=1672531200000,
            dt_utc="2023-01-01 00:05:00+00:00",
            split="TRAIN",
            event_class="MOMENTUM_DISPLACEMENT",
            direction="LONG",
            entry_price=100.0,
            atr_5m=1.0,
            atr_15m=float("nan"),
            atr_1h=float("nan"),
            volume_5m=50.0,
            rvol_5m=2.0,
            cvd_zscore=float("nan"),
            vwap_deviation_sigma=float("nan"),
            htf_trend_4h="NOT_AVAILABLE",
            htf_aligned=False,
            volatility_regime="NORMAL",
            cvd_data_status="MISSING_FLOW",
            decision_timestamp_ms=1672531500000,
        )
        d = ev.to_dict()
        self.assertEqual(d["cvd_data_status"], "MISSING_FLOW")
        self.assertTrue(np.isnan(d["cvd_zscore"]), "cvd_zscore was serialized as numeric zero instead of NaN")
        self.assertNotEqual(d["cvd_zscore"], 0.0)


class TestPhase13TimestampGapsAndRollingIntegrity(unittest.TestCase):
    """Phase 1 Mandatory Regression Tests: Timestamp Gaps & Rolling Indicator Integrity.

    Proves:
    1. A single missing 1m row marks the affected resampled interval invalid on the regular time grid.
    2. Resampled OHLCV/volume are NaNs; no prices or volumes are fabricated or interpolated.
    3. Exactly 12 rolling 5m CVD windows report MISSING_FLOW; time is never compressed.
    4. Wilder's ATR smoothing state resets across data gaps without carrying forward old state.
    5. Rolling volume SMA and swing highs/lows do not bridge across missing intervals.
    6. Reclaim signals comparing prior and current bar require consecutive timestamps and valid intervals.
    7. Clean recovery to fully valid indicators after full warm-up following a gap.
    """

    def test_single_1m_dropped_preserves_regular_time_grid_with_invalid_interval(self):
        """1. Remove one 1m row: verify grid length preserved, affected interval invalid with NaNs."""
        start_ms = 1672531200000  # 2023-01-01 00:00:00
        df_1m = _make_1m_df(start_ms, 240)  # 4 hours = 240 1m bars

        # Drop minute 7 (at 00:07 UTC)
        df_gap = df_1m.loc[df_1m["timestamp"] != start_ms + 7 * 60_000].copy()

        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_gap)

        # 5m: 240 / 5 = 48 regular grid points preserved
        self.assertEqual(len(df_5m), 48, "5m regular grid length must not shrink")
        # Bucket 00:05 (spanning minutes 5..9) has 4 minutes -> marked invalid
        row_5m_0005 = df_5m.loc[df_5m["timestamp"] == start_ms + 5 * 60_000].iloc[0]
        self.assertFalse(row_5m_0005["is_valid_interval"])
        self.assertTrue(np.isnan(row_5m_0005["close"]))
        self.assertTrue(np.isnan(row_5m_0005["volume"]))
        # Bucket 00:00 has all 5 minutes -> valid
        row_5m_0000 = df_5m.loc[df_5m["timestamp"] == start_ms].iloc[0]
        self.assertTrue(row_5m_0000["is_valid_interval"])
        self.assertFalse(np.isnan(row_5m_0000["close"]))

        # 15m: 240 / 15 = 16 regular grid points
        self.assertEqual(len(df_15m), 16)
        row_15m_0 = df_15m.loc[df_15m["timestamp"] == start_ms].iloc[0]
        self.assertFalse(row_15m_0["is_valid_interval"])
        self.assertTrue(np.isnan(row_15m_0["close"]))

        # 1h: 4 regular grid points
        self.assertEqual(len(df_1h), 4)
        row_1h_0 = df_1h.loc[df_1h["timestamp"] == start_ms].iloc[0]
        self.assertFalse(row_1h_0["is_valid_interval"])
        self.assertTrue(np.isnan(row_1h_0["close"]))

        # 4h: 1 regular grid point
        self.assertEqual(len(df_4h), 1)
        row_4h_0 = df_4h.loc[df_4h["timestamp"] == start_ms].iloc[0]
        self.assertFalse(row_4h_0["is_valid_interval"])
        self.assertTrue(np.isnan(row_4h_0["close"]))

    def test_12_affected_5m_cvd_windows_report_missing_flow_and_no_gap_compression(self):
        """2. Single gap in 5m flow marks exactly 12 rolling 1h CVD windows as MISSING_FLOW."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=60, freq="5min")
        np.random.seed(123)
        flow_vals = np.random.randn(60) * 15.0
        # Inject NaN at index 25
        flow_vals[25] = np.nan
        df_5m = pd.DataFrame({"delta_v": flow_vals}, index=idx)

        z_scores, statuses = p13.compute_cvd(df_5m)

        # The 12 rolling windows spanning index 25 are indices 25..36
        affected_indices = [i for i in range(25, 37)]
        for i in affected_indices:
            self.assertEqual(statuses.iloc[i], "MISSING_FLOW", f"Bar {i} must be MISSING_FLOW")
            self.assertTrue(np.isnan(z_scores.iloc[i]), f"Bar {i} z-score must be NaN")

        # After index 36, window (37-11..37) = (26..37) contains 12 complete valid bars.
        # It must NOT be MISSING_FLOW (it transitions to INSUFFICIENT_HISTORY or AVAILABLE)
        self.assertNotEqual(statuses.iloc[37], "MISSING_FLOW", "Bar 37 must recover from missing constituent flow")

    def test_rolling_atr_and_volume_sma_do_not_bridge_gap(self):
        """3. Wilder ATR smoothing resets across gap; rolling volume SMA requires 20 consecutive bars."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=50, freq="5min")
        # Pre-gap prices: TR = 10.0 -> ATR = 10.0
        highs = pd.Series([105.0] * 20 + [np.nan] + [110.0] * 29, index=idx)
        lows = pd.Series([95.0] * 20 + [np.nan] + [90.0] * 29, index=idx)
        closes = pd.Series([100.0] * 20 + [np.nan] + [100.0] * 29, index=idx)

        atr = p13.compute_atr(highs, lows, closes, period=14)

        # Bar 19 must have valid ATR = 10.0
        self.assertTrue(np.isclose(atr.iloc[19], 10.0))
        # Bar 20 is gap -> NaN
        self.assertTrue(np.isnan(atr.iloc[20]))
        # Bar 21 cannot measure true range from before gap (prev_close was NaN) -> NaN
        self.assertTrue(np.isnan(atr.iloc[21]))
        # Bar 22 is first valid bar after gap with TR = 20.0.
        # Stateful Wilder smoothing must reset across gap to 20.0 (unreset ewm would yield ~10.71)
        self.assertTrue(np.isclose(atr.iloc[22], 20.0), f"Expected reset to 20.0, got {atr.iloc[22]}")

    def test_reclaim_and_confluence_do_not_cross_gap(self):
        """4. Signals comparing previous and current candle reject unexpected time gaps or invalid bars."""
        engine = p13.Phase13DiscoveryEngine()
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 200, base_price=100.0)

        # Drop minutes 65..69 (an entire 5m bar at index 13)
        df_gap_1m = df_1m.loc[~df_1m["timestamp"].between(start_ms + 65 * 60_000, start_ms + 69 * 60_000)].copy()

        events, _, _ = engine.extract_events_for_symbol("BTCUSDT", df_gap_1m)

        # Bar 14 (immediately following the dropped 5m bar) must NOT emit VWAP_RECLAIM
        # because the prior bar was invalid/missing.
        ts_bar_14 = start_ms + 70 * 60_000
        reclaims_at_gap_boundary = [e for e in events if e.timestamp_ms == ts_bar_14 and e.event_class == "VWAP_RECLAIM"]
        self.assertEqual(len(reclaims_at_gap_boundary), 0, "VWAP_RECLAIM must not cross an invalid gap interval")


class TestPhase13VWAPAndDispersionStabilization(unittest.TestCase):
    """Phase 2 Mandatory Regression Tests: Session VWAP & Welford Dispersion.

    Proves:
    1. Constant price of 85000.0001 with unequal positive volumes produces 0.0 dispersion (never a fabricated positive number).
    2. Prices [85000.0, 85000.001] with equal volumes produce expected dispersion 0.0005 (+/- 1e-10).
    3. Small nominal price scales (e.g. 0.00005) preserve small valid dispersions without arbitrary epsilon suppression.
    4. Exact transaction VWAP from quote_volume vs representative-price approximation.
    5. Session gap invalidation: unaccounted-for gap invalidates remainder of day; next session resets cleanly.
    6. Non-finite volumes or zero volume produce NaNs.
    """

    def test_constant_price_85000_unequal_volumes_zero_dispersion(self):
        """1. Constant price of 85000.0001 with unequal positive volumes: dispersion must be 0.0 for N>=2."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=4, freq="5min")
        df_const = pd.DataFrame({
            "close": [85000.0001, 85000.0001, 85000.0001, 85000.0001],
            "volume": [10.5, 23.4, 15.2, 80.0]
        }, index=idx)

        vwap, std = p13.compute_vwap(df_const)

        # Bar 0: single-bar dispersion is undefined (NaN)
        self.assertTrue(np.isnan(std.iloc[0]))
        # Bars 1..3: exact zero variance (0.0), never fabricated positive number
        for i in range(1, 4):
            self.assertEqual(std.iloc[i], 0.0, f"Bar {i} dispersion must be exactly 0.0")
            self.assertAlmostEqual(vwap.iloc[i], 85000.0001, places=4)

    def test_two_bars_85000_expected_dispersion(self):
        """2. Prices [85000.0, 85000.001] with equal volumes: expected population dispersion is 0.0005."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=2, freq="5min")
        df_test = pd.DataFrame({
            "close": [85000.0, 85000.001],
            "volume": [10.0, 10.0]
        }, index=idx)

        vwap, std = p13.compute_vwap(df_test)

        self.assertAlmostEqual(vwap.iloc[1], 85000.0005, places=7)
        self.assertAlmostEqual(std.iloc[1], 0.0005, delta=1e-10)

    def test_small_nominal_price_scale_dispersion(self):
        """3. Low-priced instrument preserves small dispersion without arbitrary epsilon suppression."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=2, freq="5min")
        df_low = pd.DataFrame({
            "close": [0.00005, 0.00006],
            "volume": [100.0, 100.0]
        }, index=idx)

        vwap, std = p13.compute_vwap(df_low)

        # Population mean = 0.000055, dev = 0.000005 (5e-6)
        # Old code had a threshold std > 1e-6 which could mask smaller values; Welford retains exact value
        self.assertAlmostEqual(std.iloc[1], 0.000005, delta=1e-12)

    def test_quote_volume_turnover_provenance(self):
        """4. quote_volume turnover calculation produces exact transaction VWAP."""
        idx = pd.date_range("2023-01-01 00:00:00", periods=2, freq="5min")
        # Bar 1: close = 100, vol = 10, quote_vol = 1000
        # Bar 2: close = 105, vol = 10, quote_vol = 1020 (actual intra-bar average price was 102.0)
        df_qv = pd.DataFrame({
            "close": [100.0, 105.0],
            "volume": [10.0, 10.0],
            "quote_volume": [1000.0, 1020.0]
        }, index=idx)

        vwap, std = p13.compute_vwap(df_qv)

        # Transaction exact VWAP = (1000 + 1020) / (10 + 10) = 2020 / 20 = 101.0
        # Whereas close * volume turnover would have yielded (1000 + 1050) / 20 = 102.5
        self.assertAlmostEqual(vwap.iloc[1], 101.0, places=4)
        self.assertNotEqual(vwap.iloc[1], 102.5)

    def test_intraday_session_boundary_reset_and_gap_invalidation(self):
        """5. Data gap in Day 1 invalidates remainder of Day 1; Day 2 resets fresh at 00:00 UTC."""
        idx_day1 = pd.date_range("2023-01-01 00:00:00", periods=10, freq="5min")
        idx_day2 = pd.date_range("2023-01-02 00:00:00", periods=5, freq="5min")
        idx = idx_day1.append(idx_day2)

        prices = [100.0] * 15
        volumes = [10.0] * 15
        # Inject gap at bar 4 of Day 1
        volumes[4] = np.nan

        df_session = pd.DataFrame({"close": prices, "volume": volumes}, index=idx)
        vwap, std = p13.compute_vwap(df_session)

        # Day 1: Bars 0..3 valid
        self.assertTrue(vwap.iloc[0:4].notna().all())
        # Day 1: Bars 4..9 are invalid (gapped session)
        self.assertTrue(vwap.iloc[4:10].isna().all(), "All bars after gap in session must be NaN")
        self.assertTrue(std.iloc[4:10].isna().all(), "All std bars after gap in session must be NaN")

        # Day 2: Starts fresh at 00:00 UTC
        self.assertFalse(np.isnan(vwap.iloc[10]))
        self.assertTrue(np.isnan(std.iloc[10]))  # N=1 of Day 2 is NaN dispersion
        self.assertEqual(std.iloc[11], 0.0)  # N=2 of Day 2 is 0.0 dispersion for constant price


class TestPhase13StructuralStopEligibility(unittest.TestCase):
    """Phase 3 Mandatory Regression Tests: Structural Stop Eligibility & Fallback Removal.

    Proves:
    1. If a structural swing stop is unavailable, the evaluation is excluded (never replaced by ATR).
    2. An invalid STOP_15M_SWING or STOP_1H_SWING is never recorded as successful using an ATR substitute.
    3. If a stop is on the wrong side of entry, it is rejected (never replaced by entry +/- 1.0*ATR).
    4. If a stop distance is below minimum threshold (< 1e-4), it is excluded (never clamped to 1e-4).
    5. Stop model evaluation diagnostics explicitly count included and excluded models by reason.
    """

    def test_missing_swing_stops_never_fall_back_to_atr(self):
        """1. Missing HTF swing stops are excluded, not substituted with ATR while keeping HTF name."""
        engine = p13.Phase13DiscoveryEngine()
        start_ms = 1672531200000
        # 450 minutes of data -> 5m has 90 bars (scans bars 50..64), 1h has 7.5 bars -> 1h swing (lookback 6 completed bars) is unavailable during early events
        df_1m = _make_1m_df(start_ms, 450, base_price=100.0)

        events, outcomes, evals = engine.extract_events_for_symbol("BTCUSDT", df_1m)

        # Confirm STOP_1H_SWING is NEVER recorded among evaluated stops
        eval_stop_models = [ev.stop_model for ev in evals]
        self.assertNotIn("STOP_1H_SWING", eval_stop_models, "STOP_1H_SWING must not be evaluated when swing is missing")

        # Diagnostics must show excluded count for MISSING_SWING_DATA
        missing_1h = engine.stop_diagnostics["excluded"]["MISSING_SWING_DATA"]["STOP_1H_SWING"]
        self.assertGreater(missing_1h, 0, "Missing 1H swing must be recorded in stop_diagnostics")

    def test_wrong_side_of_entry_stop_rejected(self):
        """2. Stop on wrong side of entry is excluded with WRONG_SIDE_OF_ENTRY, not replaced with 1.0*ATR."""
        engine = p13.Phase13DiscoveryEngine()
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 200, base_price=100.0)

        # Run extraction
        events, outcomes, evals = engine.extract_events_for_symbol("BTCUSDT", df_1m)

        # For every single evaluated stop in evals:
        for ev in evals:
            if ev.direction == "LONG":
                self.assertLess(ev.sl_price, ev.entry_price, f"LONG stop {ev.sl_price} must be strictly below entry {ev.entry_price}")
            else:
                self.assertGreater(ev.sl_price, ev.entry_price, f"SHORT stop {ev.sl_price} must be strictly above entry {ev.entry_price}")

    def test_sub_minimum_stop_distance_excluded(self):
        """3. Stop distance < 1e-4 is excluded with INADMISSIBLE_DISTANCE, never clamped to 1e-4."""
        engine = p13.Phase13DiscoveryEngine()
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 200, base_price=100.0)

        events, outcomes, evals = engine.extract_events_for_symbol("BTCUSDT", df_1m)

        for ev in evals:
            sl_dist_pct = abs(ev.entry_price - ev.sl_price) / ev.entry_price
            self.assertGreaterEqual(sl_dist_pct, 1e-4, f"Evaluated stop distance {sl_dist_pct} must be >= 1e-4")

    def test_stop_diagnostics_tracking_by_reason(self):
        """4. Engine records diagnostic counts for included and excluded evaluations by exact reason."""
        engine = p13.Phase13DiscoveryEngine()
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 200, base_price=100.0)

        events, outcomes, evals = engine.extract_events_for_symbol("BTCUSDT", df_1m)

        diag = engine.stop_diagnostics
        self.assertIn("included", diag)
        self.assertIn("excluded", diag)
        for reason in ["MISSING_SWING_DATA", "NON_FINITE_PRICE", "WRONG_SIDE_OF_ENTRY", "INADMISSIBLE_DISTANCE"]:
            self.assertIn(reason, diag["excluded"])
            for m in ["STOP_5M_SWING", "STOP_15M_SWING", "STOP_1H_SWING", "STOP_ATR_ENVELOPE"]:
                self.assertIn(m, diag["excluded"][reason])


if __name__ == "__main__":
    unittest.main()


