"""
Phase 5D.3 — Forensic Probe: Ticker Subscription & Parse Errors
Short controlled capture to inspect raw WS messages.
"""
import sys
import time
import json
import logging
import websocket
import gzip

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SYMBOL = "BTC-USDT"
WS_URL = f"wss://open-api-swap.bingx.com/swap-market"

def on_message(ws, message):
    try:
        if isinstance(message, bytes):
            decompressed = gzip.decompress(message).decode('utf-8')
            print(f"<< RAW (gz): {decompressed[:500]}")
            message = decompressed
        else:
            print(f"<< RAW (txt): {message[:500]}")
    except Exception as e:
        print(f"<< RAW (bytes, err={e}): {message[:100] if isinstance(message, bytes) else message}")

def on_open(ws):
    print(">> CONNECTED")
    # Trade
    ws.send(json.dumps({
        "id": f"sub_trade_{SYMBOL}",
        "reqType": "sub",
        "dataType": f"{SYMBOL}@trade"
    }))
    print(f">> SUB trade: {SYMBOL}@trade")
    # Depth
    ws.send(json.dumps({
        "id": f"sub_depth_{SYMBOL}",
        "reqType": "sub",
        "dataType": f"{SYMBOL}@depth20"
    }))
    print(f">> SUB depth: {SYMBOL}@depth20")
    # Ticker
    ws.send(json.dumps({
        "id": f"sub_ticker_{SYMBOL}",
        "reqType": "sub",
        "dataType": f"{SYMBOL}@ticker"
    }))
    print(f">> SUB ticker: {SYMBOL}@ticker")

def on_error(ws, error):
    print(f"!! ERROR: {error}")

def on_close(ws, code, reason):
    print(f"!! CLOSE: code={code}, reason={reason}")

if __name__ == "__main__":
    print(f"Probing {WS_URL} for {SYMBOL} (30s)...")
    ws = websocket.WebSocketApp(WS_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever(ping_interval=0)  # we handle ping/pong manually
    time.sleep(30)
    ws.close()