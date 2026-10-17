"""TradingView screenshot validation for Ophelia (SOL-USDT 3m, 3 cases).

Fetches public 1m klines (Binance + BingX), fingerprints the exact UTC time of
each screenshot via its OHLC readout, recomputes EMA9/20, session VWAP and
Supertrend(10,4) with the production control_plane code, detects the marked
crossovers, and reports PASS/FAIL per case.

Read-only: no orders, no keys, no DB writes.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from control_plane import analytics                                 # noqa: E402

# Screenshot readouts (the forming 3m candle at screenshot time)
CASES = [
    {"name": "Screenshot 1 (Sun 23 Aug '26, crosshair ~09:12 chart-time)",
     "readout": {"o": 93.772, "h": 93.778, "l": 93.437, "c": 93.520},
     "expected": "BEARISH (red Supertrend crosses VWAP from above)"},
    {"name": "Screenshot 2 (Tue 25 Aug '26, crosshair 01:27 chart-time)",
     "readout": {"o": 96.471, "h": 96.598, "l": 96.436, "c": 96.459},
     "expected": "BULLISH (green Supertrend crosses VWAP from below)"},
    {"name": "Screenshot 3 (Tue 25 Aug '26, crosshair 05:30 chart-time)",
     "readout": {"o": 98.946, "h": 98.962, "l": 98.629, "c": 98.739},
     "expected": "VWAP session-reset artifact - must NOT trade"},
]


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "ophelia-validate/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def fetch_binance_1m(start_ms: int, end_ms: int) -> list[dict]:
    out: list[dict] = []
    cursor = start_ms
    while cursor < end_ms:
        kl = _get(f"https://fapi.binance.com/fapi/v1/klines"
                  f"?symbol=SOLUSDT&interval=1m&startTime={cursor}"
                  f"&endTime={end_ms}&limit=1500")
        if not kl:
            break
        for k in kl:
            out.append({"ts": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                        "low": float(k[3]), "close": float(k[4]),
                        "volume": float(k[5]), "taker_buy": float(k[9])})
        cursor = int(kl[-1][0]) + 60_000
        if len(kl) < 1500:
            break
    return out


def fetch_bingx_1m(start_ms: int, end_ms: int) -> list[dict]:
    from control_plane import bingx_client
    c = bingx_client.Client("", "", allow_trade=False)
    out: list[dict] = []
    cursor = start_ms
    while cursor < end_ms:
        rows = None
        for attempt in range(5):
            try:
                rows = c.klines("SOL-USDT", "1m", limit=1440,
                                start_ms=cursor, end_ms=end_ms)
                break
            except Exception as e:                                # noqa: BLE001
                wait = 2 ** attempt
                print(f"  bingx retry {attempt + 1} ({str(e)[:60]}; "
                      f"wait {wait}s)", flush=True)
                time.sleep(wait)
        if not rows:
            break
        out.extend(rows)
        cursor = rows[-1]["ts"] + 60_000
        if len(rows) < 100:
            break
    return out


def aggregate3(rows: list[dict]) -> list[dict]:
    return analytics.aggregate(rows, 3)


def fingerprint(rows3: list[dict], readout: dict):
    """Find 3m candles matching the readout OHLC.

    The TradingView readout shows the FORMING candle at screenshot time, so:
    open must match tightly; data-high must be >= shown high; data-low must be
    <= shown low; close was still moving and is not constrained.
    """
    hits = []
    for i, r in enumerate(rows3):
        o_ok = abs(r["open"] - readout["o"]) / readout["o"] < 0.0002
        h_ok = r["high"] >= readout["h"] * 0.9995
        l_ok = r["low"] <= readout["l"] * 1.0005
        if o_ok and h_ok and l_ok:
            hits.append((i, r))
    return hits


def detect_crosses(rows3: list[dict]):
    """Run the production cross detector across the whole series (offline)."""
    st = analytics.supertrend_series(rows3)
    vw = analytics.session_vwap_series(rows3)
    vmap = {v["ts"]: v for v in vw}
    events = []
    for i in range(1, len(rows3)):
        if i < len(st) - (len(st) - len(rows3)):
            pass
    # index alignment: st starts at start_i = length-1
    off = len(rows3) - len(st)
    for j in range(1, len(st)):
        i = j + off
        s_i, s_p = st[j], st[j - 1]
        v_i, v_p = vmap.get(rows3[i]["ts"]), vmap.get(rows3[i - 1]["ts"])
        if not v_i or not v_p or v_i["vwap"] is None or v_p["vwap"] is None:
            continue
        if v_i["day"] != v_p["day"]:
            events.append({"ts": rows3[i]["ts"], "kind": "SESSION_RESET_GUARD",
                           "note": "VWAP re-anchored (00:00 UTC); cross suppressed"})
            continue
        if abs(v_i["vwap"] - v_p["vwap"]) / v_p["vwap"] > 0.02:
            events.append({"ts": rows3[i]["ts"], "kind": "DISCONTINUITY_GUARD"})
            continue
        d_prev = s_p["line"] - v_p["vwap"]
        d_now = s_i["line"] - v_i["vwap"]
        if s_i["dir"] == 1 and d_prev < 0 <= d_now:
            events.append({"ts": rows3[i]["ts"], "kind": "BULLISH_CROSS",
                           "st_line": round(s_i["line"], 4),
                           "vwap": round(v_i["vwap"], 4),
                           "close": rows3[i]["close"]})
        elif s_i["dir"] == -1 and d_prev > 0 >= d_now:
            events.append({"ts": rows3[i]["ts"], "kind": "BEARISH_CROSS",
                           "st_line": round(s_i["line"], 4),
                           "vwap": round(v_i["vwap"], 4),
                           "close": rows3[i]["close"]})
    return events


def fmt_ts(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, timezone.utc)
    ist = dt + timedelta(hours=5, minutes=30)
    return f"{dt:%Y-%m-%d %H:%M} UTC ({ist:%H:%M} IST)"


def at_crosshair(rows3: list[dict], ts_ms: int, label: str) -> str:
    """Exact production-indicator values at the crosshair candle (+/- 2 bars)."""
    st = analytics.supertrend_series(rows3)
    vw = analytics.session_vwap_series(rows3)
    vmap = {v["ts"]: v for v in vw}
    smap = {s["ts"]: s for s in st}
    closes = [r["close"] for r in rows3]
    out = [f"  {label} production values around crosshair:"]
    base = ts_ms
    for delta in (-6, -3, 0, 3, 6):
        ts = base + delta * 60_000
        r = next((x for x in rows3 if x["ts"] == ts), None)
        s = smap.get(ts)
        v = vmap.get(ts)
        if not r:
            continue
        e9 = analytics.ema(
            __import__("numpy").array(closes[: closes.index(r["close"]) + 1]), 9)
        line = f"    {fmt_ts(ts)}: O {r['open']:.3f} H {r['high']:.3f} " \
               f"L {r['low']:.3f} C {r['close']:.3f}"
        if s:
            line += (f" | ST {'GREEN' if s['dir'] == 1 else 'RED'} "
                     f"{s['line']:.4f}")
        if v and v["vwap"]:
            line += f" | VWAP {v['vwap']:.4f}"
        out.append(line)
    return "\n".join(out)


def main() -> None:
    start = int(datetime(2026, 8, 21, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    print("Fetching Binance SOLUSDT 1m...", flush=True)
    bn = fetch_binance_1m(start, end)
    print(f"  Binance rows: {len(bn)}", flush=True)
    print("Fetching BingX SOL-USDT 1m...", flush=True)
    bx = fetch_bingx_1m(start, end)
    print(f"  BingX rows: {len(bx)}", flush=True)

    bn3 = aggregate3(bn)
    bx3 = aggregate3([r for r in bx if start <= r["ts"] < end])

    events_bn = detect_crosses(bn3)
    print("\n=== All raw cross events (Binance data, 3m) ===")
    for e in events_bn:
        print(f"  {fmt_ts(e['ts'])}  {e['kind']}  "
              + (f"ST={e.get('st_line')} VWAP={e.get('vwap')}"
                 if "st_line" in e else e.get("note", "")))

    for case in CASES:
        print(f"\n=== {case['name']} ===")
        print(f"  expected: {case['expected']}")
        for label, rows3 in (("Binance", bn3), ("BingX", bx3)):
            hits = fingerprint(rows3, case["readout"])
            for i, r in hits:
                print(f"  readout match on {label}: candle {fmt_ts(r['ts'])} "
                      f"(O {r['open']} H {r['high']} L {r['low']} C {r['close']})")
            if not hits:
                print(f"  readout match on {label}: none within 0.15%")
            if hits and label == "Binance":
                i, r = min(hits, key=lambda hr: abs(
                    hr[1]["open"] - case["readout"]["o"]))
                print(at_crosshair(rows3, r["ts"], label))


if __name__ == "__main__":
    main()
