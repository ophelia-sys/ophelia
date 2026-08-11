"""
Phase 5D.3 — Job 15/16: Reconnect resilience + Data Quality State Machine tests.

Tests verify:
1. WebSocket reconnect does not duplicate trades (dedup by trade_id)
2. DataQuality transitions are correct across snapshot scenarios
3. Stale book fallback to REST
4. Missing aggressor degrades quality
5. Empty trades produce INSUFFICIENT_DATA
6. Engine handles stop/restart gracefully
"""
import time
import pytest
from institutional.data.engine import InstitutionalDataEngine
from institutional.data.models import (
    TradeEvent, OrderBookSnapshot, OHLCVBar, MarketTicker
)
from institutional.types import DataQuality


def _mock_engine():
    """Create a fully mocked engine with no network calls."""
    engine = InstitutionalDataEngine(use_ws=False)
    engine.rest_adapter.get_klines = lambda s, i, **kwargs: [
        OHLCVBar(s, int(time.time()), 100, 100, 100, 100, 10, "REST")
    ]
    engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(
        s, int(time.time() * 1000), [[100, 1]], [[101, 1]], "REST"
    )
    engine.rest_adapter.get_funding_history = lambda s: []
    engine.rest_adapter.get_open_interest = lambda s: None
    engine.rest_adapter.get_ticker = lambda s: MarketTicker(
        s, int(time.time() * 1000), 100, 100, "REST"
    )
    engine.start(["BTC-USDT"])
    return engine


# ── Job 15: Reconnect / Resilience ────────────────────────────────

class TestReconnectResilience:
    def test_duplicate_trade_rejected_after_reconnect(self):
        """Simulates a WS reconnect replaying the same trade_id."""
        engine = _mock_engine()
        now = int(time.time() * 1000)

        t1 = TradeEvent("BTC-USDT", "reconnect_t1", now, 60000, 1.0, False, "WS")
        engine._on_trade(t1)
        engine._on_trade(t1)  # reconnect replay

        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.buy_volume == 1.0, "Duplicate should be rejected"

    def test_new_trade_after_reconnect(self):
        """After reconnect, genuinely new trades are accepted."""
        engine = _mock_engine()
        now = int(time.time() * 1000)

        engine._on_trade(TradeEvent("BTC-USDT", "t1", now, 60000, 1.0, False, "WS"))
        engine._on_trade(TradeEvent("BTC-USDT", "t1", now, 60000, 1.0, False, "WS"))  # dup
        engine._on_trade(TradeEvent("BTC-USDT", "t2", now, 60000, 2.0, False, "WS"))  # new

        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.buy_volume == 3.0

    def test_stop_and_restart(self):
        """Engine.stop() then start() should not crash."""
        engine = _mock_engine()
        engine.stop()
        engine.start(["BTC-USDT"])
        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap is not None


# ── Job 16: Data Quality State Machine ────────────────────────────

class TestDataQualityStateMachine:
    def test_valid_state_with_trades_and_book(self):
        """Full data → VALID."""
        engine = _mock_engine()
        now = int(time.time() * 1000)
        engine._on_trade(TradeEvent("BTC-USDT", "q1", now, 60000, 1.0, False, "WS"))

        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.data_quality == DataQuality.VALID

    def test_no_trades_produces_insufficient_data(self):
        """No trades in window → INSUFFICIENT_DATA, CVD/TVI are None."""
        engine = _mock_engine()
        snap = engine.get_snapshot("BTC-USDT", "1m")

        assert snap.data_quality == DataQuality.INSUFFICIENT_DATA
        assert snap.cvd is None
        assert snap.tvi is None

    def test_missing_aggressor_degrades_quality(self):
        """Trade with unknown aggressor → DEGRADED."""
        engine = _mock_engine()
        now = int(time.time() * 1000)
        t = TradeEvent("BTC-USDT", "q2", now, 60000, 1.0, None, "WS")
        engine._on_trade(t)

        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.data_quality == DataQuality.DEGRADED

    def test_invalid_book_degrades_quality(self):
        """Crossed book → DEGRADED snapshot."""
        engine = _mock_engine()
        now = int(time.time() * 1000)
        engine._on_trade(TradeEvent("BTC-USDT", "q3", now, 60000, 1.0, False, "WS"))

        # Inject a crossed book
        engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(
            s, int(time.time() * 1000), [[105, 1]], [[100, 1]], "REST",
            data_quality=DataQuality.INVALID
        )
        engine._order_books.pop("BTC-USDT", None)  # force REST fallback

        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.data_quality == DataQuality.DEGRADED

    def test_stale_book_triggers_rest_fallback(self):
        """If WS book is >30s old, engine should fall through to REST."""
        engine = _mock_engine()
        now = int(time.time() * 1000)
        engine._on_trade(TradeEvent("BTC-USDT", "q4", now, 60000, 1.0, False, "WS"))

        # Inject a stale book
        stale_ts = int(time.time() * 1000) - 60000  # 60s old
        engine._order_books["BTC-USDT"] = OrderBookSnapshot(
            "BTC-USDT", stale_ts, [[100, 1]], [[101, 1]], "WS"
        )

        snap = engine.get_snapshot("BTC-USDT", "1m")
        # Should have called REST fallback and gotten a fresh book
        assert snap.order_book is not None
        assert snap.data_quality == DataQuality.VALID

    def test_empty_ohlcv_degrades_quality(self):
        """If klines return empty → DEGRADED."""
        engine = _mock_engine()
        engine.rest_adapter.get_klines = lambda s, i, **kwargs: []
        now = int(time.time() * 1000)
        engine._on_trade(TradeEvent("BTC-USDT", "q5", now, 60000, 1.0, False, "WS"))

        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.data_quality == DataQuality.DEGRADED


# ── Phase 5D.3 Fixes: Heartbeat + Ticker Exception Visibility ────────

import gzip
import json
from institutional.data.websocket_manager import InstitutionalWebSocketManager


class TestHeartbeatHandling:
    """FIX 1: Verify plain-text Ping is handled without incrementing parse_errors."""

    def test_plain_text_ping_increments_pong_not_parse_error(self):
        """Plain 'Ping' string should trigger Pong, increment pong counter, NOT parse_errors."""
        ws_mgr = InstitutionalWebSocketManager()
        ws_mgr.on_trade_callback = lambda e: None
        ws_mgr.on_depth_callback = lambda e: None
        ws_mgr.on_ticker_callback = lambda e: None

        # Mock ws.send
        sent_messages = []
        class MockWS:
            def send(self, msg):
                sent_messages.append(msg)

        mock_ws = MockWS()

        # Send plain-text "Ping" as string
        ws_mgr._on_message(mock_ws, "Ping")

        assert ws_mgr.stats_pong_sent == 1
        assert ws_mgr.stats_parse_errors == 0
        assert sent_messages == ["Pong"]

    def test_plain_bytes_ping_increments_pong_not_parse_error(self):
        """Plain b'Ping' bytes should trigger Pong, increment pong counter, NOT parse_errors."""
        ws_mgr = InstitutionalWebSocketManager()
        ws_mgr.on_trade_callback = lambda e: None
        ws_mgr.on_depth_callback = lambda e: None
        ws_mgr.on_ticker_callback = lambda e: None

        sent_messages = []
        class MockWS:
            def send(self, msg):
                sent_messages.append(msg)

        mock_ws = MockWS()

        # Send plain bytes "Ping"
        ws_mgr._on_message(mock_ws, b"Ping")

        assert ws_mgr.stats_pong_sent == 1
        assert ws_mgr.stats_parse_errors == 0
        assert sent_messages == ["Pong"]

    def test_gzipped_json_trade_parses_correctly(self):
        """Gzipped trade JSON should parse and invoke callback, NOT increment parse_errors."""
        ws_mgr = InstitutionalWebSocketManager()
        received_trades = []
        ws_mgr.on_trade_callback = lambda e: received_trades.append(e)
        ws_mgr.on_depth_callback = lambda e: None
        ws_mgr.on_ticker_callback = lambda e: None

        class MockWS:
            def send(self, msg):
                pass

        mock_ws = MockWS()

        # Create a gzipped trade message (like BingX sends)
        trade_payload = {
            "code": 0,
            "dataType": "BTC-USDT@trade",
            "data": [{"s": "BTC-USDT", "t": "12345", "T": 1700000000000, "p": "60000", "q": "0.01", "m": True}]
        }
        gzipped = gzip.compress(json.dumps(trade_payload).encode('utf-8'))

        ws_mgr._on_message(mock_ws, gzipped)

        assert ws_mgr.stats_parse_errors == 0
        assert ws_mgr.stats_trade_events == 1
        assert len(received_trades) == 1
        assert received_trades[0].symbol == "BTC-USDT"

    def test_malformed_gzip_increments_parse_error(self):
        """Genuinely malformed gzip (not plain Ping) should increment parse_errors."""
        ws_mgr = InstitutionalWebSocketManager()
        ws_mgr.on_trade_callback = lambda e: None
        ws_mgr.on_depth_callback = lambda e: None
        ws_mgr.on_ticker_callback = lambda e: None

        class MockWS:
            def send(self, msg):
                pass

        mock_ws = MockWS()

        # Send invalid gzip data (not valid UTF-8, not valid gzip)
        ws_mgr._on_message(mock_ws, b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xffinvalid")

        assert ws_mgr.stats_parse_errors == 1

    def test_malformed_json_increments_parse_error(self):
        """Genuinely malformed JSON should increment parse_errors."""
        ws_mgr = InstitutionalWebSocketManager()
        ws_mgr.on_trade_callback = lambda e: None
        ws_mgr.on_depth_callback = lambda e: None
        ws_mgr.on_ticker_callback = lambda e: None

        class MockWS:
            def send(self, msg):
                pass

        mock_ws = MockWS()

        # Send invalid JSON
        ws_mgr._on_message(mock_ws, b"{not valid json}")

        assert ws_mgr.stats_parse_errors == 1


class TestTickerExceptionVisibility:
    """FIX 2: Ticker callback exceptions should be logged, not counted as parse errors."""

    def test_ticker_callback_exception_logged_not_parse_error(self, caplog):
        """Exception in ticker callback should be logged with context, not increment parse_errors."""
        ws_mgr = InstitutionalWebSocketManager()
        
        def failing_ticker_callback(ticker):
            raise ValueError("Simulated ticker callback failure")
        
        ws_mgr.on_ticker_callback = failing_ticker_callback
        ws_mgr.on_trade_callback = lambda e: None
        ws_mgr.on_depth_callback = lambda e: None

        class MockWS:
            def send(self, msg):
                pass

        mock_ws = MockWS()

        # Create a gzipped ticker message
        ticker_payload = {
            "code": 0,
            "dataType": "BTC-USDT@ticker",
            "data": {
                "e": "24hTicker", "E": 1700000000000, "s": "BTC-USDT",
                "c": "60000", "v": "1000", "o": "59000", "h": "61000", "l": "58000"
            }
        }
        gzipped = gzip.compress(json.dumps(ticker_payload).encode('utf-8'))

        # The exception should be caught and logged, NOT propagate (no re-raise)
        ws_mgr._on_message(mock_ws, gzipped)

        # Parse errors should NOT increment (callback error != parse error)
        assert ws_mgr.stats_parse_errors == 0
        # Ticker events should NOT increment (callback failed)
        assert ws_mgr.stats_ticker_events == 0
        
        # Verify error was logged with context
        assert any("Ticker callback error for BTC-USDT" in record.message for record in caplog.records)
        assert any("ValueError" in record.message for record in caplog.records)
        assert any("Simulated ticker callback failure" in record.message for record in caplog.records)
        
        # Verify NO "Unexpected parse error" log for callback errors
        assert not any("Unexpected parse error" in record.message for record in caplog.records)
