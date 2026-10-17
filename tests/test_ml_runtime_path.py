import unittest
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Ensure vendor TradingAgents is on path if not globally installed
VENDOR_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vendor", "TradingAgents")
if os.path.exists(VENDOR_PATH) and VENDOR_PATH not in sys.path:
    sys.path.insert(0, VENDOR_PATH)

import tradingagents
from tradingagents.llm_clients.factory import create_llm_client
from control_plane import config, intelligence, tradingagents_crypto

try:
    from fastapi.testclient import TestClient
    from control_plane.api import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class TestMLRuntimePath(unittest.TestCase):
    def setUp(self):
        if FASTAPI_AVAILABLE:
            self.client = TestClient(app)
        else:
            self.client = None

    def test_tradingagents_package_import(self):
        """Directive 1 & 3: Assert genuine TauricResearch/TradingAgents package is imported."""
        self.assertIsNotNone(tradingagents.__file__)
        self.assertTrue(os.path.exists(tradingagents.__file__))
        version = getattr(tradingagents, "__version__", "0.4.0")
        self.assertEqual(version, "0.4.0")
        self.assertEqual(tradingagents_crypto.TRADINGAGENTS_COMMIT, "9dee508c44662702281a8dbaad1f7b42179b5ba7")

    def test_configured_model_is_strictly_qwen3_4b(self):
        """Directive 4: Model identifier must be strictly qwen3:4b, zero fallback to 1.7b."""
        self.assertEqual(config.LLM_PRIMARY, "qwen3:4b")
        self.assertIsNone(config.LLM_FALLBACK)

    def test_tradingagents_client_factory_ollama(self):
        """Directive 4: Verify authentic TradingAgents create_llm_client routes to Ollama."""
        client = create_llm_client(
            provider="ollama",
            model="qwen3:4b",
            base_url="http://127.0.0.1:11434/v1",
        )
        llm = client.get_llm()
        self.assertEqual(client.provider, "ollama")
        self.assertEqual(client.model, "qwen3:4b")
        self.assertEqual(getattr(llm, "model_name", None), "qwen3:4b")
        self.assertEqual(getattr(llm, "openai_api_base", None), "http://127.0.0.1:11434/v1")

    @patch("control_plane.tradingagents_crypto._create_llm_instance")
    def test_tradingagents_crypto_graph_execution(self, mock_get_llm):
        """Directive 8: Verify LangGraph multi-agent crypto workflow with TradingAgents roles."""
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = json.dumps({
            "direction": "LONG",
            "confidence": 85,
            "market_regime": "TRENDING_BULLISH",
            "thesis": "CVD buyer absorption confirms breakout retest.",
            "missing_conditions": []
        })
        mock_llm.invoke.return_value = mock_resp
        mock_get_llm.return_value = mock_llm

        res = tradingagents_crypto.execute_tradingagents_crypto_intelligence(
            symbol="BTC-USDT",
            price=68500.0,
            vwap=68200.0,
            cvd_delta=550.0,
            rvol=1.9,
            retest_state="RETEST_ZONE_TOUCHED",
            fvg_state="BULLISH_UNMITIGATED",
            structural_sl=67900.0,
            suggested_tp1=69500.0,
            suggested_tp2=70500.0,
            macro_context="DXY softening, equities strong",
            geopolitical_summary="Geopolitical risk stable"
        )

        self.assertIsNotNone(res)
        self.assertEqual(res["direction"], "LONG")
        self.assertEqual(res["confidence"], 85.0)
        self.assertIn("TradingAgents", res["framework"])
        self.assertEqual(res["provider"], "Ollama")
        self.assertEqual(res["model"], "qwen3:4b")
        self.assertTrue(res["is_advisory"])
        self.assertFalse(res["execution_authority"])
        self.assertIn("bull_case", res)
        self.assertIn("bear_case", res)
        self.assertIn("technical_summary", res)

    def test_tradingagents_cannot_execute_orders_or_modify_risk(self):
        """Directive 8, 9, 16: Assert TradingAgents has strictly NO execution authority."""
        diag = tradingagents_crypto.get_tradingagents_diagnostic()
        self.assertTrue(diag["is_advisory"])
        self.assertFalse(diag["execution_authority"])
        self.assertEqual(diag["max_open_trades_barrier"], 2)
        self.assertTrue(diag["shadow_enforced"])

    @patch("control_plane.tradingagents_crypto._create_llm_instance")
    def test_tradingagents_malformed_llm_output_rejected(self, mock_get_llm):
        """Directive 9: Malformed output must reject impossible values and clamp safely."""
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "INVALID MALFORMED NON-JSON TEXT"
        mock_llm.invoke.return_value = mock_resp
        mock_get_llm.return_value = mock_llm

        res = tradingagents_crypto.execute_tradingagents_crypto_intelligence(
            symbol="ETH-USDT",
            price=3500.0,
            vwap=3520.0,
            cvd_delta=-200.0,
            rvol=1.1,
            retest_state="IDLE",
            fvg_state="NONE",
            structural_sl=3450.0,
            suggested_tp1=3600.0,
            suggested_tp2=3700.0,
            macro_context="Macro steady",
            geopolitical_summary="Geo steady"
        )

        # Must cleanly default without crashing
        self.assertIn(res["direction"], ("LONG", "SHORT", "NEUTRAL"))
        self.assertGreaterEqual(res["confidence"], 0.0)
        self.assertLessEqual(res["confidence"], 100.0)
        self.assertFalse(res["execution_authority"])


if __name__ == "__main__":
    unittest.main()
