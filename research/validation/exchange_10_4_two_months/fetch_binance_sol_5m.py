"""Fetch Binance SOLUSDT USD-M perpetual 5m klines — Phase 2.9B secondary cross-check.

Endpoint : GET https://fapi.binance.com/fapi/v1/klines
Params   : symbol=SOLUSDT, interval=5m, startTime/endTime (ms), limit<=1500
Output   : raw JSON pages preserved + canonical CSV + manifest JSON.
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

BASE = "https://fapi.binance.com/fapi/v1/klines"
SYMBOL = "SOLUSDT"
INTERVAL = "5m"
TF_MS = 300_000
START_MS = 1_780_272_000_000          # 2026-06-01 00:00:00 UTC
END_MS_EXCL = 1_785_542_400_000       # 2026-08-01 00:00:00 UTC (exclusive)
LIMIT = 1500
HERE = os.path.dirname(os.path.abspath(__file__))


def http_get(url: str, tries: int = 4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-p29b/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read().decode())
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"Binance fetch failed after {tries} tries: {last}")


def fetch_all() -> tuple:
    rows, pages = [], []
    t = START_MS
    page_no = 0
    while t < END_MS_EXCL:
        page_no += 1
        url = (f"{BASE}?symbol={SYMBOL}&interval={INTERVAL}"
               f"&startTime={t}&endTime={END_MS_EXCL - 1}&limit={LIMIT}")
        status, body = http_get(url)
        pages.append({"page": page_no, "url": url, "status": status,
                      "rows_returned": len(body),
                      "retrieved_utc": datetime.now(timezone.utc).isoformat()})
        if not body:
            break
        for k in body:
            rows.append({
                "candle_open_time": int(k[0]),
                "open": float(k[1]), "high": float(k[2]),
                "low": float(k[3]), "close": float(k[4]),
                "volume": float(k[5]),
            })
        last_t = int(body[-1][0])
        nxt = last_t + TF_MS
        if nxt <= t:
            break
        t = nxt
        time.sleep(0.15)
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

    csv_path = os.path.join(HERE, "binance_sol_5m_2026_06_07.csv")
    df.to_csv(csv_path, index=False, float_format="%.10f", lineterminator="\n")

    raw_pages_path = os.path.join(HERE, "raw", "binance_raw_pages.json")
    with open(raw_pages_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)

    manifest = {
        "exchange": "BINANCE",
        "endpoint": BASE,
        "symbol_api": SYMBOL,
        "contract_type": "USD-M perpetual futures",
        "interval": INTERVAL,
        "timezone": "UTC (epoch ms)",
        "start_utc": datetime.fromtimestamp(START_MS / 1000, timezone.utc).isoformat(),
        "end_utc_exclusive": datetime.fromtimestamp(END_MS_EXCL / 1000, timezone.utc).isoformat(),
        "candle_count_raw": int(n_raw),
        "candle_count_deduped": int(len(df)),
        "duplicate_rows_removed": int(n_raw - len(df)),
        "pages_fetched": len(pages),
        "retrieval_completed_utc": datetime.now(timezone.utc).isoformat(),
        "csv_filename": csv_path,
        "csv_sha256": sha256_file(csv_path),
        "raw_pages_filename": raw_pages_path,
    }
    with open(os.path.join(HERE, "BINANCE_RAW_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("BINANCE candles:", len(df),
          "| span:", datetime.fromtimestamp(int(df['candle_open_time'].iloc[0]) / 1000, timezone.utc),
          "->", datetime.fromtimestamp(int(df['candle_open_time'].iloc[-1]) / 1000, timezone.utc))
    print("manifest -> BINANCE_RAW_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
