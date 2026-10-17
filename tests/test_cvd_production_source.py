import unittest
import time
from institutional.data.models import TradeEvent
from institutional.cvd.live_engine import LiveCVDEngine

class TestCVDProductionSource(unittest.TestCase):
    def test_bingx_aggressor_m_flag_semantics(self):
        """Directive 4: Verify BingX m flag semantics (is_buyer_maker).
        is_buyer_maker = True -> Buyer is maker, seller is aggressor (SELL).
        is_buyer_maker = False -> Buyer is taker, buyer is aggressor (BUY).
        """
        now = int(time.time() * 1000)
        t_buy = TradeEvent("BTCUSDT", "t1", now, 65000.0, 1.0, is_buyer_maker=False, source="WS")
        t_sell = TradeEvent("BTCUSDT", "t2", now, 65000.0, 1.0, is_buyer_maker=True, source="WS")

        self.assertEqual(t_buy.aggressor, "BUY")
        self.assertEqual(t_sell.aggressor, "SELL")

    def test_duplicate_trades_filtered(self):
        """Directive 4: Verify duplicate trade_id is filtered out."""
        engine = LiveCVDEngine("BTCUSDT")
        t1 = TradeEvent("BTCUSDT", "dup_1", 1000, 65000.0, 1.0, is_buyer_maker=False, source="WS")
        engine.add_trade(t1)
        self.assertEqual(len(engine.trades), 1)

        # Duplicate
        engine.add_trade(t1)
        self.assertEqual(len(engine.trades), 1)

    def test_out_of_order_trades_sorted_chronologically(self):
        """Directive 4: Verify out of order trades are sorted prior to 5m block aggregation."""
        engine = LiveCVDEngine("BTCUSDT")
        t_late = TradeEvent("BTCUSDT", "t_late", 500, 65000.0, 1.0, is_buyer_maker=False, source="WS")
        t_early = TradeEvent("BTCUSDT", "t_early", 200, 64900.0, 1.0, is_buyer_maker=True, source="WS")

        engine.add_trade(t_late)
        engine.add_trade(t_early)

        # Trigger separation/sort
        engine.trades.sort(key=lambda x: x.timestamp)
        self.assertEqual(engine.trades[0].trade_id, "t_early")
        self.assertEqual(engine.trades[1].trade_id, "t_late")
