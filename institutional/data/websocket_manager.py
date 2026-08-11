import time
import json
import threading
import websocket
from typing import Dict, List, Callable, Optional
import gzip
import numpy as np

from institutional.types import DataQuality
from institutional.data.models import (
    TradeEvent, OrderBookSnapshot, MarketTicker
)
from utils.logger import logger


class InstitutionalWebSocketManager:
    """
    Read-only WebSocket manager for BingX public data streams.
    Runs in an isolated daemon thread to avoid blocking TradingEngine.
    """

    # Use BingX Perpetual Swap WS endpoint
    WS_URL = "wss://open-api-swap.bingx.com/swap-market"

    def __init__(self):
        self._symbols: List[str] = []
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

        # Callbacks
        self.on_trade_callback: Optional[Callable[[TradeEvent], None]] = None
        self.on_depth_callback: Optional[Callable[[OrderBookSnapshot], None]] = None
        self.on_ticker_callback: Optional[Callable[[MarketTicker], None]] = None

        # Runtime observability counters
        self.stats_trade_events: int = 0
        self.stats_depth_events: int = 0
        self.stats_ticker_events: int = 0
        self.stats_reconnects: int = 0
        self.stats_parse_errors: int = 0
        self.stats_pong_sent: int = 0

    def start(self, symbols: List[str]):
        if self._is_running:
            return

        self._symbols = symbols
        self._is_running = True

        self._thread = threading.Thread(target=self._run_forever, daemon=True, name="InstWSThread")
        self._thread.start()

    def stop(self):
        self._is_running = False
        if self._ws:
            self._ws.close()

    def _run_forever(self):
        while self._is_running:
            try:
                self._ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                self._ws.run_forever()
            except Exception as e:
                logger.error(f"[InstWS] WebSocket error: {e}")

            if self._is_running:
                self.stats_reconnects += 1
                logger.info("[InstWS] Reconnecting in 5 seconds...")
                time.sleep(5)

    def _on_open(self, ws):
        logger.info("[InstWS] Connected to BingX Market Data WS")

        for symbol in self._symbols:
            # 1. Trade
            ws.send(json.dumps({
                "id": f"sub_trade_{symbol}",
                "reqType": "sub",
                "dataType": f"{symbol}@trade"
            }))

            # 2. Depth (level 20)
            ws.send(json.dumps({
                "id": f"sub_depth_{symbol}",
                "reqType": "sub",
                "dataType": f"{symbol}@depth20"
            }))

            # 3. Ticker
            ws.send(json.dumps({
                "id": f"sub_ticker_{symbol}",
                "reqType": "sub",
                "dataType": f"{symbol}@ticker"
            }))

    def _on_message(self, ws, message):
        # FIX 1: Handle plain-text Ping BEFORE attempting gzip decompression
        # BingX sends periodic plain-text "Ping" frames (not gzipped).
        # We must check for plain-text Ping on both str and bytes to avoid
        # misclassifying gzip.BadGzipFile as a parse error.
        try:
            # First, try to decode as plain text (handles both str and plain bytes)
            if isinstance(message, bytes):
                # Try to decode as UTF-8 first to check for plain Ping
                try:
                    text_message = message.decode('utf-8')
                    if text_message == "Ping":
                        ws.send("Pong")
                        self.stats_pong_sent += 1
                        return
                except UnicodeDecodeError:
                    # Not valid UTF-8, must be gzipped binary data
                    pass

                # If we get here, it's gzipped - decompress it
                message = gzip.decompress(message).decode('utf-8')
                
                # FIX 2: Also check for gzipped "Ping" frames (BingX sends gzipped Ping)
                if message == "Ping":
                    ws.send("Pong")
                    self.stats_pong_sent += 1
                    return
            else:
                # Already a string
                if message == "Ping":
                    ws.send("Pong")
                    self.stats_pong_sent += 1
                    return

            # Now message is a decoded string (either was plain JSON or gzipped JSON)
            data = json.loads(message)

            if "dataType" in data:
                dt = data["dataType"]
                if "@trade" in dt:
                    self._parse_trade(data)
                elif "@depth" in dt:
                    self._parse_depth(data)
                elif "@ticker" in dt:
                    self._parse_ticker(data)

        except gzip.BadGzipFile:
            # Genuinely malformed gzip data - count as parse error
            self.stats_parse_errors += 1
            logger.error("[InstWS] Failed to decompress gzip frame (not plain Ping)")
        except json.JSONDecodeError as e:
            # Genuinely malformed JSON - count as parse error
            self.stats_parse_errors += 1
            logger.error(f"[InstWS] JSON decode error: {e}")
        except Exception as e:
            # Any other unexpected error - log and count
            self.stats_parse_errors += 1
            logger.error(f"[InstWS] Unexpected parse error: {e}")

    def _parse_trade(self, payload: dict):
        if not self.on_trade_callback: return

        data_list = payload.get("data", [])
        if isinstance(data_list, dict):
            data_list = [data_list]

        for t in data_list:
            event = TradeEvent(
                symbol=t.get("s", "UNKNOWN"),
                trade_id=str(t.get("t", "")),
                timestamp=int(t.get("T", 0)),
                price=float(t.get("p", 0.0)),
                quantity=float(t.get("q", 0.0)),
                is_buyer_maker=bool(t.get("m", False)),
                source="WS"
            )
            try:
                self.on_trade_callback(event)
                self.stats_trade_events += 1
            except Exception as e:
                logger.error(f"[InstWS] Error in on_trade_callback: {e}")

    def _parse_depth(self, payload: dict):
        if not self.on_depth_callback: return

        d = payload.get("data", {})
        symbol = payload.get("dataType", "").split("@")[0]

        raw_bids = [[float(p), float(q)] for p, q in d.get("bids", [])]
        raw_asks = [[float(p), float(q)] for p, q in d.get("asks", [])]

        # Validation and normalization
        valid_bids = []
        for p, q in raw_bids:
            if not (np.isnan(p) or np.isnan(q) or np.isinf(p) or np.isinf(q) or p <= 0 or q < 0):
                valid_bids.append([p, q])

        valid_asks = []
        for p, q in raw_asks:
            if not (np.isnan(p) or np.isnan(q) or np.isinf(p) or np.isinf(q) or p <= 0 or q < 0):
                valid_asks.append([p, q])

        # Normalize order
        valid_bids.sort(key=lambda x: x[0], reverse=True) # highest to lowest
        valid_asks.sort(key=lambda x: x[0]) # lowest to highest

        # Check crossed book
        dq = DataQuality.VALID
        if not valid_bids or not valid_asks:
            dq = DataQuality.INVALID
        elif valid_bids[0][0] >= valid_asks[0][0]:
            dq = DataQuality.INVALID

        timestamp = int(d.get("T", time.time()*1000))
        # Reject future timestamps (+1 second buffer for clock drift)
        if timestamp > (time.time() + 1.0) * 1000:
            dq = DataQuality.INVALID

        snapshot = OrderBookSnapshot(
            symbol=symbol,
            timestamp=timestamp,
            bids=valid_bids,
            asks=valid_asks,
            source="WS",
            data_quality=dq
        )
        try:
            self.on_depth_callback(snapshot)
            self.stats_depth_events += 1
        except Exception as e:
            logger.error(f"[InstWS] Error in on_depth_callback: {e}")

    def _parse_ticker(self, payload: dict):
        if not self.on_ticker_callback: return

        d = payload.get("data", {})
        symbol = d.get("s", "UNKNOWN")

        ticker = MarketTicker(
            symbol=symbol,
            timestamp=int(d.get("E", time.time()*1000)),
            last_price=float(d.get("c", 0.0)),
            volume_24h=float(d.get("v", 0.0)),
            source="WS"
        )
        try:
            self.on_ticker_callback(ticker)
            self.stats_ticker_events += 1
        except Exception as e:
            # FIX 2: Log the actual ticker callback exception with context
            # Do NOT increment stats_parse_errors - this is a callback error,
            # not a parsing error. The ticker was parsed successfully.
            logger.error(f"[InstWS] Ticker callback error for {symbol}: {type(e).__name__}: {e}")

    def _on_error(self, ws, error):
        logger.error(f"[InstWS] WS Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"[InstWS] WS Closed: code={close_status_code}, reason={close_msg}")