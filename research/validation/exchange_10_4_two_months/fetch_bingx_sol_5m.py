"""Fetch BingX SOL-USDT perpetual 5m klines - Phase 2.9B primary source.

Endpoint : GET https://open-api.bingx.com/openApi/swap/v3/quote/klines
Semantics (empirically verified 2026-08-22):
    - response is DESCENDING (newest first)
    - window is anchored at endTime: (endTime - limit*tf, endTime]
    - hard row cap per request: 1000
    - history depth cap ~45 days (binary-searched, cached in raw/bingx_horizon.txt)
Pagination: forward, endTime-anchored windows of 1000 bars.
Output   : raw JSON pages preserved + canonical CSV (ascending) + manifest JSON.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

BASE = "https://open-api.bingx.com/openApi/swap/v3/quote/klines"
SYMBOL = "SOL-USDT"
INTERVAL = "5m"
TF_MS = 300_000
PAGE_BARS = 1000
START_MS = 1_780_272_000_000          # 2026-06-01 00:00:00 UTC (requested window start)
END_MS_EXCL = 1_785_542_400_000       # 2026-08-01 00:00:00 UTC (exclusive)
HERE = os.path.dirname(os.path.abspath(__file__))
HORIZON_MS: int | None = None


def http_get(url: str, tries: int = 8):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-p29b/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status, json.loads(r.read().decode())
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(min(2.5 * (i + 1), 20.0))
    raise RuntimeError(f"BingX fetch failed after {tries} tries: {last}")


def find_oldest_available() -> int:
    """Binary-search oldest available candle; cached in raw/bingx_horizon.txt."""
    global HORIZON_MS
    cache = os.path.join(HERE, "raw", "bingx_horizon.txt")
    if os.path.exists(cache):
        cached = int(open(cache).read().strip())
        if abs(cached - END_MS_EXCL) < 45 * 86_400_000:
            HORIZON_MS = cached
            return cached
    lo, hi = START_MS - 30 * 86_400_000, END_MS_EXCL      # lo empty, hi has data
    _, body = http_get(f"{BASE}?symbol={SYMBOL}&interval={INTERVAL}&startTime={hi}&limit=1")
    if not body.get("data"):
        raise RuntimeError("BingX has no data inside the requested window at all")
    while hi - lo > TF_MS:
        mid = (lo + hi) // 2
        _, body = http_get(f"{BASE}?symbol={SYMBOL}&interval={INTERVAL}&startTime={mid}&limit=1")
        if body.get("data"):
            hi = mid
        else:
            lo = mid
        time.sleep(1.5)
    HORIZON_MS = hi
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w") as f:
        f.write(str(hi))
    return hi


def fetch_page(cursor_ms: int, win_end_ms: int):
    """One endTime-anchored page; returns ascending list of candle dicts."""
    url = (f"{BASE}?symbol={SYMBOL}&interval={INTERVAL}"
           f"&startTime={cursor_ms}&endTime={win_end_ms}&limit={PAGE_BARS}")
    status, body = http_get(url)
    attempt = 0
    while body.get("code") == 100410 and attempt < 8:      # throttled: back off
        attempt += 1
        wait = min(10.0 * attempt, 60.0)
        print(f"  BingX throttle (100410), waiting {wait:.0f}s ...", flush=True)
        time.sleep(wait)
        status, body = http_get(url)
    if body.get("code") not in (0, "0"):
        raise RuntimeError(f"BingX API code={body.get('code')} msg={body.get('msg')}")
    data = body.get("data") or []
    data = list(reversed(data))                            # -> ascending
    return status, url, data


def fetch_all() -> tuple:
    rows, pages = [], []
    horizon = find_oldest_available()
    print("BingX API history horizon (oldest candle):",
          datetime.fromtimestamp(horizon / 1000, timezone.utc).isoformat(), flush=True)
    time.sleep(3.0)
    cursor = (horizon // TF_MS) * TF_MS
    page_no = 0
    while cursor < END_MS_EXCL:
        page_no += 1
        win_end = min(cursor + PAGE_BARS * TF_MS, END_MS_EXCL) - 1
        status, url, data = fetch_page(cursor, win_end)
        print(f"  page {page_no}: rows={len(data)}", flush=True)
        pages.append({"page": page_no, "url": url, "status": status,
                      "rows_returned": len(data),
                      "retrieved_utc": datetime.now(timezone.utc).isoformat()})
        for k in data:
            rows.append({
                "candle_open_time": int(k["time"]),
                "open": float(k["open"]), "high": float(k["high"]),
                "low": float(k["low"]), "close": float(k["close"]),
                "volume": float(k.get("volume", 0.0)),
            })
        if not data:
            break
        cursor = win_end + 1
        time.sleep(1.2)
    df = pd.DataFrame(rows)
    df["candle_close_time"] = df["candle_open_time"] + TF_MS
    return df, pages


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    os.makedirs(os.path.join(HERE, "raw"), exist_ok=True)
    df, pages = fetch_all()
    n_raw = len(df)
    df = df.drop_duplicates(subset="candle_open_time").sort_values("candle_open_time")
    df = df.reset_index(drop=True)

    csv_path = os.path.join(HERE, "bingx_sol_5m_2026_07.csv")
    df.to_csv(csv_path, index=False, float_format="%.10f", lineterminator="\n")

    raw_pages_path = os.path.join(HERE, "raw", "bingx_raw_pages.json")
    with open(raw_pages_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)

    manifest = {
        "exchange": "BINGX",
        "endpoint": BASE,
        "symbol_api": SYMBOL,
        "contract_type": "USD-M perpetual swap",
        "interval": INTERVAL,
        "timezone": "UTC (epoch ms)",
        "requested_window_start_utc": datetime.fromtimestamp(
            START_MS / 1000, timezone.utc).isoformat(),
        "api_history_horizon_utc": (datetime.fromtimestamp(
            HORIZON_MS / 1000, timezone.utc).isoformat() if HORIZON_MS
            else "see raw/bingx_horizon.txt"),
        "actual_first_candle_utc": datetime.fromtimestamp(
            int(df["candle_open_time"].iloc[0]) / 1000, timezone.utc).isoformat(),
        "end_utc_exclusive": datetime.fromtimestamp(
            END_MS_EXCL / 1000, timezone.utc).isoformat(),
        "window_note": ("BingX v3 klines serve only ~45 days of history; June 2026 is "
                        "unavailable from the official endpoint. Sample = maximal "
                        "contiguous BingX-native window ending 2026-07-31 23:55 UTC."),
        "candle_count_raw": int(n_raw),
        "candle_count_deduped": int(len(df)),
        "duplicate_rows_removed": int(n_raw - len(df)),
        "pages_fetched": len(pages),
        "retrieval_completed_utc": datetime.now(timezone.utc).isoformat(),
        "csv_filename": csv_path,
        "csv_sha256": sha256_file(csv_path),
        "raw_pages_filename": raw_pages_path,
    }
    with open(os.path.join(HERE, "BINGX_RAW_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("BINGX candles:", len(df),
          "| span:", datetime.fromtimestamp(int(df["candle_open_time"].iloc[0]) / 1000, timezone.utc),
          "->", datetime.fromtimestamp(int(df["candle_open_time"].iloc[-1]) / 1000, timezone.utc))
    print("manifest -> BINGX_RAW_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
