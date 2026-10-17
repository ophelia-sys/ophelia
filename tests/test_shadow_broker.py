import os
import unittest
from unittest.mock import patch, MagicMock
from core.errors import ShadowModeIsolationError
from brokers.shadow_broker import ShadowBroker
from exchange.bingx_client import BingXClient

class TestShadowBrokerIsolation(unittest.TestCase):

    def setUp(self):
        self.broker = ShadowBroker()

    def test_shadow_broker_blocks_place_market_order(self):
        with self.assertRaises(ShadowModeIsolationError):
            self.broker.place_market_order("BTC-USDT", "LONG", 0.01)

    def test_shadow_broker_blocks_place_limit_order(self):
        with self.assertRaises(ShadowModeIsolationError):
            self.broker.place_limit_order("BTC-USDT", "LONG", 0.01, 50000.0)

    def test_shadow_broker_blocks_process_signal_for_entries(self):
        # A valid HOLD or LONG_CANDIDATE should not raise an error (it just ignores it safely)
        self.assertIsNone(self.broker.process_signal({"signal": "HOLD"}))
        self.assertIsNone(self.broker.process_signal({"signal": "LONG_CANDIDATE"}))
        
        # But attempting to process a live actionable signal like "LONG" or "SHORT" should raise
        with self.assertRaises(ShadowModeIsolationError):
            self.broker.process_signal({"signal": "LONG"})
            
    def test_bingx_client_http_post_isolation(self):
        # Ensure that if OPHELIA_MODE is SHADOW, the client strictly blocks order POST requests
        with patch.dict(os.environ, {"OPHELIA_MODE": "SHADOW", "BINGX_API_KEY": "test", "BINGX_SECRET_KEY": "test"}):
            client = BingXClient()
            with self.assertRaises(ShadowModeIsolationError):
                client._post("/openApi/swap/v2/trade/order", {"symbol": "BTC-USDT"})

if __name__ == '__main__':
    unittest.main()
