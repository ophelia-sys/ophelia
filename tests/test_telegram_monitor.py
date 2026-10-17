import unittest
import os
import json
import tempfile
import time
from unittest.mock import patch, MagicMock

# Create a dummy config/env to prevent telegram bot from loading actual token during tests
os.environ["TELEGRAM_BOT_TOKEN"] = "dummy_token"
os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "12345"

from telegram.shadow_monitor import ShadowMonitorBot

class TestShadowMonitorBot(unittest.TestCase):
    def setUp(self):
        # Create a temporary log file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file_path = os.path.join(self.temp_dir.name, "ophelia.log")
        
        self.bot = ShadowMonitorBot()
        self.bot.state_file = os.path.join(self.temp_dir.name, "shadow_state.json")
        self.bot.data_dir = self.temp_dir.name
        self.bot.get_shadow_logs = self.mock_get_shadow_logs
        
        self.dummy_logs = [
            "2026-08-18 05:40:28,377 | INFO | ======================================================================\n",
            "2026-08-18 05:40:28,377 | INFO | Initializing Ophelia Trading Platform\n",
            "2026-08-18 05:40:28,378 | INFO | ======================================================================\n",
            "2026-08-18 05:40:28,951 | INFO | [InstWS] Connected to BingX Market Data WS\n",
            "2026-08-18 05:45:00,000 | INFO | Market Scan Complete\n",
            "2026-08-18 05:45:01,111 | INFO | [PHASE 7] BTC-USDT Buffer Warming: 288/288 blocks (Failed Closed)\n",
            f"2026-08-18 05:46:00,000 | INFO | [SHADOW_JSON] {json.dumps({'timestamp': 1723959960000, 'symbol': 'BTC-USDT', 'probability_long': 0.85, 'probability_short': 0.10, 'frozen_threshold_long': 0.7, 'frozen_threshold_short': 0.7, 'decision': 'LONG_CANDIDATE', 'reason': 'PROB_LONG >= 0.7', 'telemetry': {'delta_deterioration_bullish': 1.0}})}\n",
            f"2026-08-18 05:46:01,000 | INFO | [SHADOW_JSON] {json.dumps({'timestamp': 1723959961000, 'symbol': 'ETH-USDT', 'probability_long': 0.85, 'probability_short': 0.90, 'frozen_threshold_long': 0.7, 'frozen_threshold_short': 0.7, 'decision': 'SHORT_CANDIDATE', 'reason': 'CONFLICT RESOLVED: SHORT_MARGIN >= LONG_MARGIN', 'telemetry': {'divergence_bearish': 1.0}})}\n",
            f"2026-08-18 05:46:02,000 | INFO | [SHADOW_JSON] {json.dumps({'timestamp': 1723959962000, 'symbol': 'SOL-USDT', 'probability_long': 0.1, 'probability_short': 0.1, 'frozen_threshold_long': 0.7, 'frozen_threshold_short': 0.7, 'decision': 'HOLD', 'reason': 'BELOW THRESHOLDS', 'telemetry': {}})}\n",
            "2026-08-18 05:46:03,000 | ERROR | Connection aborted.\n",
            "2026-08-18 05:46:04,000 | WARNING | New signal entries blocked.\n"
        ]

    def mock_get_shadow_logs(self, limit=5000):
        return self.dummy_logs

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_state(self):
        state = self.bot.parse_state()
        
        self.assertIsNone(state["shadow_state"]["shadow_started_at"])
        self.assertEqual(state["websocket_state"], "CONNECTED")
        self.assertEqual(state["buffer_warming_min"], 0)
        self.assertEqual(state["errors"], 1)
        self.assertEqual(state["warnings"], 1)
        self.assertEqual(len(state["symbol_state"]), 3)
        self.assertEqual(state["shadow_state"]["long_candidates"], 0)
        self.assertEqual(state["shadow_state"]["short_candidates"], 0)
        self.assertEqual(state["shadow_state"]["holds"], 0)
        self.assertEqual(state["shadow_state"]["conflicts"], 0)
        self.assertEqual(state["shadow_state"]["telemetry_counts"]["dtr"], 0)
        self.assertEqual(state["shadow_state"]["telemetry_counts"]["div"], 0)
        self.assertEqual(state["shadow_state"]["telemetry_counts"]["flp"], 0)
        self.assertEqual(state["shadow_state"]["telemetry_counts"]["abs"], 0)

    @patch("telegram.shadow_monitor.ShadowMonitorBot.send_message")
    def test_cmd_progress(self, mock_send):
        self.bot.cmd_progress(12345)
        self.assertTrue(mock_send.called)
        
        msg = mock_send.call_args[0][1]
        
        # Verify required strings exist in output
        self.assertIn("CURRENT VPS CVD WARM-UP", msg)
        self.assertIn("ACTUAL 24-HOUR SHADOW", msg)
        self.assertIn("OBSERVATIONS", msg)
        self.assertIn("CONFLICT STATISTICS", msg)
        self.assertIn("DATA INTEGRITY", msg)
        self.assertIn("DTR: 0", msg)
        self.assertIn("DIV: 0", msg)
        self.assertIn("FLP: 0", msg)
        self.assertIn("ABS: 0", msg)

    @patch("telegram.shadow_monitor.ShadowMonitorBot.send_message")
    def test_cmd_health(self, mock_send):
        self.bot.cmd_health(12345)
        self.assertTrue(mock_send.called)
        
        msg = mock_send.call_args[0][1]
        self.assertIn("VPS HEALTH", msg)
        self.assertIn("OPHELIA HEALTH", msg)
        self.assertIn("LIVE EXECUTION: BLOCKED", msg)

    @patch("telegram.shadow_monitor.ShadowMonitorBot.send_message")
    def test_cmd_status(self, mock_send):
        self.bot.cmd_status(12345)
        self.assertTrue(mock_send.called)
        
        msg = mock_send.call_args[0][1]
        self.assertIn("OPHELIA CURRENT STATUS", msg)
        self.assertIn("BTC-USDT", msg)
        self.assertIn("LONG Prob: 0.8500", msg)
        self.assertIn("Decision: LONG_CANDIDATE", msg)
        self.assertIn("LIVE EXECUTION: BLOCKED", msg)
        self.assertIn("Adv. OF Flags: DTR", msg)

    @patch("telegram.shadow_monitor.ShadowMonitorBot.send_message")
    def test_cmd_hi(self, mock_send):
        self.bot.cmd_hi(12345)
        self.assertTrue(mock_send.called)
        
        msg = mock_send.call_args[0][1]
        self.assertIn("/health", msg)
        self.assertIn("/status", msg)
        self.assertIn("/progress", msg)
        
if __name__ == "__main__":
    unittest.main()
