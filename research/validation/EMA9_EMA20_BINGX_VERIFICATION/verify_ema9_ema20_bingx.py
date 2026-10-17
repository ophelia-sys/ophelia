"""EMA9/EMA20 crossover verification - BingX SOLUSDT 5m (resilient small-page fetcher).

Anchors (IST = UTC+5:30): A ~ 2026-08-21 21:00 IST (15:30 UTC) | B ~ 2026-08-22 02:20 IST
(= 2026-08-21 20:50 UTC). EMA alpha=2/(N+1), SMA seed. Cross confirmed at close only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))
SYMBOL_API = "SOL-USDT"
HOSTS = ["https://open-api.bingx.com", "https://open-api.bingx.pro"]
PATH = "/openApi/swap/v3/quote/klines"
BIN_BASE = "https://fapi.binance.com/fapi/v1/klines"
TF_MS = 300_000
PAGE = 150                       # small pages survive when big responses get reset
FETCH_START_UTC = datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)
ANCHOR_A_UTC = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)
ANCHOR_B_UTC = datetime(2026, 8, 21, 20, 50, tzinfo=timezone.utc)
CSV_BX = os.path.join(HERE, "bingx_sol_5m_verification_window.csv")


def http_get(url: str, tries: int = 4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ophelia-emaverify/1.0",
                              "Connection": "close"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(min(3.0 * (i + 1), 20.0))
    raise last if isinstance(last, Exception) else RuntimeError("fetch failed")


def fetch_bingx() -> pd.DataFrame:
    have = pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])
    if os.path.exists(CSV_BX):
        have = pd.read_csv(CSV_BX)
        have["open_time"] = have["open_time"].astype("int64")
    t = int(FETCH_START_UTC.timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - TF_MS
    hi_host = HOSTS[0]
    while t < end_ms:
        win_end = min(t + PAGE * TF_MS, end_ms)
        body, used = None, None
        for h in HOSTS:
            try:
                body = http_get(f"{h}{PATH}?symbol={SYMBOL_API}&interval=5m"
                                f"&startTime={t}&endTime={win_end}&limit={PAGE}")
                if body.get("code") not in (0, "0"):
                    body = None
                    continue
                used = h
                break
            except Exception:
                continue
        if body is None:
            print(f"  both hosts failed at {t}; cooling down 60s", flush=True)
            time.sleep(60)
            continue
        hi_host = used
        data = body.get("data") or []
        for k in data:
            have = pd.concat([have, pd.DataFrame([{
                "open_time": int(k["time"]),
                "open": float(k["open"]), "high": float(k["high"]),
                "low": float(k["low"]), "close": float(k["close"]),
                "volume": float(k.get("volume", 0.0))}])], ignore_index=True)
        have = have.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
        have.to_csv(CSV_BX, index=False)                 # checkpoint every page
        nxt = win_end + TF_MS if len(data) else int(data[0]["time"]) + TF_MS if data else win_end + TF_MS
        if len(data):
            nxt = int(data[-1]["time"]) + TF_MS
        if nxt <= t:
            break
        t = nxt
        time.sleep(0.8)
    print(f"bingx fetch done via {hi_host}: {len(have)} candles", flush=True)
    return have


def fetch_binance() -> pd.DataFrame:
    rows, t = [], int(FETCH_START_UTC.timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - TF_MS
    while t < end_ms:
        kl = http_get(f"{BIN_BASE}?symbol=SOLUSDT&interval=5m&startTime={t}"
                      f"&endTime={end_ms}&limit=1500")
        if not kl:
            break
        for k in kl:
            rows.append({"open_time": int(k[0]), "close": float(k[4])})
        nxt = int(kl[-1][0]) + TF_MS
        if nxt <= t:
            break
        t = nxt
        time.sleep(0.3)
    return pd.DataFrame(rows).drop_duplicates("open_time").sort_values("open_time")


def ema(close: np.ndarray, n: int) -> np.ndarray:
    alpha = 2.0 / (n + 1.0)
    out = np.full(len(close), np.nan)
    out[n - 1] = close[:n].mean()
    for i in range(n, len(close)):
        out[i] = alpha * close[i] + (1 - alpha) * out[i - 1]
    return out


def fmt(ts_ms: int):
    u = datetime.fromtimestamp(ts_ms / 1000, timezone.utc)
    return (u.strftime("%Y-%m-%d %H:%M:%S"),
            u.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"))


def ts_of(utc_str: str) -> int:
    return int(datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def main() -> int:
    bx = fetch_bingx()
    o = bx["open"].to_numpy(float); h = bx["high"].to_numpy(float)
    l = bx["low"].to_numpy(float); c = bx["close"].to_numpy(float)
    ot = bx["open_time"].to_numpy(np.int64)
    e9, e20 = ema(c, 9), ema(c, 20)

    s = pd.Series(c).ewm(span=9, adjust=False).mean().to_numpy()
    pandas_maxdiff = float(np.nanmax(np.abs(s[200:] - e9[200:]))) if len(c) > 300 else None

    crosses = []
    for i in range(1, len(c)):
        if any(np.isnan(x) for x in (e9[i], e20[i], e9[i - 1], e20[i - 1])):
            continue
        d0 = e9[i - 1] - e20[i - 1]
        d1 = e9[i] - e20[i]
        if d0 <= 0 and d1 > 0:
            direction = "LONG"
        elif d0 >= 0 and d1 < 0:
            direction = "SHORT"
        else:
            continue
        crosses.append({
            "direction": direction, "event_idx": i,
            "candle_open_utc": fmt(ot[i])[0], "candle_open_ist": fmt(ot[i])[1],
            "candle_close_utc": fmt(ot[i] + TF_MS)[0],
            "confirmation_ist": fmt(ot[i] + TF_MS)[1],
            "next_open_utc": fmt(ot[i] + TF_MS)[0],
            "next_open_ist": fmt(ot[i] + TF_MS)[1],
            "ema9_prev": round(e9[i - 1], 6), "ema20_prev": round(e20[i - 1], 6),
            "ema9": round(e9[i], 6), "ema20": round(e20[i], 6),
            "spread_prev": round(d0, 6), "spread": round(d1, 6),
            "confirm_close": c[i]})
    cdf = pd.DataFrame(crosses)
    cdf.to_csv(os.path.join(HERE, "OPHELIA_EMA_CROSSOVER_FORENSICS.csv"), index=False)

    def nearest(anchor_utc, label):
        a_ms = int(anchor_utc.timestamp() * 1000)
        best, best_dt = None, None
        for _, row in cdf.iterrows():
            dt = ts_of(row["candle_close_utc"]) - a_ms
            if best_dt is None or abs(dt) < abs(best_dt):
                best, best_dt = row, dt
        out = {"anchor_label": label,
               "anchor_utc": anchor_utc.isoformat(),
               "anchor_ist": anchor_utc.astimezone(IST).strftime("%Y-%m-%d %H:%M")}
        if best is None:
            out["found"] = False
            return out
        i = int(best["event_idx"])
        out.update({"found": True, "direction": best["direction"],
                    "exact_candle_open_utc": best["candle_open_utc"],
                    "exact_candle_open_ist": best["candle_open_ist"],
                    "confirmation_close_utc": best["candle_close_utc"],
                    "delta_minutes_from_anchor": round(best_dt / 60_000, 1),
                    "bar_index": i, "ema9": best["ema9"], "ema20": best["ema20"],
                    "close": float(c[i])})
        return out

    anch = [nearest(ANCHOR_A_UTC, "A(~21:00 IST)"),
            nearest(ANCHOR_B_UTC, "B(~02:20 IST)")]
    pd.DataFrame(anch).to_csv(
        os.path.join(HERE, "OPHELIA_EMA_ANCHOR_VERIFICATION.csv"), index=False)

    forensics = []
    for a in anch:
        if not a.get("found"):
            continue
        i = a["bar_index"]
        for off, tag in ((-1, "BEFORE"), (0, "CROSSOVER"), (1, "AFTER")):
            j = i + off
            forensics.append({"anchor": a["anchor_label"], "role": tag,
                              "open_utc": fmt(ot[j])[0], "open_ist": fmt(ot[j])[1],
                              "open": o[j], "high": h[j], "low": l[j], "close": c[j],
                              "ema9": round(e9[j], 6), "ema20": round(e20[j], 6)})
    pd.DataFrame(forensics).to_csv(
        os.path.join(HERE, "OPHELIA_EMA_ANCHOR_CANDLES.csv"), index=False)

    feed_diag = {}
    try:
        bn = fetch_binance()
        m = bx.merge(bn, on="open_time", suffixes=("_bx", "_bn"))
        dc = (m["close_bx"] - m["close_bn"]).abs()
        feed_diag = {"overlap_bars": int(len(m)),
                     "mean_abs_close_diff": round(float(dc.mean()), 6),
                     "max_abs_close_diff": round(float(dc.max()), 6),
                     "mean_abs_close_diff_bps": round(
                         float((dc / m["close_bn"] * 1e4).mean()), 3)}
    except Exception as e:                                       # noqa: BLE001
        feed_diag = {"error": str(e)[:120]}

    w_lo = int((ANCHOR_A_UTC - timedelta(hours=8)).timestamp() * 1000)
    w_hi = int((ANCHOR_B_UTC + timedelta(hours=6)).timestamp() * 1000)
    win = [r.to_dict() for _, r in cdf.iterrows()
           if w_lo <= ts_of(r["candle_close_utc"]) <= w_hi]

    results = {
        "meta": {
            "symbol_api": SYMBOL_API, "contract": "USD-M perpetual swap",
            "timeframe": "5m", "timezone_internal": "UTC",
            "fetch_start_utc": FETCH_START_UTC.isoformat(),
            "last_complete_bar_utc": fmt(int(ot[-1]) + TF_MS)[0],
            "candles": int(len(bx)),
            "csv_sha256": hashlib.sha256(open(CSV_BX, "rb").read()).hexdigest(),
            "ema": {"alpha_9": 0.2, "alpha_20": 2 / 21,
                    "seed": "SMA(first N closes)", "warmup_bars": 20,
                    "pandas_ewm_maxdiff_after_bar200": pandas_maxdiff},
            "crossover_definition":
                "LONG d<=0->d>0 | SHORT d>=0->d<0 (d=ema9-ema20), confirmed at close",
            "total_crossovers_in_window": len(cdf),
            "screenshot_timeframe": "UNKNOWN (no timeframe axis visible in provided crop)",
        },
        "anchors": anch,
        "windowed_crossovers": win,
        "feed_diagnostic_binance": feed_diag,
    }
    with open(os.path.join(HERE, "OPHELIA_EMA_CROSSOVER_RESULTS.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
        f.write("\n")

    print(f"candles {len(bx)} | crossovers {len(cdf)} | pandas maxdiff {pandas_maxdiff}")
    print("windowed crossovers:")
    for r in win:
        print(f"  {r['direction']:5s} open {r['candle_open_utc']} | IST {r['candle_open_ist']}"
              f" | close {r['confirm_close']:.4f} | e9 {r['ema9']:.4f} e20 {r['ema20']:.4f}")
    for a in anch:
        print(a["anchor_label"], "->", a.get("direction"),
              a.get("exact_candle_open_utc"), "| IST",
              a.get("exact_candle_open_ist"), "| delta_min",
              a.get("delta_minutes_from_anchor"))
    print("feed diag:", feed_diag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
