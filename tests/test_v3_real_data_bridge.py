import unittest
import copy
from unittest.mock import patch, MagicMock
import pandas as pd

from core.decision_engine import DecisionEngine
from core.scanner import Scanner
from institutional.data.engine import InstitutionalDataEngine
from institutional.types import DataQuality, MicrostructureState, MarketState
from institutional.data.models import MarketDataSnapshot, OrderBookSnapshot, OHLCVBar
from institutional.institutional_math import InstitutionalMathEngine as InstitutionalMathEngineV3
from core.settings import TradingSettings


class TestV3RealDataBridge(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()
        # Provide 6 minutes of data so resampling to 5m yields a completed bar.
        self.df_1m = pd.DataFrame({
            "timestamp": [
                pd.Timestamp("2024-01-01 00:00:00"),
                pd.Timestamp("2024-01-01 00:01:00"),
                pd.Timestamp("2024-01-01 00:02:00"),
                pd.Timestamp("2024-01-01 00:03:00"),
                pd.Timestamp("2024-01-01 00:04:00"),
                pd.Timestamp("2024-01-01 00:05:00")
            ],
            "open": [100.0] * 6,
            "high": [100.1] * 6,
            "low": [99.9] * 6,
            "close": [100.05] * 6,
            "volume": [10.0] * 6
        })
        self.signal = {"signal": "BUY", "cross": "UP"}

        self.mock_snapshot = MarketDataSnapshot(
            symbol="BTC-USDT",
            timestamp=1000000,
            timeframe="1m",
            ohlcv=[],
            data_quality=DataQuality.VALID,
            order_book=OrderBookSnapshot(
                symbol="BTC-USDT",
                timestamp=1000000,
                bids=[[64740.0, 1.0]],
                asks=[[64745.0, 1.0]],
                source="TEST"
            ),
            cvd=1234.5,
            tvi=0.42,
            microstructure=MicrostructureState(
                mid_price=64742.5,
                spread=5.0,
                queue_imbalance=-0.31,
                depth_imbalance=0.73,
                microprice=64742.12
            )
        )

    def test_lineage_metrics_reach_v3(self):
        # A, B, C, I - Lineage Test
        with patch.object(InstitutionalMathEngineV3, 'analyze') as mock_analyze:
            # We mock the return state to something valid so V3Translator doesn't blow up
            dummy_state = MarketState(
                symbol="BTC-USDT", timestamp=1000, timeframe="1m",
                microstructure=self.mock_snapshot.microstructure
            )
            mock_analyze.return_value = dummy_state

            analysis = self.engine.evaluate("BTC-USDT", self.df_1m, self.signal, snapshot=self.mock_snapshot)
            
            # Assert evaluate ran without error
            self.assertIsNotNone(analysis)

            # Check that analyze was called with our real snapshot
            mock_analyze.assert_called_once_with(self.mock_snapshot)
            
            # Ensure the snapshot was the one with the exact metrics we provided
            called_snapshot = mock_analyze.call_args[0][0]
            self.assertEqual(called_snapshot.microstructure.depth_imbalance, 0.73)
            self.assertEqual(called_snapshot.microstructure.queue_imbalance, -0.31)
            self.assertEqual(called_snapshot.microstructure.microprice, 64742.12)
            self.assertEqual(called_snapshot.cvd, 1234.5)
            self.assertEqual(called_snapshot.tvi, 0.42)

    def test_missing_data_unavailable(self):
        # D - Missing data remains unavailable
        partial_snapshot = MarketDataSnapshot(
            symbol="BTC-USDT",
            timestamp=1000000,
            timeframe="1m",
            ohlcv=[],
            data_quality=DataQuality.UNAVAILABLE,
            order_book=None,
            cvd=None,
            tvi=None,
            microstructure=MicrostructureState(
                mid_price=None, spread=None, queue_imbalance=None, depth_imbalance=None, microprice=None
            )
        )
        with patch.object(InstitutionalMathEngineV3, 'analyze') as mock_analyze:
            dummy_state = MarketState(
                symbol="BTC-USDT", timestamp=1000, timeframe="1m",
                microstructure=partial_snapshot.microstructure
            )
            mock_analyze.return_value = dummy_state
            
            self.engine.evaluate("BTC-USDT", self.df_1m, self.signal, snapshot=partial_snapshot)
            called_snapshot = mock_analyze.call_args[0][0]
            self.assertIsNone(called_snapshot.cvd)
            self.assertIsNone(called_snapshot.microstructure.depth_imbalance)

    def test_scanner_passes_snapshot(self):
        # Ensure scanner logic connects properly
        inst_data = MagicMock(spec=InstitutionalDataEngine)
        inst_data.get_snapshot.return_value = self.mock_snapshot
        
        scanner = Scanner(institutional_data=inst_data)
        scanner.strategy = MagicMock()
        scanner.strategy.get_signal.return_value = {"signal": "BUY", "cross": "UP"}
        scanner.market = MagicMock()
        scanner.market.get_klines.return_value = self.df_1m
        
        with patch.object(DecisionEngine, 'evaluate') as mock_eval:
            scanner.scan_symbol("BTC-USDT")
            inst_data.get_snapshot.assert_called_with("BTC-USDT")
            
            # evaluate should be called with snapshot
            mock_eval.assert_called_once()
            self.assertEqual(mock_eval.call_args[1]["snapshot"], self.mock_snapshot)

    def test_scanner_handles_institutional_failure(self):
        # F - InstitutionalDataEngine failure cannot break the legacy decision
        inst_data = MagicMock(spec=InstitutionalDataEngine)
        inst_data.get_snapshot.side_effect = Exception("Simulated DB Crash")
        
        scanner = Scanner(institutional_data=inst_data)
        scanner.strategy = MagicMock()
        scanner.strategy.get_signal.return_value = {"signal": "BUY", "cross": "UP"}
        scanner.market = MagicMock()
        scanner.market.get_klines.return_value = self.df_1m
        
        with patch.object(DecisionEngine, 'evaluate') as mock_eval:
            scanner.scan_symbol("BTC-USDT")
            mock_eval.assert_called_once()
            # snapshot should be None due to crash
            self.assertIsNone(mock_eval.call_args[1].get("snapshot"))
            
    def test_ofi_remains_unavailable(self):
        # H - OFI cannot inherit any proxy
        with patch.object(InstitutionalMathEngineV3, 'analyze') as mock_analyze:
            dummy_state = MarketState(
                symbol="BTC-USDT", timestamp=1000, timeframe="1m",
                microstructure=self.mock_snapshot.microstructure
            )
            mock_analyze.return_value = dummy_state

            analysis = self.engine.evaluate("BTC-USDT", self.df_1m, self.signal, snapshot=self.mock_snapshot)
            self.assertEqual(analysis.math.order_flow_state, "UNAVAILABLE")
            self.assertNotEqual(analysis.math.order_flow_state, dummy_state.microstructure.depth_imbalance)

    def test_v3_isolation_preservation(self):
        # E, G - V3 exception cannot break legacy decision, cannot modify live decision
        normal_analysis = self.engine.evaluate("BTC-USDT", self.df_1m, self.signal, snapshot=self.mock_snapshot)
        
        # We'll make it raise an exception
        with patch.object(InstitutionalMathEngineV3, 'analyze', side_effect=Exception("V3 Catastrophic Error")):
            crash_analysis = self.engine.evaluate("BTC-USDT", self.df_1m, self.signal, snapshot=self.mock_snapshot)
            
            self.assertIsNotNone(crash_analysis)
            self.assertEqual(crash_analysis.approved, True) # Passed normal rules
            self.assertEqual(normal_analysis, crash_analysis)
