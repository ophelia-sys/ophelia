"""Operator command-layer tests: deterministic slash commands, position
accounting, reconciliation, precision, break-even, LLM-independence."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="ophelia-cmd-test-")
os.environ["OPH_DATA_DIR"] = _TMP
os.environ["OPH_STATE_DIR"] = _TMP

from control_plane import account, core, db                     # noqa: E402
from control_plane.core import CoreReject                        # noqa: E402
from control_plane.telegram_bot import Bot                       # noqa: E402


def _canned_exchange():
    acc = {"asset": "USDT", "balance": 25.22, "available_margin": 11.93,
           "used_margin": 13.29, "equity": 27.51, "unrealized_pnl": 2.29}
    pos = [{"symbol": "XRPUSDT", "side": "SHORT", "qty": 151.0, "entry": 3.10,
            "mark": 3.05, "leverage": 10, "unrealized_pnl": 7.55,
            "unrealized_pnl_pct": 1.616, "move_from_entry_pct": -1.613,
            "notional": 460.55, "liquidation_price": 3.65, "position_id": 1}]
    return acc, pos


class BotCase(unittest.TestCase):
    def setUp(self):
        self.patcher = patch("control_plane.sessions.in_blackout", return_value=False)
        self.patcher.start()
        self.bot = Bot()
        self.bot.sent = []
        Bot.send = lambda self, cid, text, keyboard=None: \
            self.sent.append(str(text))
        self.cid = 777001

    def tearDown(self):
        self.patcher.stop()

    def send(self, text):
        self.bot.handle(self.cid, text)

    @property
    def last(self):
        sent = getattr(self.bot, "sent", [])
        return sent[-1] if sent else ""


class TestCommandRouting(BotCase):
    def test_1_hi_master_menu(self):
        self.send("/hi")
        self.assertIn("OPHELIA", self.last)
        self.assertIn("Mode:", self.last)
        self.assertIn("Choose a command:", self.last)

    def test_2_status_deterministic_llm_down(self):
        with patch("control_plane.llm.parse_intent",
                   side_effect=RuntimeError("LLM DOWN")):
            self.send("/status")
        self.assertIn("Mode:", self.last)

    def test_21_position_works_without_llm(self):
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange), \
                patch("control_plane.llm.parse_intent",
                      side_effect=RuntimeError("LLM DOWN")):
            self.send("/position")
        self.assertIn("XRPUSDT", self.last)
        self.assertIn("SHORT", self.last)

    def test_22_hi_works_without_llm(self):
        with patch("control_plane.llm.parse_intent",
                   side_effect=RuntimeError("LLM DOWN")):
            self.send("/hi")
        self.assertIn("OPHELIA", self.last)

    def test_23_bingx_works_without_llm(self):
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange), \
                patch("control_plane.llm.parse_intent",
                      side_effect=RuntimeError("LLM DOWN")):
            self.send("/bingx")
        self.assertIn("BINGX ACCOUNT", self.last)


class TestPositionAccounting(BotCase):
    def setUp(self):
        super().setUp()
        c = db._wl_conn()
        with db._lock:
            c.execute("UPDATE positions SET status='CLOSED' WHERE status IN ('OPEN','PARTIAL','TRAILING')")
            c.commit()

    def test_3_position_shows_real_exchange_position(self):
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange), \
                patch("control_plane.account.reconcile",
                      return_value={"ok": True, "issues": [],
                                    "reconciliation_required": False}):
            self.send("/position")
        self.assertIn("XRPUSDT SHORT", self.last)
        self.assertIn("151", self.last)
        self.assertIn("3.10", self.last)          # entry
        self.assertIn("liquidation", self.last.lower())

    def test_20_position_agrees_with_bingx(self):
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange), \
                patch("control_plane.account.reconcile",
                      return_value={"ok": True, "issues": [],
                                    "reconciliation_required": False}):
            self.send("/bingx")
            bingx_txt = self.last
            self.send("/position")
            pos_txt = self.last
        self.assertIn("XRPUSDT", bingx_txt)
        self.assertIn("XRPUSDT", pos_txt)
        self.assertIn("SHORT", pos_txt)

    def test_4_bingx_has_no_exchange_realized_pnl(self):
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange):
            self.send("/bingx")
        self.assertNotIn("exchange, total", self.last)
        self.assertNotIn("Realized PnL (exchange", self.last)
        self.assertIn("unrealized PnL (exchange)", self.last)  # still shown

    def test_5_bingx_ophelia_tracked_pnl_only(self):
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange):
            self.send("/bingx")
        self.assertIn("OPHELIA DAILY PNL", self.last)
        self.assertIn("Ophelia-tracked only", self.last)

    def test_25_ophelia_realized_pnl_persists_through_day(self):
        """Closed Ophelia trade earlier today counts even with nothing open."""
        pid = db.create_position({"symbol": "SOL-USDT", "direction": "LONG",
                                  "entry": 100.0, "qty": 1.0, "leverage": 5,
                                  "status": "OPEN", "mode": "SHADOW"})
        import time as _t
        db.update_position(pid, status="CLOSED", closed_ms=int(_t.time() * 1000),
                           exit_price=101.0, realized_pnl=1.0)
        pnl = account.ophelia_daily_pnl()
        self.assertGreaterEqual(pnl["realized"], 1.0)
        self.assertEqual(pnl["open_ophelia_positions"], 0)

    def test_24_daily_pnl_day_is_explicit_utc(self):
        pnl = account.ophelia_daily_pnl()
        self.assertRegex(pnl["day_utc"], r"\d{4}-\d{2}-\d{2}")
        self.assertIn("00:00 UTC", pnl["resets"])


class TestReconciliation(unittest.TestCase):
    def test_17_qty_mismatch_flagged(self):
        db.create_position({"symbol": "XRP-USDT", "direction": "SHORT",
                            "entry": 3.10, "qty": 100.0, "leverage": 10,
                            "status": "OPEN", "mode": "LIVE"})
        with patch("control_plane.account.exchange_snapshot",
                   side_effect=_canned_exchange):
            rec = account.reconcile()
        self.assertTrue(rec["reconciliation_required"])
        kinds = {i["kind"] for i in rec["issues"]}
        self.assertIn("QTY_MISMATCH", kinds)   # local 100 vs exchange 151


class TestWizards(BotCase):
    def test_6_trade_menu(self):
        self.send("/trade")
        self.assertIn("SUPERTREND + VWAP", self.last)
        self.assertIn("EMA 9/20", self.last)

    def test_7_stvwap_wizard_defaults_3m(self):
        self.send("/st_vwap")
        self.assertIn("SUPERTREND + VWAP wizard", self.last)
        self.assertIn("Timeframe: 3m", self.last)
        self.assertIn("SETUP INCOMPLETE", self.last)

    def test_8_ema_wizard(self):
        self.send("/ema 15m bearish")
        self.assertIn("EMA 9/20 wizard", self.last)
        self.assertIn("Timeframe: 15m", self.last)
        self.assertIn("Direction: BEARISH", self.last)

    def test_9_sl_manual(self):
        self.send("/st_vwap sol 3m long")
        self.send("/sl manual 0.8")
        self.assertIn("0.8% entry_pct", self.last)

    def test_sl_multi(self):
        self.send("/st_vwap sol 3m long")
        self.send("/sl multi 0.8 vwap0.5 st0.2")
        self.assertIn("0.8% entry_pct", self.last)
        self.assertIn("0.5% vwap_pct", self.last)
        self.assertIn("0.2% supertrend_pct", self.last)

    def test_10_target(self):
        import math
        import time as _t
        now = int(_t.time() * 1000)
        rows = [{"ts": now - (600 - i) * 60_000,
                 "open": 100 + 0.3 * math.sin(i / 20),
                 "high": 100.4 + 0.3 * math.sin(i / 20),
                 "low": 99.6 + 0.3 * math.sin(i / 20),
                 "close": 100 + 0.3 * math.sin(i / 20),
                 "volume": 10.0, "taker_buy": 5.0, "trades": 10}
                for i in range(600)]
        db.upsert_candles("BINANCE", "SOL-USDT", rows)
        self.send("/st_vwap sol 3m long")
        self.send("/target 1:2")
        self.assertIn("TP1: 100% @ 2R", self.last)
        # complete the draft, arm, and verify R resolved to a live % target
        self.send("/sl multi 0.8 vwap0.5 st0.2")
        self.send("/partial 50@0.8 25@1.2 trail 0.8")
        self.send("/margin 50%")
        self.send("/leverage 20")
        self.send("/arm")
        self.assertIn("proposing", self.last)
        self.send("/setup")
        self.assertIn("WAITING_CONFIRMATION", self.last)
        self.assertRegex(self.last, r"Targets:.*\+[\d.]+%")

    def test_11_partial(self):
        self.send("/st_vwap sol 3m long")
        self.send("/partial 50@0.8 25@1.2 trail 0.8")
        self.assertIn("TP1: 50% @ +0.8%", self.last)
        self.assertIn("TP2: 25% @ +1.2%", self.last)
        self.assertIn("Trailing: 0.8% buffer", self.last)

    def test_partial_bad_sum_rejected(self):
        self.send("/st_vwap sol")
        self.send("/partial 50@0.8")
        self.assertIn("must be exactly 100", self.last)

    def test_12_margin_pct_and_usdt(self):
        self.send("/st_vwap sol")
        self.send("/margin 50%")
        self.assertIn("Margin: 50%", self.last)
        self.send("/margin 10usdt")
        self.assertIn("Margin: 10 USDT fixed", self.last)

    def test_13_leverage(self):
        self.send("/st_vwap sol")
        self.send("/leverage 20")
        self.assertIn("Leverage: 20x", self.last)
        self.send("/leverage 200")
        self.assertIn("out of allowed range", self.last)

    def test_14_setup_incomplete_lists_missing(self):
        self.send("/st_vwap")
        self.send("/setup")
        self.assertIn("SETUP INCOMPLETE", self.last)
        self.assertIn("margin", self.last)
        self.assertIn("stop", self.last)

    def test_setup_complete_draft(self):
        self.send("/st_vwap sol 3m long")
        self.send("/sl multi 0.8 vwap0.5 st0.2")
        self.send("/partial 50@0.8 25@1.2 trail 0.8")
        self.send("/margin 50%")
        self.send("/leverage 20")
        self.send("/setup")
        self.assertIn("Complete", self.last)
        self.assertNotIn("SETUP INCOMPLETE", self.last)

    def test_15_edit_menu(self):
        self.send("/st_vwap sol")
        self.send("/edit")
        self.assertIn("Current draft:", self.last)

    def test_arm_incomplete_blocked(self):
        self.send("/st_vwap")
        self.send("/arm")
        self.assertIn("SETUP INCOMPLETE", self.last)

    def test_19_closeall_double_confirm(self):
        db.record_shadow_trade({"automation_id": None, "ts_open_ms": 1,
                                "direction": "LONG", "entry": 100.0,
                                "stop": 99.0, "target": 102.0, "qty": 1.0,
                                "status": "OPEN_SHADOW"})
        self.send("/closeall")
        pend = self.bot.sessions[self.cid]["pending"]
        self.assertIsNotNone(pend)
        self.assertEqual(pend["kind"], "CLOSEALL_CONFIRM")
        self.assertIn("WARNING", self.last)


class TestEngineCorrections(unittest.TestCase):
    def _pos(self, **over):
        p = {"id": 1, "symbol": "TEST-USDT", "direction": "LONG", "entry": 100.0,
             "qty": 10.0, "leverage": 20, "margin_usdt": 50.0,
             "stops": [{"type": "entry_pct", "value": 0.8}],
             "targets": [], "trailing_pct": None, "trailing_ref": None,
             "stop_current": None, "status": "OPEN", "mode": "SHADOW",
             "detail": {}}
        p.update(over)
        return p

    def test_16_breakeven_auto_trigger(self):
        p = self._pos(detail={"breakeven": {"trigger_pct": 0.8,
                                            "buffer_pct": 0.0}})
        acts = core.evaluate_position(p, 100.5, None, None)   # +0.5%: not yet
        self.assertFalse(any(a["action"] == "breakeven" for a in acts))
        acts = core.evaluate_position(p, 100.85, None, None)  # +0.85%: fire
        be = [a for a in acts if a["action"] == "breakeven"]
        self.assertTrue(be)
        self.assertAlmostEqual(be[0]["stop"], 100.0, places=6)
        self.assertTrue(p["detail"]["breakeven_done"])
        # stop now armed: a drop back to entry exits
        acts2 = core.evaluate_position(p, 99.99, None, None)
        self.assertTrue(any(a["action"] == "exit_all" for a in acts2))

    def test_18_qty_step_normalization(self):
        spec = {"symbol": "SOLUSDT", "price_precision": 3,
                "quantity_precision": 1, "min_qty": 0.5, "min_notional": 5.0,
                "max_leverage": 150, "contract_size": None}
        with patch("control_plane.core._contract_spec", return_value=spec):
            out = core.normalize_qty("SOL-USDT", 1.23456, 100.0)
            self.assertAlmostEqual(out["qty"], 1.2, places=6)
            with self.assertRaises(CoreReject):
                core.normalize_qty("SOL-USDT", 0.3, 100.0)     # below minQty
            with self.assertRaises(CoreReject):
                core.normalize_qty("SOL-USDT", 0.5, 5.0)       # notional 2.5 < 5


class TestOpenPositionEdit(BotCase):
    def setUp(self):
        super().setUp()
        for p in db.open_positions():          # isolate from earlier tests
            db.update_position(p["id"], status="CLOSED", closed_ms=1)

    def _open_pos(self):
        return db.create_position({"symbol": "SOL-USDT", "direction": "LONG",
                                   "entry": 100.0, "qty": 2.0, "leverage": 10,
                                   "status": "OPEN", "mode": "SHADOW",
                                   "stops": [{"type": "entry_pct",
                                              "value": 0.8}],
                                   "targets": []})

    def test_edit_stop_shows_old_new_and_confirms(self):
        pid = self._open_pos()
        self.send("/edit stop 1.5")
        self.assertIn("EDIT STOP", self.last)
        self.assertIn("Confirm? YES", self.last)
        self.send("yes")
        row = next(r for r in db.open_positions() if r["id"] == pid)
        self.assertAlmostEqual(row["stop_current"], 98.5, places=6)

    def test_edit_stop_wrong_side_rejected(self):
        self._open_pos()
        self.send("/edit stop -1")          # -1% -> level above entry for LONG
        self.assertIn("Rejected", self.last)

    def test_edit_trailing_and_breakeven(self):
        pid = self._open_pos()
        self.send("/edit trailing 0.5")
        self.send("yes")
        row = next(r for r in db.open_positions() if r["id"] == pid)
        self.assertEqual(row["trailing_pct"], 0.5)
        self.send("/edit breakeven 0.8")
        self.send("yes")
        row = next(r for r in db.open_positions() if r["id"] == pid)
        self.assertEqual(row["detail"]["breakeven"]["trigger_pct"], 0.8)

    def test_edit_qty_reduce(self):
        pid = self._open_pos()
        self.send("/edit qty -50%")
        self.send("yes")
        row = next(r for r in db.open_positions() if r["id"] == pid)
        self.assertAlmostEqual(row["qty"], 1.0, places=6)

    def test_edit_requires_confirmation(self):
        pid = self._open_pos()
        self.send("/edit stop 1.5")
        row = next(r for r in db.open_positions() if r["id"] == pid)
        self.assertIsNone(row["stop_current"])      # not applied yet
        self.send("no")
        row = next(r for r in db.open_positions() if r["id"] == pid)
        self.assertIsNone(row["stop_current"])      # still not applied


if __name__ == "__main__":
    unittest.main()
