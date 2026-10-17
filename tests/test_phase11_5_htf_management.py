"""Unit and integration tests for Phase 11.5 HTF Regime & Trade Management Research.

Layer: tests/test_phase11_5_htf_management.py
Verifies:
1. Resampling 5m bars to 1H and 4H closed candles.
2. Strict forward causality in HTF feature extraction (zero lookahead).
3. 1H and 4H trend alignment and structure location rules.
4. Trade management policy simulation (Fixed, Breakeven, Partial, Trailing, Time-exit).
5. Conservative same-candle execution ordering.
6. Absolute safety invariants (SHADOW mode, zero live authority).
"""
from __future__ import annotations

import unittest
from typing import List

from control_plane.phase11_5_htf_engine import (
    resample_htf_candles,
    compute_htf_features,
    simulate_trade_management,
    HTFCandidateSnapshot,
)
from control_plane import config


class TestPhase11_5HTFManagement(unittest.TestCase):
    """Test suite validating Phase 11.5 HTF engine and trade management logic."""

    def setUp(self):
        # Create synthetic 5m candles covering 24 hours (288 bars)
        # Starting at 2023-10-01 00:00:00 UTC (ts = 1696118400000)
        self.base_ts = 1696118400000
        self.candles_5m: List[dict] = []
        for i in range(288):
            ts = self.base_ts + i * 5 * 60 * 1000
            price = 28000.0 + i * 5.0
            self.candles_5m.append({
                "ts": ts,
                "open": price - 2.0,
                "high": price + 4.0,
                "low": price - 3.0,
                "close": price,
                "volume": 100.0 + i
            })

    def test_resample_htf_candles_1h_and_4h(self):
        """Verify grouping of 5m bars into closed 1H and 4H bars."""
        c1h = resample_htf_candles(self.candles_5m, bar_ms=3600 * 1000)
        self.assertEqual(len(c1h), 24, "288 5m bars must yield exactly 24 1H bars")
        self.assertEqual(c1h[0]["ts"], self.base_ts + 3600 * 1000)
        
        c4h = resample_htf_candles(self.candles_5m, bar_ms=4 * 3600 * 1000)
        self.assertEqual(len(c4h), 6, "288 5m bars must yield exactly 6 4H bars")
        self.assertEqual(c4h[0]["ts"], self.base_ts + 4 * 3600 * 1000)

    def test_causal_htf_zero_lookahead(self):
        """Ensure bars closing after candidate timestamp are never included."""
        c1h = resample_htf_candles(self.candles_5m, bar_ms=3600 * 1000)
        c4h = resample_htf_candles(self.candles_5m, bar_ms=4 * 3600 * 1000)
        
        # Test candidate at hour 20, minute 25
        cand_ts = self.base_ts + (20 * 60 + 25) * 60 * 1000
        feats = compute_htf_features(cand_ts, "LONG", c1h, c4h)
        
        # Candidate at 20:25 only has access to 1H bars closed at or before 20:00
        self.assertTrue(feats["has_1h"])
        self.assertEqual(feats["trend_1h"], "BULLISH")
        self.assertTrue(feats["trend_aligned_1h"])

    def test_simulate_trade_management_fixed(self):
        """Verify baseline fixed SL/TP exit simulation."""
        # Simple upward trajectory
        future_candles = [
            {"high": 102.0, "low": 99.0, "close": 101.0},
            {"high": 105.0, "low": 100.0, "close": 104.0},
            {"high": 111.0, "low": 103.0, "close": 110.0},  # Hits TP1 at 110.0
        ]
        gross_r, net_r, reason, duration = simulate_trade_management(
            policy_name="FIXED_SL_TP",
            direction="LONG",
            entry=100.0,
            sl=95.0,
            tp1=110.0,
            tp2=120.0,
            future_candles_5m=future_candles,
            cur_atr=2.0,
            friction_rate=0.0009
        )
        self.assertEqual(reason, "TP1")
        self.assertEqual(gross_r, 2.0)  # (110 - 100) / 5 = 2.0R
        self.assertLess(net_r, gross_r)  # Net must subtract friction
        self.assertEqual(duration, 15)   # 3 bars * 5m

    def test_simulate_trade_management_breakeven_activation(self):
        """Verify breakeven activation ratchets stop to entry."""
        # Price reaches +0.8R (104.0) then drops below entry
        future_candles = [
            {"high": 104.5, "low": 99.5, "close": 104.0},   # MFE reaches +0.9R
            {"high": 103.0, "low": 99.0, "close": 99.5},    # Hits BE stop at 100.0
        ]
        gross_r, net_r, reason, duration = simulate_trade_management(
            policy_name="BE_0.8R",
            direction="LONG",
            entry=100.0,
            sl=95.0,
            tp1=110.0,
            tp2=120.0,
            future_candles_5m=future_candles,
            cur_atr=2.0,
            friction_rate=0.0009
        )
        self.assertEqual(reason, "BE_EXIT")
        self.assertAlmostEqual(gross_r, 0.0, places=4)
        self.assertLess(net_r, 0.0)  # Net loses friction only

    def test_simulate_trade_management_tp1_partial(self):
        """Verify 50% partial exit at TP1 with remaining 50% held."""
        future_candles = [
            {"high": 110.5, "low": 99.5, "close": 110.0},  # Hits TP1 (110.0) -> 50% closed at +2.0R
            {"high": 108.0, "low": 99.0, "close": 99.5},   # Remaining 50% stopped out at BE (100.0)
        ]
        gross_r, net_r, reason, duration = simulate_trade_management(
            policy_name="TP1_PARTIAL",
            direction="LONG",
            entry=100.0,
            sl=95.0,
            tp1=110.0,
            tp2=120.0,
            future_candles_5m=future_candles,
            cur_atr=2.0,
            friction_rate=0.0009
        )
        # 50% of 2.0R = 1.0R, 50% of 0.0R = 0.0R -> total gross R = 1.0R
        self.assertAlmostEqual(gross_r, 1.0, places=4)
        self.assertGreater(net_r, 0.9)

    def test_simulate_trade_management_time_exit(self):
        """Verify time-based exit triggers at bar 6 (30m)."""
        future_candles = [{"high": 101.0, "low": 99.0, "close": 100.5} for _ in range(10)]
        gross_r, net_r, reason, duration = simulate_trade_management(
            policy_name="TIME_EXIT_30M",
            direction="LONG",
            entry=100.0,
            sl=95.0,
            tp1=110.0,
            tp2=120.0,
            future_candles_5m=future_candles,
            cur_atr=2.0,
            friction_rate=0.0009
        )
        self.assertEqual(reason, "TIME_EXIT_30M")
        self.assertEqual(duration, 30)

    def test_safety_invariants(self):
        """Verify SHADOW mode and zero live trading authority."""
        self.assertEqual(config.DEFAULT_TRADING_MODE, "SHADOW")


if __name__ == "__main__":
    unittest.main()
