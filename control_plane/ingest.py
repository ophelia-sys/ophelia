"""Ingest: poll Binance 1m klines (primary, has taker data) into the rolling DB.

Watchlist-driven: every active symbol is polled each cycle; a newly added
symbol is backfilled with the full 24h retention window immediately; a removed
symbol has its retained data deleted by db.watchlist_remove().
"""
from __future__ import annotations

import json
import time
import urllib.request

from . import config, db


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ophelia-cp/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _parse_klines(kl) -> list[dict]:
    rows = []
    for k in kl:
        vol = float(k[5])
        tb = float(k[9]) if len(k) > 9 else 0.0
        rows.append({"ts": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                     "low": float(k[3]), "close": float(k[4]),
                     "volume": vol,
                     "taker_buy": min(tb, vol),
                     "trades": int(k[8]) if len(k) > 8 else 0})
    return rows


def _parse_bingx_klines(kl) -> list[dict]:
    rows = []
    for k in kl:
        vol = float(k.get("volume") or 0.0)
        rows.append({"ts": int(k["time"]),
                     "open": float(k["open"]),
                     "high": float(k["high"]),
                     "low": float(k["low"]),
                     "close": float(k["close"]),
                     "volume": vol,
                     "taker_buy": vol * 0.5,
                     "trades": 0})
    return rows


def poll_bingx_gold_1m() -> int:
    """Fetch recent 1m klines from BingX Perpetual Swap for Gold."""
    contract = config.resolve_gold_contract()
    venue_sym = contract["venue_symbol"]
    url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={venue_sym}&interval=1m&limit=15"
    data = _get(url)
    kl = data.get("data", [])
    rows = _parse_bingx_klines(kl)
    return db.upsert_candles("BINGX", config.GOLD_DISPLAY_NAME, rows)


def poll_binance_1m(symbol_pair: str | None = None) -> int:
    """Fetch recent 1m klines (last ~10 min window) and upsert. Returns row count."""
    pair = symbol_pair or next(
        (s.replace("-USDT", "USDT") for s in db.watchlist_symbols(user_id=None)
         if s.endswith("-USDT")), "SOLUSDT")
    end = int(time.time() * 1000)
    start = end - 11 * 60_000
    kl = _get(f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}"
              f"&interval=1m&startTime={start}&endTime={end}&limit=15")
    rows = _parse_klines(kl)
    sym = f"{pair[:-4]}-USDT"
    return db.upsert_candles("BINANCE", sym, rows)


def backfill_symbol(symbol: str, hours: int | None = None) -> int:
    """Backfill the retention window (default 24h) for one symbol."""
    hours = hours or config.RETENTION_HOURS
    if symbol in (config.GOLD_DISPLAY_NAME, "GOLD", "XAU"):
        contract = config.resolve_gold_contract()
        venue_sym = contract["venue_symbol"]
        url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={venue_sym}&interval=1m&limit=1440"
        data = _get(url)
        kl = data.get("data", [])
        rows = _parse_bingx_klines(kl)
        n = db.upsert_candles("BINGX", config.GOLD_DISPLAY_NAME, rows)
        print(f"[ingest] {config.GOLD_DISPLAY_NAME} backfilled {n} rows from BingX ({hours}h)", flush=True)
        return n

    pair = symbol.replace("-", "")
    end = int(time.time() * 1000)
    start = end - hours * 3600_000
    total = 0
    cursor = start
    while cursor < end:
        kl = _get(f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}"
                  f"&interval=1m&startTime={cursor}&endTime={end}&limit=1500")
        rows = _parse_klines(kl)
        if not rows:
            break
        total += db.upsert_candles("BINANCE", symbol, rows)
        cursor = rows[-1]["ts"] + 60_000
        if len(rows) < 1500:
            break
    print(f"[ingest] {symbol} backfilled {total} rows "
          f"({hours}h)", flush=True)
    return total


def poll_loop(stop_event):
    """Continuous ingest thread: every 20s, all watchlist symbols + cleanup."""
    last_cleanup = 0.0
    while not stop_event.is_set():
        try:
            for s in db.watchlist_symbols(user_id=None) or config.SYMBOLS:
                try:
                    if s in (config.GOLD_DISPLAY_NAME, "GOLD", "XAU") or "GOLD" in s or "XAU" in s:
                        n = poll_bingx_gold_1m()
                    else:
                        pair = s.replace("-", "")
                        n = poll_binance_1m(pair)
                    if n:
                        print(f"[ingest] {s} upserted {n}", flush=True)
                except Exception as e:                            # noqa: BLE001
                    print(f"[ingest] {s} error: {str(e)[:120]}", flush=True)
            if time.time() - last_cleanup >= config.CLEANUP_INTERVAL_MIN * 60:
                stats = db.cleanup_expired()
                print(f"[cleanup] {stats}", flush=True)
                last_cleanup = time.time()
        except Exception as e:                                    # noqa: BLE001
            print(f"[ingest] loop error {str(e)[:160]}", flush=True)
        stop_event.wait(20)

