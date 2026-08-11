import unittest
from institutional.compatibility import V3Translator
from institutional.types import MarketState, DataQuality, MicrostructureState
from core.institutional_math import MathAnalysis

class TestV3ShadowMode(unittest.TestCase):

    def test_v3_translator_valid_data(self):
        state = MarketState(
            symbol="BTC-USDT",
            timestamp=1234567890,
            timeframe="1m",
            volatility_score=8,
            momentum_score=1.5,
            trend_persistence=0.7,
            data_quality=DataQuality.VALID
        )
        
        analysis = V3Translator.translate(state)
        
        # Volatility maps directly 8 -> 8.0
        self.assertEqual(analysis.volatility_score, 8.0)
        
        # Momentum Z-Score 1.5 -> 1.5 * 3.33 = 4.995 (round to 5.0)
        self.assertEqual(analysis.momentum_score, 5.0)
        
        # Trend 0.7 -> 0.7 * 10 = 7.0
        self.assertEqual(analysis.trend_persistence_score, 7.0)

    def test_v3_translator_insufficient_data(self):
        state = MarketState(
            symbol="BTC-USDT",
            timestamp=1234567890,
            timeframe="1m",
            volatility_score=8,
            momentum_score=1.5,
            trend_persistence=0.7,
            data_quality=DataQuality.INSUFFICIENT_DATA
        )
        
        analysis = V3Translator.translate(state)
        
        self.assertEqual(analysis.volatility_score, "UNAVAILABLE")
        self.assertEqual(analysis.momentum_score, "UNAVAILABLE")
        self.assertEqual(analysis.trend_persistence_score, "UNAVAILABLE")

    def test_ofi_remains_unavailable(self):
        state = MarketState(
            symbol="BTC-USDT",
            timestamp=1234567890,
            timeframe="1m",
            data_quality=DataQuality.VALID
        )
        analysis = V3Translator.translate(state)
        self.assertEqual(analysis.order_flow_state, "UNAVAILABLE")
        # Legacy contract has no 'ofi' field, proving it cannot leak into DecisionEngine's core math logic.

    def test_microstructure_preserves_identity(self):
        micro_state = MicrostructureState(
            depth_imbalance=0.45,
            queue_imbalance=-0.2,
            data_quality=DataQuality.VALID
        )
        state = MarketState(
            symbol="BTC-USDT",
            timestamp=1234567890,
            timeframe="1m",
            microstructure=micro_state,
            data_quality=DataQuality.VALID
        )
        
        # The translation process does not alias these to OFI
        analysis = V3Translator.translate(state)
        self.assertEqual(analysis.order_flow_state, "UNAVAILABLE")

    def test_v3_exception_isolation(self):
        from core.decision_engine import DecisionEngine
        import pandas as pd
        from unittest.mock import patch

        engine = DecisionEngine()
        # Provide 6 minutes of data so resampling to 5m yields a completed bar.
        df_1m = pd.DataFrame({
            "timestamp": [
                pd.Timestamp("2024-01-01 00:00:00"),
                pd.Timestamp("2024-01-01 00:01:00"),
                pd.Timestamp("2024-01-01 00:02:00"),
                pd.Timestamp("2024-01-01 00:03:00"),
                pd.Timestamp("2024-01-01 00:04:00"),
                pd.Timestamp("2024-01-01 00:05:00")
            ],
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.5] * 6,
            "volume": [10.0] * 6
        })
        signal = {"signal": "BUY", "cross": "UP"}
        
        # Test normal execution
        normal_analysis = engine.evaluate("BTC-USDT", df_1m, signal)
        
        # Test execution with V3 failure
        with patch("institutional.institutional_math.InstitutionalMathEngine.analyze", side_effect=Exception("Simulated V3 Crash")):
            crash_analysis = engine.evaluate("BTC-USDT", df_1m, signal)
            
        # The output must be perfectly identical
        self.assertEqual(normal_analysis, crash_analysis)

