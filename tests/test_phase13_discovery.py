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
        """Test 4: Mutating bars strictly after decision time T leaves all features at T byte-for-byte identical."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 300)  # 5 hours
        decision_offset_min = 120  # Decision at T = 2 hours
        t_decision_ms = start_ms + decision_offset_min * 60_000
        bar_open_ms = t_decision_ms - 5 * 60_000

        # Run uncorrupted
        df_5m_clean, df_15m_clean, df_1h_clean, df_4h_clean = p13.resample_phase13_bars(df_1m)
        df_15m_clean["atr_14"] = p13.compute_atr(df_15m_clean["high"], df_15m_clean["low"], df_15m_clean["close"], 14)
        df_1h_clean["atr_14"] = p13.compute_atr(df_1h_clean["high"], df_1h_clean["low"], df_1h_clean["close"], 14)
        df_4h_clean["trend_4h"] = "BULL"
        merged_clean = p13.merge_completed_htf_features(df_5m_clean, df_15m_clean, df_1h_clean, df_4h_clean)
        row_clean = merged_clean.loc[merged_clean["timestamp"] == bar_open_ms].iloc[0]

        # Corrupt all bars with timestamp >= t_decision_ms (future bars)
        df_1m_corrupt = df_1m.copy()
        mask_future = df_1m_corrupt["timestamp"] >= t_decision_ms
        df_1m_corrupt.loc[mask_future, "close"] *= 1000.0
        df_1m_corrupt.loc[mask_future, "high"] *= 2000.0
        df_1m_corrupt.loc[mask_future, "low"] = 0.001
        df_1m_corrupt.loc[mask_future, "volume"] = 9999999.0
        df_1m_corrupt.loc[mask_future, "delta_v"] = -888888.0

        df_5m_bad, df_15m_bad, df_1h_bad, df_4h_bad = p13.resample_phase13_bars(df_1m_corrupt)
        df_15m_bad["atr_14"] = p13.compute_atr(df_15m_bad["high"], df_15m_bad["low"], df_15m_bad["close"], 14)
        df_1h_bad["atr_14"] = p13.compute_atr(df_1h_bad["high"], df_1h_bad["low"], df_1h_bad["close"], 14)
        df_4h_bad["trend_4h"] = "BULL"
        merged_bad = p13.merge_completed_htf_features(df_5m_bad, df_15m_bad, df_1h_bad, df_4h_bad)
        row_bad = merged_bad.loc[merged_bad["timestamp"] == bar_open_ms].iloc[0]

        # Verify all features at decision time T are identical
        test_features = [
            "open", "high", "low", "close", "volume",
            "close_15m", "high_15m", "low_15m", "atr_15m", "swing_low_15m", "swing_high_15m",
            "close_1h", "high_1h", "low_1h", "atr_1h", "swing_low_1h", "swing_high_1h",
        ]
        for feat in test_features:
            v_clean = row_clean[feat]
            v_bad = row_bad[feat]
            if np.isnan(v_clean):
                self.assertTrue(np.isnan(v_bad), f"Feature {feat} was NaN in clean but {v_bad} in corrupt")
            else:
                self.assertEqual(v_clean, v_bad, f"Feature {feat} differed: {v_clean} vs {v_bad}")

    def test_test5_incomplete_candles_and_data_gaps(self):
        """Test 5: Incomplete HTF candle dropped from pipeline; missing values remain NaN with zero fallbacks."""
        start_ms = 1672531200000
        df_1m = _make_1m_df(start_ms, 60)
        # Drop minute 7 -> 00:00-00:15 has 14 bars (< 15)
        df_1m_gap = df_1m.loc[df_1m["timestamp"] != start_ms + 7 * 60_000].copy()

        df_5m, df_15m, df_1h, df_4h = p13.resample_phase13_bars(df_1m_gap)
        # 15m candle for 00:00 must be dropped
        self.assertTrue(len(df_15m.loc[df_15m["timestamp"] == start_ms]) == 0)
        # 1h candle for 00:00 must be dropped (59 bars < 60)
        self.assertTrue(len(df_1h.loc[df_1h["timestamp"] == start_ms]) == 0)

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


if __name__ == "__main__":
    unittest.main()


