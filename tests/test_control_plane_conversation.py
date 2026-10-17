"""Unit tests for the conversational control-plane layer (nlg + llm validation)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_plane import nlg                                    # noqa: E402
from control_plane.llm import validate_intent                    # noqa: E402
from control_plane.telegram_bot import Bot                       # noqa: E402


class TestValidateIntent(unittest.TestCase):
    def test_symbol_normalization(self):
        intent, err = validate_intent({"intent_type": "MARKET_QUERY",
                                       "symbol": "sol"})
        self.assertEqual(err, "")
        self.assertEqual(intent["symbol"], "SOL-USDT")

    def test_rejects_bad_timeframe(self):
        _, err = validate_intent({"intent_type": "MARKET_QUERY", "timeframe_min": 7})
        self.assertTrue(err)

    def test_rejects_bad_intent(self):
        _, err = validate_intent({"intent_type": "EXECUTE_ORDER"})
        self.assertTrue(err)

    def test_margin_bounds(self):
        _, err = validate_intent({"intent_type": "AUTOMATION_CREATE",
                                  "margin_usage_pct": 150})
        self.assertTrue(err)

    def test_leverage_bounds(self):
        _, err = validate_intent({"intent_type": "AUTOMATION_CREATE",
                                  "leverage": 99})
        self.assertTrue(err)


class TestNlg(unittest.TestCase):
    def test_usd_formatting(self):
        self.assertEqual(nlg._usd(93.25), "$93.25")
        self.assertEqual(nlg._usd(104000.123), "$104,000.12")
        self.assertEqual(nlg._usd(None), "n/a")

    def test_health_summary_natural(self):
        h = {"cpu_pct": 8, "ram_used_pct": 50, "ram_available_gb": 4.1,
             "disk_used_pct": 11,
             "data_health": {"rows": 1440, "data_age_min": 0.3,
                             "last_cleanup_min_ago": 5, "cleanup_ok": True},
             "sessions": {"sessions_active_utc": ["ASIA"],
                          "blackout_new_entries": False}}
        out = nlg.health_summary(h)
        self.assertIn("Ophelia is healthy", out)
        self.assertIn("CPU: 8%", out)
        self.assertIn("1,440", out.replace("\u202f", ","))
        self.assertNotIn("{", out)

    def test_proposal_summary_natural_and_preference_note(self):
        p = {"symbol": "SOL-USDT", "timeframe_min": 5,
             "direction_preference": "BULLISH", "mode": "SHADOW",
             "entry_ref_price": 93.25, "ema_state": "BULLISH", "leverage": 20,
             "risk": {"allocated_margin": 50.0, "notional": 1000.0}}
        out = nlg.proposal_summary(p)
        self.assertIn("EMA 9/20 crossover", out)
        self.assertIn("preference only", out)
        self.assertIn("YES / NO", out)
        self.assertNotIn("{", out)

    def test_missing_params_message(self):
        out = nlg.missing_params_message(["timeframe_min"],
                                         {"symbol": "SOL-USDT",
                                          "margin_usage_pct": 50})
        self.assertIn("timeframe", out.lower())
        self.assertIn("Noted so far", out)

    def test_crossover_estimate_is_labelled_estimate(self):
        ce = {"estimate_bars": 3.5, "state": "BULLISH", "spread_now": 0.02,
              "would_cross_to": "BEARISH"}
        out = nlg.crossover_estimate_summary(ce, 5)
        self.assertIn("ESTIMATE", out)

    def test_news_summary_marks_preference(self):
        ctx = {"daily_bias": "BULLISH", "confidence": 0.4,
               "bias_strength": 0.4, "reason_codes": ["breadth_up=0.67"]}
        out = nlg.news_summary(ctx)
        self.assertIn("preference only", out)

    def test_maybe_raw_only_on_request(self):
        natural = "ok"
        payload = {"a": 1}
        self.assertEqual(nlg.maybe_raw("hello", natural, payload), "ok")
        self.assertIn("(raw)", nlg.maybe_raw("show raw json", natural, payload))


class TestConfirmationVocabulary(unittest.TestCase):
    """try_confirmation must only act on explicit yes/no."""

    def _bot_with_pending(self):
        from control_plane.telegram_bot import Bot
        b = Bot()
        cid = 1
        b.sessions[cid] = {
            "context": {}, "history": [],
            "pending": {"kind": "AUTOMATION_CONFIRM",
                        "spec": {"strategy": "EMA_CROSSOVER",
                                 "symbol": "SOL-USDT", "timeframe_min": 5,
                                 "direction_preference": "ANY",
                                 "margin_usage_pct": 50.0, "leverage": 20.0}}}
        return b, cid

    def test_vague_does_not_confirm(self):
        with patch.object(Bot, "send"), \
             patch("control_plane.core.register_condition") as arm:
            b, cid = self._bot_with_pending()
            for vague in ("looks good", "okay", "fine", "cool"):
                b.sessions[cid]["pending"] = {
                    "kind": "AUTOMATION_CONFIRM",
                    "spec": b.sessions[cid]["pending"]["spec"]}
                handled = b.try_confirmation(cid, vague)
                self.assertFalse(handled, vague)
                arm.assert_not_called()

    def test_explicit_yes_arms(self):
        with patch.object(Bot, "send"), \
             patch("control_plane.core.register_condition",
                   return_value={"automation_id": 7, "proposal": {}}) as arm:
            b, cid = self._bot_with_pending()
            self.assertTrue(b.try_confirmation(cid, "ARM IT"))
            arm.assert_called_once()

    def test_no_cancels(self):
        with patch.object(Bot, "send"):
            b, cid = self._bot_with_pending()
            self.assertTrue(b.try_confirmation(cid, "no"))
            self.assertIsNone(b.sessions[cid]["pending"])


class TestGrounding(unittest.TestCase):
    """Deterministic extraction must override LLM fabrication."""

    def test_numbers_extracted(self):
        g = nlg.extract_params_from_text("use 50% margin at 20x on sol, 5m")
        self.assertEqual(g["margin_usage_pct"], 50.0)
        self.assertEqual(g["leverage"], 20.0)
        self.assertEqual(g["timeframe_min"], 5)
        self.assertEqual(g["symbol"], "SOL-USDT")

    def test_no_invention(self):
        g = nlg.extract_params_from_text("set up ema crossover")
        self.assertNotIn("margin_usage_pct", g)
        self.assertNotIn("leverage", g)
        self.assertEqual(g.get("strategy"), "EMA_CROSSOVER")

    def test_preference_not_restriction(self):
        g = nlg.extract_params_from_text("bullish preferred please")
        self.assertEqual(g["direction_preference"], "BULLISH")


if __name__ == "__main__":
    unittest.main(verbosity=2)
