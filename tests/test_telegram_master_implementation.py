"""
Comprehensive verification test suite for Ophelia Telegram and Control-Plane.
Validates all requirements for Chunks 2, 3, 4, 5, 6, 7 and production secret enforcement.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock web framework dependencies if running on environments without fastapi/jwt
for mod in ["fastapi", "fastapi.security", "jwt", "pydantic", "bcrypt"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

# Ensure test environment before imports
os.environ["DATA_DIR"] = os.path.join(os.path.dirname(__file__), "test_data_tg_master")
os.environ["OPH_MAX_OPEN_TRADES"] = "2"

from control_plane import config
from control_plane import db
from control_plane import core
from control_plane import telegram_bot
from control_plane import api


class TestTelegramMasterImplementation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(os.environ["DATA_DIR"], exist_ok=True)
        db._auto_conn()
        db.ensure_seed_watchlist()
        db.set_mode("SHADOW")

    def setUp(self):
        # Clear positions and automations between test cases
        db.ensure_seed_watchlist()
        with db._lock:
            conn = db._auto_conn()
            conn.execute("DELETE FROM positions")
            conn.execute("DELETE FROM shadow_trades")
            conn.execute("DELETE FROM automations")
            conn.commit()
        self.bot = telegram_bot.Bot()
        self.bot._call = MagicMock(return_value={})
        self.chat_id = 999888777
        self.bot.sessions[self.chat_id] = {"context": {}, "pending": None, "history": []}

    # -------------------------------------------------------------
    # CHUNK 2: Command & Callback Routing
    # -------------------------------------------------------------
    def test_hi_command_and_menu_keyboard(self):
        """Test /hi displays master menu with expected buttons."""
        with patch.object(self.bot, "send") as mock_send:
            handled = self.bot._command(self.chat_id, "/hi")
            self.assertTrue(handled)
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertIn("OPHELIA", args[1])
            kb = args[2] if len(args) > 2 else kwargs.get("keyboard")
            self.assertIsNotNone(kb)
            all_callbacks = [btn["callback_data"] for row in kb["inline_keyboard"] for btn in row]
            for expected in ["/trade", "/strategy", "/choose_symbol", "/position", "/setup", "/bingx", "/live", "/status", "/health", "/progress", "/closeall", "/help"]:
                self.assertIn(expected, all_callbacks)

    def test_all_menu_callbacks_route_cleanly(self):
        """Test that all callback actions in _MENU_KB route to deterministic handlers without error."""
        menu_callbacks = [btn["callback_data"] for row in telegram_bot._MENU_KB["inline_keyboard"] for btn in row]
        with patch("control_plane.news.fetch_yahoo_macro_context", return_value={"macro_sentiment": "RISK_ON", "instruments": {}}), \
             patch("control_plane.account.exchange_snapshot", return_value=({}, [])), \
             patch("control_plane.bingx_client.from_env", return_value=MagicMock()):
            for cb_data in menu_callbacks:
                with patch.object(self.bot, "send") as mock_send:
                    cb_payload = {
                        "id": "cb_1",
                        "from": {"id": 1},
                        "message": {"chat": {"id": self.chat_id}},
                        "data": cb_data
                    }
                    self.bot._on_callback(cb_payload)
                    mock_send.assert_called()

    # -------------------------------------------------------------
    # CHUNK 3: Symbol Configuration (Single, Multiple, All)
    # -------------------------------------------------------------
    def test_symbol_single(self):
        """Test setting a single symbol."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/choose_symbol btc")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["symbol"], "BTC-USDT")
            self.assertEqual(d["symbols"], ["BTC-USDT"])
            self.assertEqual(d["symbol_scope"]["mode"], "SINGLE")

    def test_symbol_multiple(self):
        """Test setting multiple symbols."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/choose_symbol btc eth sol")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["symbol"], "MULTIPLE")
            self.assertIn("BTC-USDT", d["symbols"])
            self.assertIn("ETH-USDT", d["symbols"])
            self.assertIn("SOL-USDT", d["symbols"])
            self.assertEqual(d["symbol_scope"]["mode"], "MULTIPLE")

    def test_symbol_all_watchlist(self):
        """Test setting ALL_WATCHLIST."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/choose_symbol all")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["symbol"], "ALL_WATCHLIST")
            self.assertEqual(d["symbol_scope"]["mode"], "ALL_WATCHLIST")
            self.assertGreaterEqual(len(d["symbols"]), 1)

    # -------------------------------------------------------------
    # CHUNK 4: Strategy Configuration & Timeframes
    # -------------------------------------------------------------
    def test_strategy_single_vwap(self):
        """Test setting VWAP_SUPERTREND strategy."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/st_vwap 3m")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["strategy"], "VWAP_SUPERTREND")
            self.assertEqual(d["timeframe_min"], 3)

    def test_strategy_single_ema(self):
        """Test setting EMA_CROSSOVER strategy."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/ema 1m")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["strategy"], "EMA_CROSSOVER")
            self.assertEqual(d["timeframe_min"], 1)

    def test_strategy_both_independent_timeframes(self):
        """Test setting BOTH strategies with independent timeframes."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/strategy both 5m 1m")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["strategy"], "BOTH")
            self.assertEqual(d["strategy_timeframes"]["VWAP_SUPERTREND"], 5)
            self.assertEqual(d["strategy_timeframes"]["EMA_CROSSOVER"], 1)

    def test_timeframe_command(self):
        """Test /timeframe command for single and both."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/strategy both")
            self.bot.handle(self.chat_id, "/timeframe both 3m 1m")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["strategy_timeframes"]["VWAP_SUPERTREND"], 3)
            self.assertEqual(d["strategy_timeframes"]["EMA_CROSSOVER"], 1)

    # -------------------------------------------------------------
    # CHUNK 5: Risk Configuration (Stops, Targets, Margin, Leverage)
    # -------------------------------------------------------------
    def test_stop_loss_commands(self):
        """Test various /sl commands."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/sl manual 1.5")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["stops"], [{"type": "entry_pct", "value": 1.5}])

            self.bot.handle(self.chat_id, "/sl vwap 0.3")
            self.assertEqual(d["stops"], [{"type": "vwap_pct", "value": 0.3}])

            self.bot.handle(self.chat_id, "/sl supertrend 0.4")
            self.assertEqual(d["stops"], [{"type": "supertrend_pct", "value": 0.4}])

    def test_strategy_specific_risk_updates(self):
        """Test setting distinct stops for each strategy under BOTH."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/strategy both")
            self.bot.handle(self.chat_id, "/sl st_vwap supertrend 0.5")
            self.bot.handle(self.chat_id, "/sl ema manual 1.2")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["strategy_risk"]["VWAP_SUPERTREND"]["stops"], [{"type": "supertrend_pct", "value": 0.5}])
            self.assertEqual(d["strategy_risk"]["EMA_CROSSOVER"]["stops"], [{"type": "entry_pct", "value": 1.2}])

    def test_target_and_partial_commands(self):
        """Test /target and /partial configuration."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/target 1:2")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["targets"], [{"pct_qty": 100, "r": 2.0}])

            self.bot.handle(self.chat_id, "/partial 50@0.8 25@1.2 trail 0.8")
            self.assertEqual(len(d["targets"]), 2)
            self.assertEqual(d["trailing_pct"], 0.8)

    def test_margin_and_leverage_commands(self):
        """Test /margin and /leverage commands."""
        with patch.object(self.bot, "send"):
            self.bot.handle(self.chat_id, "/trade")
            self.bot.handle(self.chat_id, "/margin 25usdt")
            d = self.bot.sessions[self.chat_id]["trade"]
            self.assertEqual(d["margin_usdt"], 25.0)

            self.bot.handle(self.chat_id, "/margin 50%")
            self.assertEqual(d["margin_usage_pct"], 50.0)

            self.bot.handle(self.chat_id, "/leverage 20")
            self.assertEqual(d["leverage"], 20.0)

    # -------------------------------------------------------------
    # CHUNK 6: MAX_OPEN_TRADES = 2 Centrally Enforced
    # -------------------------------------------------------------
    def test_max_open_trades_constant_is_two(self):
        """Verify MAX_OPEN_TRADES default is 2."""
        self.assertEqual(config.MAX_OPEN_TRADES, 2)

    def test_one_trade_block_blocks_third_trade(self):
        """Verify one_trade_block allows 0 and 1 position, but blocks on 2 positions."""
        self.assertFalse(core.one_trade_block())
        # Create 1st position -> still allowed
        pid1 = db.create_position({
            "symbol": "BTC-USDT", "direction": "LONG", "entry": 65000.0,
            "qty": 0.01, "leverage": 15.0, "margin_usdt": 45.0, "mode": "SHADOW", "status": "OPEN"
        })
        self.assertFalse(core.one_trade_block(), "Second position must be allowed when limit is 2!")

        # Create 2nd position -> now hard cap of 2 is reached
        pid2 = db.create_position({
            "symbol": "ETH-USDT", "direction": "LONG", "entry": 3500.0,
            "qty": 0.1, "leverage": 15.0, "margin_usdt": 45.0, "mode": "SHADOW", "status": "OPEN"
        })
        block = core.one_trade_block()
        self.assertTrue(block, "Third position must be blocked when 2 positions exist!")
        self.assertEqual(block["open"], 2)
        self.assertEqual(block["limit"], 2)

        # Attempting to confirm shadow trade or execute third entry raises CoreReject
        with db._lock:
            c = db._auto_conn()
            cur = c.execute("INSERT INTO shadow_trades (direction, entry, qty, stop, target, status, detail_json) "
                            "VALUES ('LONG', 150.0, 1.0, 140.0, 170.0, 'PROPOSED', '{\"symbol\": \"SOL-USDT\"}')")
            c.commit()
            tid = cur.lastrowid

        with self.assertRaises(core.CoreReject) as ctx:
            core.confirm_shadow_trade(tid)
        self.assertIn("Max open trades limit reached", str(ctx.exception))


    def test_evaluate_active_automations_evaluates_both_and_blocks_concurrency(self):
        """Verify evaluate_active_automations handles BOTH and stops at limit 1."""
        # Create an automation with BOTH strategies
        aid = db.create_automation({
            "strategy": "BOTH",
            "symbol": "ALL_WATCHLIST",
            "timeframe": 3,
            "direction_pref": "ANY",
            "leverage": 15,
            "margin_usdt": 20,
            "params": {
                "strategy": "BOTH",
                "strategy_timeframes": {"VWAP_SUPERTREND": 3, "EMA_CROSSOVER": 1},
                "strategy_risk": {
                    "VWAP_SUPERTREND": {"stops": [{"type": "supertrend_pct", "value": 0.5}], "targets": [{"r": 2.0, "pct_qty": 100}]},
                    "EMA_CROSSOVER": {"stops": [{"type": "entry_pct", "value": 1.0}], "targets": [{"r": 2.0, "pct_qty": 100}]}
                }
            }
        })

        # Mock market data so that VWAP_SUPERTREND triggers a signal
        mock_st_cross = {"direction": "LONG", "candle_ts": 1700000000000, "close": 65000.0, "st_line": 64500.0}
        mock_regime = {"state": "BULLISH", "eligible": "BOTH"}

        with patch("control_plane.analytics.vwap_regime", return_value=mock_regime), \
             patch("control_plane.analytics.st_vwap_cross_event", side_effect=[
                 {"direction": "LONG", "candle_ts": 1700000000000, "close": 65000.0, "st_line": 64500.0},
                 {"direction": "LONG", "candle_ts": 1700000060000, "close": 65100.0, "st_line": 64600.0},
                 {"direction": "LONG", "candle_ts": 1700000120000, "close": 65200.0, "st_line": 64700.0},
             ]):
            events = core.evaluate_active_automations()
            self.assertEqual(len(events), 1)
            self.assertIn(events[0]["symbol"], db.watchlist_symbols())

            # With 1 trade open, a 2nd trade is allowed under MAX_OPEN_TRADES = 2
            events2 = core.evaluate_active_automations()
            self.assertEqual(len(events2), 1, "Second trade must be allowed when MAX_OPEN_TRADES is 2!")

            # With 2 trades open, the 3rd trade is strictly blocked by one_trade_block
            events3 = core.evaluate_active_automations()
            self.assertEqual(events3, [], "Third trade must be blocked once 2 trades are active!")



    # -------------------------------------------------------------
    # CHUNK 7: Reconciliation & Views
    # -------------------------------------------------------------
    def test_position_view_renders_cleanly(self):
        """Test _position_view returns formatted string without error."""
        with patch("control_plane.account.exchange_snapshot", return_value=({}, [])):
            view = self.bot._position_view()
            self.assertIsInstance(view, str)
            self.assertIn("No active position", view)

            # Add shadow position
            db.create_position({
                "symbol": "BTC-USDT", "direction": "LONG", "entry": 65000.0,
                "qty": 0.01, "leverage": 15.0, "margin_usdt": 45.0, "mode": "SHADOW", "status": "OPEN",
                "stop_current": 64000.0
            })
            view_with_pos = self.bot._position_view()
            self.assertIn("BTC-USDT", view_with_pos)
            self.assertIn("RECONCILIATION_REQUIRED", view_with_pos)

    # -------------------------------------------------------------
    # Production Secret Requirement
    # -------------------------------------------------------------
    def test_production_secret_enforcement(self):
        """Verify production environment raises error if SECRET_KEY is missing."""
        # Test in production mode
        with patch.dict(os.environ, {"OPHELIA_ENV": "production", "SECRET_KEY": "", "JWT_SECRET": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                api._get_jwt_secret()
            self.assertIn("Production secret required", str(ctx.exception))

        # Test in dev mode: returns persistent 256-bit token
        with patch.dict(os.environ, {"OPHELIA_ENV": "development", "SECRET_KEY": "", "JWT_SECRET": ""}):
            sec = api._get_jwt_secret()
            self.assertGreaterEqual(len(sec), 64)
            # Second call retrieves the exact same saved secret
            sec2 = api._get_jwt_secret()
            self.assertEqual(sec, sec2)


if __name__ == "__main__":
    unittest.main()
