"""
Deterministic verification test suite for Ophelia Institutional Microstructure,
CVD Engine, Structure Detectors, MarketState Engine, and Kronos Advisory Safety.
"""

import unittest
import time
import sys
from unittest.mock import MagicMock

for mod in ["fastapi", "fastapi.security", "jwt", "pydantic", "bcrypt"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

from institutional.types import DataQuality, Direction
from institutional.cvd.cvd_engine import CVDEngine, CVDTrade
from institutional.structure_detectors import (
    detect_fvg,
    detect_liquidity_sweep,
    detect_equal_highs_lows,
    detect_displacement,
    detect_cvd_divergence,
)
from institutional.market_state import MarketStateEngine, MarketState
from institutional.research.evaluation_framework import FeatureEvaluator
from control_plane.kronos import KronosAdvisor, KronosAdvisoryReport
from control_plane import config


class TestInstitutionalMicrostructureAndCVD(unittest.TestCase):

    def setUp(self):
        self.now_ms = 1756900000000  # Fixed deterministic timestamp

    # -------------------------------------------------------------
    # 1. CVD ENGINE TESTS
    # -------------------------------------------------------------
    def test_cvd_trade_aggressor_classification(self):
        """Verify verified BingX exchange semantics for buyer maker."""
        # is_buyer_maker == True -> Buyer was Maker -> Aggressor was SELLER
        sell_trade = CVDTrade(
            trade_id="t1",
            timestamp=self.now_ms,
            price=65000.0,
            quantity=0.1,
            quote_quantity=6500.0,
            is_buyer_maker=True
        )
        self.assertEqual(sell_trade.aggressor, "SELL")
        self.assertEqual(sell_trade.signed_delta, -6500.0)

        # is_buyer_maker == False -> Buyer was Taker -> Aggressor was BUYER
        buy_trade = CVDTrade(
            trade_id="t2",
            timestamp=self.now_ms + 100,
            price=65010.0,
            quantity=0.2,
            quote_quantity=13002.0,
            is_buyer_maker=False
        )
        self.assertEqual(buy_trade.aggressor, "BUY")
        self.assertEqual(buy_trade.signed_delta, 13002.0)

    def test_cvd_engine_accumulation_and_deduplication(self):
        """Verify CVD accumulation, trade deduplication, and volume balance."""
        engine = CVDEngine(symbol="BTC-USDT", interval_ms=60_000)

        t1 = CVDTrade("t1", self.now_ms, 65000.0, 1.0, 65000.0, is_buyer_maker=False)  # +65000 BUY
        t2 = CVDTrade("t2", self.now_ms + 1000, 65000.0, 0.5, 32500.0, is_buyer_maker=True)  # -32500 SELL
        t3 = CVDTrade("t1", self.now_ms + 2000, 65000.0, 1.0, 65000.0, is_buyer_maker=False)  # Duplicate!

        accepted1 = engine.add_trade(t1)
        accepted2 = engine.add_trade(t2)
        accepted3 = engine.add_trade(t3)

        self.assertTrue(accepted1)
        self.assertTrue(accepted2)
        self.assertFalse(accepted3, "Duplicate trade_id must be rejected")

        state = engine.get_state(self.now_ms + 3000)
        self.assertEqual(state["cumulative_delta"], 32500.0)
        self.assertEqual(state["trade_count"], 2)
        self.assertEqual(state["direction"], "BULLISH")

    def test_cvd_engine_reset_behavior(self):
        """Verify cumulative reset logic operates deterministically."""
        engine = CVDEngine(symbol="BTC-USDT", interval_ms=60_000, reset_interval_ms=3600_000)
        t1 = CVDTrade("t1", self.now_ms, 65000.0, 1.0, 65000.0, is_buyer_maker=False)
        engine.add_trade(t1)
        self.assertEqual(engine.cumulative_delta, 65000.0)

        # Explicit reset
        engine.reset_cumulative(self.now_ms + 1000)
        self.assertEqual(engine.cumulative_delta, 0.0)

    def test_cvd_engine_stale_detection(self):
        """Verify engine marks state STALE when last trade exceeds stale threshold."""
        engine = CVDEngine(symbol="BTC-USDT", stale_threshold_ms=60_000)
        t1 = CVDTrade("t1", self.now_ms, 65000.0, 1.0, 65000.0, is_buyer_maker=False)
        engine.add_trade(t1)

        # Fresh
        dq_fresh = engine.get_data_quality(self.now_ms + 30_000)
        self.assertEqual(dq_fresh, DataQuality.VALID)

        # Stale (> 60s)
        dq_stale = engine.get_data_quality(self.now_ms + 70_000)
        self.assertEqual(dq_stale, DataQuality.STALE)

    # -------------------------------------------------------------
    # 2. STRUCTURE DETECTORS TESTS
    # -------------------------------------------------------------
    def test_fvg_detection_bullish_and_bearish(self):
        """Verify 3-candle Fair Value Gap detection."""
        # Bullish FVG: Candle 1 High < Candle 3 Low
        bull_highs = [65000.0, 65300.0, 65500.0]
        bull_lows = [64800.0, 65050.0, 65200.0]  # c3_low (65200) > c1_high (65000)
        bull_closes = [64950.0, 65250.0, 65400.0]

        res_bull = detect_fvg(bull_highs, bull_lows, bull_closes, self.now_ms, "BTC-USDT")
        self.assertTrue(res_bull.detected)
        self.assertEqual(res_bull.direction, "BULLISH")
        self.assertEqual(res_bull.measurements["gap_low"], 65000.0)
        self.assertEqual(res_bull.measurements["gap_high"], 65200.0)

        # Bearish FVG: Candle 1 Low > Candle 3 High
        bear_highs = [65500.0, 65200.0, 64900.0]  # c3_high (64900) < c1_low (65100)
        bear_lows = [65100.0, 64800.0, 64600.0]
        bear_closes = [65200.0, 64900.0, 64700.0]

        res_bear = detect_fvg(bear_highs, bear_lows, bear_closes, self.now_ms, "BTC-USDT")
        self.assertTrue(res_bear.detected)
        self.assertEqual(res_bear.direction, "BEARISH")
        self.assertEqual(res_bear.measurements["gap_low"], 64900.0)
        self.assertEqual(res_bear.measurements["gap_high"], 65100.0)

    def test_liquidity_sweep_detection(self):
        """Verify liquidity sweep where wick penetrates swing level but close remains inside."""
        lookback = 10
        # Swing high is 66000.0
        highs = [65000.0] * 9 + [66000.0] + [66200.0]  # last candle high = 66200 (sweeps 66000)
        lows = [64500.0] * 10 + [65700.0]
        closes = [64900.0] * 10 + [65900.0]  # last candle close = 65900 (< 66000.0)

        res = detect_liquidity_sweep(highs, lows, closes, self.now_ms, "BTC-USDT", lookback=lookback)
        self.assertTrue(res.detected)
        self.assertEqual(res.direction, "BEARISH")
        self.assertEqual(res.measurements["swept_level"], 66000.0)
        self.assertEqual(res.measurements["type"], "BUY_SIDE_LIQUIDITY_SWEPT")

    def test_equal_highs_lows_detection(self):
        """Verify equal highs / equal lows within tight tolerance."""
        highs = [65000.0] * 5 + [65500.0, 65100.0, 65200.0, 65502.0, 65100.0]  # 65500.0 and 65502.0 are EQH
        lows = [64000.0] * len(highs)

        res = detect_equal_highs_lows(highs, lows, self.now_ms, "BTC-USDT", lookback=10, tolerance_pct=0.001)
        self.assertTrue(res.detected)
        self.assertEqual(res.measurements["structure"], "EQUAL_HIGHS")

    def test_displacement_impulse_detection(self):
        """Verify large impulse candle triggers displacement detector."""
        opens = [65000.0] * 15 + [65100.0]
        highs = [65050.0] * 15 + [66000.0]
        lows = [64950.0] * 15 + [65050.0]
        closes = [65000.0] * 15 + [65950.0]  # Body = 850.0 vs typical ATR ~100.0

        res = detect_displacement(opens, highs, lows, closes, self.now_ms, "BTC-USDT", atr_lookback=14)
        self.assertTrue(res.detected)
        self.assertEqual(res.direction, "BULLISH")
        self.assertGreater(res.measurements["body_to_atr"], 2.0)

    def test_cvd_divergence_detection(self):
        """Verify price vs CVD divergence detection."""
        # Bearish divergence: Price makes higher high, CVD makes lower high
        prices = [65000, 65100, 65050, 65200, 65150, 65300, 65400, 65350, 65500, 65600]
        cvd = [1000, 1500, 1400, 1800, 1600, 1200, 1100, 900, 800, 700]

        res = detect_cvd_divergence(prices, cvd, self.now_ms, "BTC-USDT", lookback=10)
        self.assertTrue(res.detected)
        self.assertEqual(res.direction, "BEARISH")
        self.assertEqual(res.measurements["type"], "REGULAR_BEARISH_DIVERGENCE")

    # -------------------------------------------------------------
    # 3. MARKET-STATE COMPOSITION & IMMUTABILITY
    # -------------------------------------------------------------
    def test_market_state_compiler_and_immutability(self):
        """Verify MarketState compiles deterministically and is immutable."""
        closes = [65000.0 + i * 10 for i in range(25)]
        highs = [c + 20 for c in closes]
        lows = [c - 20 for c in closes]
        volumes = [100.0] * 25

        ms = MarketStateEngine.compile(
            symbol="BTC-USDT",
            timestamp=self.now_ms,
            timeframe="5m",
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            current_price=closes[-1],
            vwap=65100.0,
            supertrend_direction="BULLISH"
        )

        self.assertIsInstance(ms, MarketState)
        self.assertEqual(ms.symbol, "BTC-USDT")
        self.assertEqual(ms.trend_state, "BULLISH")
        self.assertIn("vwap_diff_pct", ms.metrics)

        # Immutability check: modifying attributes must raise FrozenInstanceError
        with self.assertRaises(Exception):
            ms.trend_state = "BEARISH"

    # -------------------------------------------------------------
    # 4. KRONOS ADVISORY SAFETY TESTS
    # -------------------------------------------------------------
    def test_kronos_strictly_advisory_safety(self):
        """Verify Kronos advisor generates advisory reports and CANNOT execute or authorize orders."""
        ms = MarketState(
            symbol="BTC-USDT",
            timestamp=self.now_ms,
            timeframe="5m",
            trend_state="BULLISH",
            volatility_state="EXPANDED",
            volume_state="SURGE",
            vwap_state="CLEAR_ABOVE",
            cvd_state="BULLISH_DELTA",
            order_flow_state="BUY_DOMINANT",
            liquidity_state="NORMAL",
            displacement_state="IMPULSE_UP",
            session_state="LONDON",
            data_quality="VALID",
            confidence=0.85,
            metrics={"vwap_diff_pct": 0.45}
        )

        report = KronosAdvisor.evaluate_market_state(ms)
        self.assertIsInstance(report, KronosAdvisoryReport)
        self.assertTrue(report.is_advisory)
        self.assertFalse(report.execution_authority)
        self.assertEqual(report.sentiment, "BULLISH")
        self.assertIn("EXPANDED", report.risk_warnings[0])

        # Execution authority checks: Must explicitly raise PermissionError
        with self.assertRaises(PermissionError):
            KronosAdvisor.execute_order("BTC-USDT", "BUY", 1.0)

        with self.assertRaises(PermissionError):
            KronosAdvisor.authorize_trade("BTC-USDT")

    # -------------------------------------------------------------
    # 5. RESEARCH EVALUATION FRAMEWORK TESTS
    # -------------------------------------------------------------
    def test_feature_evaluator_excursions(self):
        """Verify research backtest harness calculates MFE, MAE, and win rates."""
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        highs = [100.5, 101.5, 102.5, 103.5, 104.5, 105.5]
        lows = [99.5, 100.5, 101.5, 102.5, 103.5, 104.5]

        summary = FeatureEvaluator.evaluate_events(
            feature_name="TEST_IMPULSE",
            symbol="BTC-USDT",
            timeframe="1m",
            closes=closes,
            highs=highs,
            lows=lows,
            event_indices=[0],
            event_directions=["LONG"],
            horizon_bars=4,
            target_pct=1.0,
            stop_pct=0.5
        )

        self.assertEqual(summary.sample_size, 1)
        self.assertEqual(summary.win_rate_pct, 100.0)
        self.assertGreater(summary.avg_mfe_pct, 0.0)

    # -------------------------------------------------------------
    # 6. GLOBAL SAFETY INVARIANTS & ENDPOINT INTEGRATION
    # -------------------------------------------------------------
    def test_global_max_open_trades_invariant(self):
        """Verify MAX_OPEN_TRADES = 2 invariant is strictly preserved."""
        self.assertEqual(config.MAX_OPEN_TRADES, 2)

    def test_ml_and_world_api_endpoints_contracts(self):
        """Verify ML state and WORLD context endpoints return valid contracts."""
        from control_plane.api import get_ml_state_data, get_world_context_data

        # ML state contract
        ml_resp = get_ml_state_data(symbol="BTC-USDT")
        self.assertIn("regime", ml_resp)
        self.assertIn("sentiment", ml_resp)
        self.assertIn("confidence", ml_resp)
        self.assertTrue(ml_resp["is_advisory"])
        self.assertFalse(ml_resp["execution_authority"])
        self.assertIn("ADVISORY ONLY", ml_resp["advisory_notice"])

        # WORLD context contract
        world_resp = get_world_context_data()
        self.assertIn("session_context", world_resp)
        self.assertIn("market_environment", world_resp)
        self.assertIn("macro_events", world_resp)
        self.assertIn("NO AUTONOMOUS EXECUTION", world_resp["notice"])


if __name__ == "__main__":
    unittest.main()
