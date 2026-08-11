import unittest
import numpy as np
import time
import pandas as pd
from institutional.institutional_math import InstitutionalMathEngine
from institutional.data.models import MarketDataSnapshot, OHLCVBar, OrderBookSnapshot
from institutional.types import DataQuality

class TestInstitutionalMathEngine(unittest.TestCase):
    def setUp(self):
        self.engine = InstitutionalMathEngine(normalization_window=50)

    def test_insufficient_data(self):
        snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "5m", ohlcv=[])
        state = self.engine.analyze(snapshot)
        self.assertEqual(state.data_quality, DataQuality.INSUFFICIENT_DATA)

        # Small DataFrame
        df = pd.DataFrame({"close": [1.0] * 10})
        bars = [OHLCVBar("BTC-USDT", i, 1.0, 1.0, 1.0, row["close"], 10.0, "TEST") for i, row in df.iterrows()]
        snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "5m", ohlcv=bars)
        state = self.engine.analyze(snapshot)
        self.assertEqual(state.data_quality, DataQuality.INSUFFICIENT_DATA)

    def test_synthetic_data_processing(self):
        # Generate 100 random candles
        np.random.seed(42)
        close = np.cumsum(np.random.randn(100)) + 1000
        df = pd.DataFrame({
            "open": close + np.random.randn(100),
            "high": close + np.abs(np.random.randn(100)) + 1,
            "low": close - np.abs(np.random.randn(100)) - 1,
            "close": close,
            "volume": np.random.rand(100) * 100
        })

        bars = [OHLCVBar("BTC-USDT", i, row["open"], row["high"], row["low"], row["close"], row["volume"], "TEST") for i, row in df.iterrows()]
        
        book_snapshot = OrderBookSnapshot("BTC-USDT", int(time.time()*1000), [[1000.0, 1]], [[1000.5, 1]], "TEST")
        snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "5m", ohlcv=bars, order_book=book_snapshot)
        state = self.engine.analyze(snapshot)
        
        # We gave it 100 candles, but window is 50, so it should be VALID
        self.assertEqual(state.data_quality, DataQuality.VALID)
        self.assertEqual(state.oi_state, "INSUFFICIENT_DATA")

    def test_nan_handling(self):
        # Insert NaNs in the data
        df = pd.DataFrame({
            "open": [100.0] * 60,
            "high": [105.0] * 60,
            "low": [95.0] * 60,
            "close": [100.0] * 60,
            "volume": [1000.0] * 60
        })
        
        # Inject NaNs at the end
        df.loc[58:, "close"] = np.nan
        df.loc[59:, "volume"] = np.nan

        bars = [OHLCVBar("BTC-USDT", i, row["open"], row["high"], row["low"], row["close"], row["volume"], "TEST") for i, row in df.iterrows()]
        snapshot = MarketDataSnapshot("BTC-USDT", int(time.time()*1000), "5m", ohlcv=bars)
        state = self.engine.analyze(snapshot)
        
        # Should not crash. Results might be None or NaN, but it should return a MarketState
        self.assertTrue(hasattr(state, "symbol"))
        self.assertEqual(state.symbol, "BTC-USDT")

if __name__ == "__main__":
    unittest.main()
