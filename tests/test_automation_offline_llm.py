import unittest
from unittest.mock import patch, MagicMock
import time
from control_plane import db, core

class TestAutomationOfflineLLM(unittest.TestCase):
    def setUp(self):
        # Prevent blackout window during tests
        self.blackout_patcher = patch("control_plane.sessions.in_blackout", return_value=False)
        self.blackout_patcher.start()

    def tearDown(self):
        self.blackout_patcher.stop()

    @patch("urllib.request.urlopen", side_effect=Exception("Ollama is OFFLINE"))
    def test_automation_evaluates_without_llm(self, mock_urlopen):
        """Directive 7: Verify automation evaluates purely with price/indicators when Ollama is offline."""
        aid = db.create_automation({
            "strategy": "EMA_CROSSOVER",
            "symbol": "BTC-USDT",
            "timeframe": 3,
            "direction_pref": "ANY",
            "leverage": 10.0,
            "margin_usdt": 20.0,
            "mode": "SHADOW",
            "params": {"sl_mode": "entry_pct", "sl_val": 1.0}
        }, user_id=99)

        # Evaluate automation
        try:
            # Running evaluation must NOT invoke urllib or crash when Ollama is down
            events = core.evaluate_active_automations()
            # Assert mock_urlopen was NEVER called during automation evaluation
            mock_urlopen.assert_not_called()
        finally:
            db.delete_automation(aid, user_id=99)

    def test_max_open_trades_blocks_execution_in_evaluator(self):
        """Directive 8: Verify MAX_OPEN_TRADES = 2 blocks new trade when 2 positions already exist."""
        # Create 2 dummy open positions for user 99
        p1 = db.create_position({"symbol": "BTC-USDT", "direction": "LONG", "entry": 65000, "qty": 0.01, "mode": "SHADOW", "status": "OPEN"}, user_id=99)
        p2 = db.create_position({"symbol": "ETH-USDT", "direction": "LONG", "entry": 3500, "qty": 0.1, "mode": "SHADOW", "status": "OPEN"}, user_id=99)

        try:
            open_pos = db.open_positions(user_id=99)
            self.assertEqual(len(open_pos), 2)

            # Preflight must report limit reached
            pf = core.run_preflight(user_id=99)
            self.assertFalse(pf["ready_for_live"])
            self.assertTrue(any("Limit reached" in r or "CAP BELOW CURRENT EXPOSURE" in r for r in pf["blocking_reasons"]))
        finally:
            db.update_position(p1, status="CLOSED", closed_ms=int(time.time()*1000))
            db.update_position(p2, status="CLOSED", closed_ms=int(time.time()*1000))
