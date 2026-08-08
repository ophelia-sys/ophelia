"""
Ophelia Telegram Strategy Settings, Advanced Risk Management, and Safety Test Suite.

Validates all risk, SL/TP, trailing, partial position, and safety requirements.
No live/paper orders submitted during execution.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

import config
from core.enums import EngineState
from core.settings import TradingSettings
from core.trading_engine import TradingEngine
from risk.risk_manager import RiskManager
from telegram.bot_adapter import TelegramAdapter


class TestOpheliaAdvancedRiskAndSafety(unittest.TestCase):

    def setUp(self):
        config.LIVE_TRADING = False
        config.ENABLE_TELEGRAM = False
        config.TELEGRAM_TOKEN = ""
        config.TELEGRAM_ALLOWED_USER_IDS = [123456789]
        if os.path.exists("data/settings.json"):
            try:
                os.remove("data/settings.json")
            except Exception:
                pass

    def test_01_percentage_sl_long_and_short(self):
        sl_long = RiskManager.calculate_sl_price(100.0, "LONG", "PRICE_PERCENT", 1.0)
        self.assertAlmostEqual(sl_long, 99.0)

        sl_short = RiskManager.calculate_sl_price(100.0, "SHORT", "PRICE_PERCENT", 1.0)
        self.assertAlmostEqual(sl_short, 101.0)

    def test_02_fixed_loss_sl(self):
        # Entry = 100.0, loss = 2 USDT, quantity = 0.1
        # Price delta = 2 / 0.1 = 20.0
        sl_long = RiskManager.calculate_sl_price(100.0, "LONG", "FIXED_LOSS", 2.0, quantity=0.1)
        self.assertAlmostEqual(sl_long, 80.0)

        sl_short = RiskManager.calculate_sl_price(100.0, "SHORT", "FIXED_LOSS", 2.0, quantity=0.1)
        self.assertAlmostEqual(sl_short, 120.0)

    def test_03_percentage_tp_long_and_short(self):
        tp_long = RiskManager.calculate_tp_price(100.0, "LONG", "PRICE_PERCENT", 2.0)
        self.assertAlmostEqual(tp_long, 102.0)

        tp_short = RiskManager.calculate_tp_price(100.0, "SHORT", "PRICE_PERCENT", 2.0)
        self.assertAlmostEqual(tp_short, 98.0)

    def test_04_trailing_activation_and_buffer(self):
        # Activation = 1.0%, Buffer = 0.8%
        # Price 100.5 -> profit 0.5% (< activation 1.0%) -> stop remains None
        stop1 = RiskManager.calculate_trailing_stop(100.0, 100.5, "LONG", trailing_activation=1.0, trailing_buffer=0.8)
        self.assertIsNone(stop1)

        # Price 101.5 -> profit 1.5% (>= activation 1.0%) -> candidate stop = 101.5 * (1 - 0.008) = 100.688
        stop2 = RiskManager.calculate_trailing_stop(100.0, 101.5, "LONG", trailing_activation=1.0, trailing_buffer=0.8)
        self.assertAlmostEqual(stop2, 100.688)

    def test_05_trailing_movement_and_never_backward(self):
        # LONG: Stop follows highest price upward only
        stop1 = RiskManager.calculate_trailing_stop(100.0, 102.0, "LONG", trailing_activation=1.0, trailing_buffer=0.8)
        # 102.0 * (1 - 0.008) = 101.184
        self.assertAlmostEqual(stop1, 101.184)

        # Price drops to 101.5 -> Stop must NOT move backward
        stop2 = RiskManager.calculate_trailing_stop(100.0, 101.5, "LONG", trailing_activation=1.0, trailing_buffer=0.8, current_stop=stop1)
        self.assertEqual(stop2, stop1)

        # SHORT: Stop follows lowest price downward only
        stop_short1 = RiskManager.calculate_trailing_stop(100.0, 98.0, "SHORT", trailing_activation=1.0, trailing_buffer=0.8)
        # 98.0 * (1 + 0.008) = 98.784
        self.assertAlmostEqual(stop_short1, 98.784)

        # Price rises to 98.5 -> Stop must NOT move backward
        stop_short2 = RiskManager.calculate_trailing_stop(100.0, 98.5, "SHORT", trailing_activation=1.0, trailing_buffer=0.8, current_stop=stop_short1)
        self.assertEqual(stop_short2, stop_short1)

    def test_06_per_symbol_settings(self):
        engine = TradingEngine()
        engine.update_sl_setting("PRICE_PERCENT", 1.0)
        engine.update_sl_setting("PRICE_PERCENT", 0.7, symbol="BTC-USDT")

        global_cfg = engine.settings.get_risk_config(None)
        btc_cfg = engine.settings.get_risk_config("BTC-USDT")

        self.assertEqual(global_cfg["sl_value"], 1.0)
        self.assertEqual(btc_cfg["sl_value"], 0.7)

    def test_07_exit_plan_100_percent_validation(self):
        # Valid exit plan
        valid, err, legs = TradingSettings.parse_exit_plan(["25@1.0", "25@2.0", "50@trailing"])
        self.assertTrue(valid)
        self.assertEqual(len(legs), 3)

        # Invalid sum != 100%
        valid, err, legs = TradingSettings.parse_exit_plan(["25@1.0", "25@2.0"])
        self.assertFalse(valid)

        # Negative leg %
        valid, err, legs = TradingSettings.parse_exit_plan(["-25@1.0", "125@2.0"])
        self.assertFalse(valid)

    def test_08_partial_tp_and_remaining_quantity(self):
        engine = TradingEngine()
        # Open 1.0 SOL-USDT position at 100.0 with exit plan [50% @ +2%, 50% @ trailing]
        risk_cfg = {
            "sl_mode": "PRICE_PERCENT",
            "sl_value": 5.0,
            "tp_mode": "PRICE_PERCENT",
            "tp_value": 2.0,
            "trailing_activation": 1.0,
            "trailing_buffer": 0.8,
            "exit_plan": [{"pct": 50.0, "type": "tp", "target_pct": 2.0}, {"pct": 50.0, "type": "trailing"}],
        }

        # Open position
        engine.broker.process_signal(
            {"symbol": "SOL-USDT", "signal": "BUY", "price": 100.0, "timestamp": 1000},
            engine.risk_manager,
            risk_config=risk_cfg
        )
        pos = engine.position_manager.get_position("SOL-USDT")
        self.assertIsNotNone(pos)
        initial_qty = pos.quantity

        # Price rises to 102.5 (profit 2.5% >= 2.0%) -> 50% partial TP leg triggers
        engine.broker.process_signal(
            {"symbol": "SOL-USDT", "signal": "HOLD", "price": 102.5, "timestamp": 1010},
            engine.risk_manager,
            risk_config=risk_cfg
        )
        pos_after = engine.position_manager.get_position("SOL-USDT")
        self.assertIsNotNone(pos_after)
        self.assertAlmostEqual(pos_after.quantity, initial_qty * 0.5)

        # Trade journal should record PARTIAL_TP
        recent = engine.get_recent_trades(limit=5)
        last_trade = recent[-1]
        self.assertEqual(last_trade["status"], "PARTIAL_TP")
        self.assertAlmostEqual(float(last_trade["quantity"]), initial_qty * 0.5)

    def test_09_no_duplicate_partial_exits_and_total_quantity_cap(self):
        engine = TradingEngine()
        risk_cfg = {
            "sl_mode": "PRICE_PERCENT",
            "sl_value": 5.0,
            "tp_mode": "PRICE_PERCENT",
            "tp_value": 2.0,
            "trailing_activation": 1.0,
            "trailing_buffer": 0.8,
            "exit_plan": [{"pct": 50.0, "type": "tp", "target_pct": 2.0}, {"pct": 50.0, "type": "trailing"}],
        }

        engine.broker.process_signal(
            {"symbol": "SOL-USDT", "signal": "BUY", "price": 100.0, "timestamp": 1000},
            engine.risk_manager,
            risk_config=risk_cfg
        )
        pos = engine.position_manager.get_position("SOL-USDT")

        # Cycle 1: Triggers 50% partial TP
        engine.broker.process_signal(
            {"symbol": "SOL-USDT", "signal": "HOLD", "price": 102.5, "timestamp": 1010},
            engine.risk_manager,
            risk_config=risk_cfg
        )

        # Cycle 2: Same price 102.5 -> TP leg already executed, must NOT trigger duplicate partial exit
        qty_before_cycle2 = engine.position_manager.get_position("SOL-USDT").quantity
        engine.broker.process_signal(
            {"symbol": "SOL-USDT", "signal": "HOLD", "price": 102.5, "timestamp": 1020},
            engine.risk_manager,
            risk_config=risk_cfg
        )
        qty_after_cycle2 = engine.position_manager.get_position("SOL-USDT").quantity
        self.assertEqual(qty_before_cycle2, qty_after_cycle2)

    def test_10_protection_only_overrides_entry_automation(self):
        engine = TradingEngine()
        engine.protection_only_mode = True
        engine.protection_degraded = True
        engine.engine_state = EngineState.PROTECTION_ONLY
        engine.scanner.last_failed_symbols = ["BTC-USDT"]

        engine.scanner.scan = MagicMock(return_value=[{"symbol": "BTC-USDT", "signal": "BUY", "price": 50000.0, "timestamp": 1000}])
        engine.broker.process_signal = MagicMock()

        engine.process_market()
        # New signal entry blocked in PROTECTION_ONLY
        for call in engine.broker.process_signal.call_args_list:
            sig = call[0][0]
            if sig.get("symbol") == "BTC-USDT":
                self.assertNotEqual(sig.get("signal"), "BUY")

    def test_11_telegram_no_direct_orders_or_creds(self):
        engine = TradingEngine()
        adapter = TelegramAdapter(engine)
        self.assertFalse(hasattr(adapter, "client"))
        self.assertFalse(hasattr(adapter, "order_manager"))
        status_str = str(engine.get_status_summary())
        self.assertNotIn("secret", status_str.lower())
        self.assertNotIn("key", status_str.lower())


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOpheliaAdvancedRiskAndSafety)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
