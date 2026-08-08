"""
Focused Non-Live Unit Test Suite for Live Partial Exit Order Construction.

Verifies OrderManager.close_long and close_short signatures,
OrderRequest parameter construction, and full-close backward compatibility.
No real orders are placed.
"""

import sys
import unittest
from unittest.mock import MagicMock

from core.enums import OrderSide, OrderType, PositionSide
from exchange.order_manager import OrderManager
from models.order_request import OrderRequest
from models.position import Position


class TestLivePartialExitOrderConstruction(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.get_contract.return_value = MagicMock(
            symbol="SOL-USDT",
            quantity_precision=2,
            min_quantity=0.01,
        )
        self.order_manager = OrderManager(self.mock_client)

    def test_01_partial_close_long_order_request_construction(self):
        # Position of 1.0 SOL-USDT LONG
        mock_position = Position(
            symbol="SOL-USDT",
            side=PositionSide.LONG,
            quantity=1.0,
            entry_price=100.0,
            mark_price=105.0,
            unrealized_pnl=5.0,
            leverage=20,
            position_id=101,
        )
        self.mock_client.get_positions.return_value = [mock_position]
        self.mock_client.place_order.return_value = MagicMock(order_id=555)

        # Trigger partial close of 0.25 SOL-USDT for LONG
        res = self.order_manager.close_long(
            symbol="SOL-USDT",
            quantity=0.25,
            client_order_id="INTENT_PARTIAL_LONG_123",
        )

        self.mock_client.place_order.assert_called_once()
        order_req: OrderRequest = self.mock_client.place_order.call_args[0][0]

        self.assertEqual(order_req.symbol, "SOL-USDT")
        self.assertEqual(order_req.side, OrderSide.SELL)
        self.assertEqual(order_req.position_side, PositionSide.LONG)
        self.assertEqual(order_req.order_type, OrderType.MARKET)
        self.assertEqual(order_req.quantity, 0.25)
        self.assertEqual(order_req.client_order_id, "INTENT_PARTIAL_LONG_123")
        self.assertTrue(order_req.reduce_only)

    def test_02_partial_close_short_order_request_construction(self):
        # Position of 1.0 SOL-USDT SHORT
        mock_position = Position(
            symbol="SOL-USDT",
            side=PositionSide.SHORT,
            quantity=1.0,
            entry_price=100.0,
            mark_price=95.0,
            unrealized_pnl=5.0,
            leverage=20,
            position_id=202,
        )
        self.mock_client.get_positions.return_value = [mock_position]
        self.mock_client.place_order.return_value = MagicMock(order_id=777)

        # Trigger partial close of 0.5 SOL-USDT for SHORT
        res = self.order_manager.close_short(
            symbol="SOL-USDT",
            quantity=0.5,
            client_order_id="INTENT_PARTIAL_SHORT_456",
        )

        self.mock_client.place_order.assert_called_once()
        order_req: OrderRequest = self.mock_client.place_order.call_args[0][0]

        self.assertEqual(order_req.symbol, "SOL-USDT")
        self.assertEqual(order_req.side, OrderSide.BUY)
        self.assertEqual(order_req.position_side, PositionSide.SHORT)
        self.assertEqual(order_req.order_type, OrderType.MARKET)
        self.assertEqual(order_req.quantity, 0.5)
        self.assertEqual(order_req.client_order_id, "INTENT_PARTIAL_SHORT_456")
        self.assertTrue(order_req.reduce_only)

    def test_03_full_close_backward_compatibility(self):
        mock_position = Position(
            symbol="SOL-USDT",
            side=PositionSide.LONG,
            quantity=1.0,
            entry_price=100.0,
            mark_price=105.0,
            unrealized_pnl=5.0,
            leverage=20,
            position_id=101,
        )
        self.mock_client.get_positions.return_value = [mock_position]

        # Call close_long without quantity (full close)
        self.order_manager.close_long(symbol="SOL-USDT")

        # Must call close_position(101) by position_id and NOT place_order
        self.mock_client.close_position.assert_called_once_with(101)
        self.mock_client.place_order.assert_not_called()

    def test_04_quantity_capped_at_position_quantity(self):
        mock_position = Position(
            symbol="SOL-USDT",
            side=PositionSide.LONG,
            quantity=0.5,
            entry_price=100.0,
            mark_price=105.0,
            unrealized_pnl=2.5,
            leverage=20,
            position_id=101,
        )
        self.mock_client.get_positions.return_value = [mock_position]

        # Attempt to partial close 2.0 when position quantity is 0.5
        # Since 2.0 >= 0.5, it should execute a full position close via position_id
        self.order_manager.close_long(symbol="SOL-USDT", quantity=2.0)
        self.mock_client.close_position.assert_called_once_with(101)

    def test_05_no_close_all_positions_fallback(self):
        self.mock_client.get_positions.return_value = []
        res = self.order_manager.close_long(symbol="SOL-USDT", quantity=0.1)

        self.assertIsNone(res)
        self.mock_client.close_all_positions.assert_not_called()


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLivePartialExitOrderConstruction)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
