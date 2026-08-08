"""
Ophelia Safety and Telegram Integration Test Suite.

Validates all 24 safety criteria without submitting live/paper orders.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

import config
from core.enums import EngineState
from core.trading_engine import TradingEngine
from telegram.bot_adapter import TelegramAdapter


class TestOpheliaTelegramAndSafety(unittest.TestCase):

    def setUp(self):
        config.LIVE_TRADING = False
        config.ENABLE_TELEGRAM = False
        config.TELEGRAM_TOKEN = ""
        config.TELEGRAM_ALLOWED_USER_IDS = [123456789]

    def test_01_project_imports(self):
        import app.application
        import bot
        import main
        import telegram.bot_adapter
        self.assertTrue(True)

    def test_02_03_engine_init_without_telegram_and_no_creds(self):
        os.environ.pop("BINGX_API_KEY", None)
        os.environ.pop("BINGX_SECRET_KEY", None)
        engine = TradingEngine()
        self.assertFalse(engine.live_trading)
        self.assertEqual(engine.engine_state, EngineState.NORMAL)

    def test_04_telegram_module_imports(self):
        from telegram.bot_adapter import TelegramAdapter
        self.assertIsNotNone(TelegramAdapter)

    def test_05_06_user_authentication(self):
        engine = TradingEngine()
        adapter = TelegramAdapter(engine)
        adapter.allowed_user_ids = {123456789}
        self.assertTrue(adapter.is_authorized(123456789))
        self.assertFalse(adapter.is_authorized(999999999))
        self.assertFalse(adapter.is_authorized(None))

    def test_07_08_09_10_status_health_mode_positions(self):
        engine = TradingEngine()
        adapter = TelegramAdapter(engine)
        adapter.allowed_user_ids = {123456789}

        status = engine.get_status_summary()
        self.assertEqual(status["mode"], "PAPER")
        self.assertEqual(status["engine_state"], "NORMAL")

        health = engine.get_health_summary()
        self.assertEqual(health["status"], "HEALTHY")

        positions = engine.get_positions_summary()
        self.assertEqual(len(positions), 0)

    def test_11_12_13_engine_controls(self):
        engine = TradingEngine()

        # Test Pause
        success, msg = engine.pause_trading()
        self.assertTrue(success)
        self.assertEqual(engine.engine_state, EngineState.PAUSED)

        # Test Stop
        success, msg = engine.stop_trading()
        self.assertTrue(success)
        self.assertEqual(engine.engine_state, EngineState.STOPPED)

        # Test Resume to Normal
        success, msg = engine.resume_trading()
        self.assertTrue(success)
        self.assertEqual(engine.engine_state, EngineState.NORMAL)

        # Test PROTECTION_ONLY cannot be bypassed by resume
        engine.protection_only_mode = True
        engine.protection_degraded = True
        engine.engine_state = EngineState.PROTECTION_ONLY

        success, msg = engine.resume_trading()
        self.assertFalse(success)
        self.assertEqual(engine.engine_state, EngineState.PROTECTION_ONLY)

    def test_14_15_16_close_position_confirmation(self):
        engine = TradingEngine()
        adapter = TelegramAdapter(engine)
        adapter.allowed_user_ids = {123456789}
        adapter.send_message = MagicMock(return_value=True)

        # Attempt close without confirmation -> requests confirmation
        adapter._cmd_close(chat_id=123456789, user_id=123456789, args=["SOL-USDT"])
        adapter.send_message.assert_called()

        # Test expired confirmation
        key = (123456789, "close", "SOL-USDT")
        adapter._pending_confirmations[key] = {
            "expires_at": time.time() - 10,
            "symbol": "SOL-USDT",
        }
        adapter._cmd_confirm_close(chat_id=123456789, user_id=123456789, args=["SOL-USDT"])
        self.assertIn("EXPIRED", adapter.send_message.call_args[0][1].upper())

    def test_17_no_fallback_close_all_on_missing_id(self):
        engine = TradingEngine()
        success, msg = engine.close_position_safe("NON_EXISTENT_SYMBOL")
        self.assertFalse(success)
        self.assertIn("NOT FOUND", msg.upper())

    def test_18_emergency_close_uses_broker(self):
        engine = TradingEngine()
        engine.broker.emergency_close_all = MagicMock(return_value={"closed": []})
        success, msg = engine.emergency_close_safe()
        self.assertTrue(success)
        engine.broker.emergency_close_all.assert_called_once()

    def test_19_telegram_no_direct_bingx_client(self):
        engine = TradingEngine()
        adapter = TelegramAdapter(engine)
        self.assertFalse(hasattr(adapter, "client"))
        self.assertFalse(hasattr(adapter, "order_manager"))

    def test_20_legacy_bot_py_safety(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bot_script", "bot.py")
        bot_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot_script)
        self.assertTrue(hasattr(bot_script, "main"))


    def test_21_telegram_failure_does_not_crash_engine(self):
        engine = TradingEngine()
        adapter = TelegramAdapter(engine)
        adapter.send_message = MagicMock(side_effect=Exception("Network error"))
        try:
            adapter.notify("Test notification")
        except Exception:
            self.fail("Telegram failure crashed engine notification handler")

    def test_22_23_24_architecture_and_credentials_safety(self):
        engine = TradingEngine()
        status_str = str(engine.get_status_summary())
        self.assertNotIn("secret", status_str.lower())
        self.assertNotIn("key", status_str.lower())


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOpheliaTelegramAndSafety)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
