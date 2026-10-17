import unittest
import time
from control_plane.retest_engine import (
    CausalRetestEngine,
    RetestState,
    calculate_atr,
    calculate_rvol,
    detect_swing_points,
    compute_structural_targets_stops,
    generate_setup_candidate_from_state,
)


class TestCausalRetestEngine(unittest.TestCase):
    def setUp(self):
        # Construct synthetic candle series without lookahead
        # 30 candles: initial consolidation, then breakout upwards
        self.candles = []
        base_price = 100.0
        base_ts = 1700000000000
        for i in range(30):
            # Price oscillates between 99 and 101, then breaks out to 105 on candle 25
            if i < 25:
                o = base_price + (i % 2 - 0.5)
                c = o + 0.2
                h = max(o, c) + 0.5
                l = min(o, c) - 0.5
                v = 1000.0
            else:
                # Breakout candle
                o = 101.0
                c = 105.0 + (i - 25) * 0.5
                h = c + 0.5
                l = o - 0.2
                v = 3000.0  # High volume
            self.candles.append({
                "symbol": "BTC-USDT",
                "ts": base_ts + i * 60000,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "taker_buy": v * 0.7,
                "trades": 50
            })

    def test_causal_swing_points_zero_lookahead(self):
        highs = [c["high"] for c in self.candles]
        lows = [c["low"] for c in self.candles]
        lookback = 3
        swing_highs, swing_lows = detect_swing_points(highs, lows, lookback=lookback)
        # All detected swings must be strictly older than len - lookback
        max_allowed_idx = len(highs) - lookback - 1
        for idx, val in swing_highs:
            self.assertLessEqual(idx, max_allowed_idx, "Swing high detected in unconfirmed future bars!")
        for idx, val in swing_lows:
            self.assertLessEqual(idx, max_allowed_idx, "Swing low detected in unconfirmed future bars!")

    def test_retest_state_transitions(self):
        engine = CausalRetestEngine(
            symbol="BTC-USDT",
            timeframe=3,
            direction="LONG",
            retest_window=5,
            displacement_atr_mult=1.0,
            rvol_threshold=1.5,
            require_freshness=False
        )

        state = RetestState(symbol="BTC-USDT", timeframe=3, direction="LONG", state="IDLE")
        vwap = 100.5

        # Evaluate on breakout candles
        state = engine.evaluate_step(state, self.candles[:26], vwap)
        self.assertEqual(state.state, "WAITING_FOR_RETEST")
        self.assertIsNotNone(state.breakout_price)
        self.assertIsNotNone(state.zone_low)
        self.assertIsNotNone(state.zone_high)

        # Now simulate next candle retesting the zone
        retest_candle = {
            "symbol": "BTC-USDT",
            "ts": self.candles[-1]["ts"] + 60000,
            "open": 105.0,
            "high": 105.2,
            "low": state.zone_high - 0.05,  # Touches zone
            "close": state.zone_high + 0.5,  # Closes above zone
            "volume": 2000.0,
            "taker_buy": 1500.0,
            "trades": 60
        }
        candles_retest = self.candles[:26] + [retest_candle]
        state = engine.evaluate_step(state, candles_retest, vwap)
        self.assertIn(state.state, ("RETEST_TOUCHED", "RETEST_ZONE_TOUCHED"))

        # Next candle confirms rejection and advances to REJECTION_CONFIRMED
        rejection_candle = {
            "symbol": "BTC-USDT",
            "ts": retest_candle["ts"] + 60000,
            "open": state.zone_high + 0.1,
            "high": state.zone_high + 1.5,
            "low": state.zone_high,
            "close": state.zone_high + 1.2,  # Bullish expansion
            "volume": 2500.0,
            "taker_buy": 2000.0,
            "trades": 70
        }
        candles_rejection = candles_retest + [rejection_candle]
        state = engine.evaluate_step(state, candles_rejection, vwap)
        self.assertIn(state.state, ("CONFIRMING_REJECTION", "REJECTION_CONFIRMED"))

        # Next check advances to ENTRY_READY / ENTRY_CANDIDATE
        state = engine.evaluate_step(state, candles_rejection, vwap)
        self.assertIn(state.state, ("ENTRY_READY", "ENTRY_CANDIDATE"))

    def test_structural_targets_and_stops(self):
        vwap = 100.5
        entry = 105.0
        ts = compute_structural_targets_stops(self.candles, "LONG", entry, vwap)
        self.assertIn("sl", ts)
        self.assertIn("tp1", ts)
        self.assertIn("tp2", ts)
        self.assertLess(ts["sl"], entry, "LONG SL must be strictly below entry price")
        if ts["tp2"] is not None:
            self.assertGreaterEqual(ts["tp2"], ts["tp1"], "TP2 must be greater than or equal to TP1")
        self.assertGreaterEqual(ts["risk_reward"], 1.0)

    def test_generate_setup_candidate_dto(self):
        state = RetestState(
            symbol="BTC-USDT",
            timeframe=3,
            direction="LONG",
            state="WAITING_FOR_RETEST",
            breakout_price=105.0,
            breakout_ts=1700000000000,
            zone_low=101.5,
            zone_high=102.0,
            elapsed_candles=1
        )
        dto = generate_setup_candidate_from_state(state, self.candles, 100.5)
        self.assertEqual(dto["symbol"], "BTC-USDT")
        self.assertEqual(dto["direction"], "LONG")
        self.assertEqual(dto["strategy"], "VWAP_STRUCTURE_RETEST")
        self.assertIn("suggested_sl", dto)
        self.assertIn("suggested_tp1", dto)
        self.assertIn("suggested_tp2", dto)
        self.assertIn("confidence_pct", dto)
        self.assertIn("thesis", dto)


if __name__ == "__main__":
    unittest.main()
