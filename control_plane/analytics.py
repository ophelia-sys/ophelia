"""Canonical production indicators + analytics (aggregation, flow, profile, book).

Indicator implementations mirror the verified canonical code:
  EMA: alpha=2/(N+1), SMA seed.  VWAP: typical price, volume-weighted, UTC session.
  Supertrend(10, 4.0): Pine-equivalent band ratchet.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone

import numpy as np

from . import db
from . import config
from . import fast_math

# ------------------------------------------------------------------ indicators

def ema(close: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    if len(close) < n:
        return out
    k = 2.0 / (n + 1.0)
    out[n - 1] = close[:n].mean()
    for i in range(n, len(close)):
        out[i] = k * close[i] + (1 - k) * out[i - 1]
    return out


def session_vwap(df_rows: list[dict]) -> float:
    """Session VWAP over the provided rows (caller passes current UTC-day rows)."""
    pv = sum(((r["high"] + r["low"] + r["close"]) / 3.0) * (r["volume"] or 0) for r in df_rows)
    v = sum((r["volume"] or 0) for r in df_rows)
    return pv / v if v > 0 else None


def supertrend(rows: list[dict], length=10, factor=4.0):
    """Returns (direction, active_line) of the LAST bar; Pine-equivalent recursion."""
    h = np.array([r["high"] for r in rows], float)
    l = np.array([r["low"] for r in rows], float)
    c = np.array([r["close"] for r in rows], float)
    if len(c) < length + 2:
        return None, None
    tr = np.empty(len(c)); tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - pc), np.abs(l[1:] - pc)])
    atr = np.full(len(c), np.nan)
    atr[length - 1] = tr[:length].mean()
    a = 1.0 / length
    for i in range(length, len(c)):
        atr[i] = a * tr[i] + (1 - a) * atr[i - 1]
    hl2 = (h + l) / 2
    bu = hl2 + factor * atr; bl = hl2 - factor * atr
    fu = np.copy(bu); fl = np.copy(bl); d = np.ones(len(c), dtype=int)
    start_i = next((k for k in range(len(c)) if not math.isnan(bu[k])), None)
    if start_i is None:
        return None, None
    fu[:start_i + 1] = bu[start_i]
    fl[:start_i + 1] = bl[start_i]
    d[:start_i + 1] = 1
    for i in range(start_i + 1, len(c)):
        fu[i] = bu[i] if (bu[i] < fu[i-1] or c[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = bl[i] if (bl[i] > fl[i-1] or c[i-1] < fl[i-1]) else fl[i-1]
        if d[i-1] == 1 and c[i] < fl[i]:
            d[i] = -1
        elif d[i-1] == -1 and c[i] > fu[i]:
            d[i] = 1
        else:
            d[i] = d[i-1]
    active = fl[-1] if d[-1] == 1 else fu[-1]
    return int(d[-1]), float(active)


def supertrend_series(rows: list[dict], length=10, factor=4.0):
    """Full Supertrend series: [{ts, dir, line}] per bar (same recursion as
    supertrend(); kept separate so the last-bar helper stays untouched)."""
    h = np.array([r["high"] for r in rows], float)
    l = np.array([r["low"] for r in rows], float)
    c = np.array([r["close"] for r in rows], float)
    n = len(c)
    if n < length + 2:
        return []
    tr = np.empty(n); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]),
                                np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan)
    atr[length - 1] = tr[:length].mean()
    a = 1.0 / length
    for i in range(length, n):
        atr[i] = a * tr[i] + (1 - a) * atr[i - 1]
    hl2 = (h + l) / 2
    bu = hl2 + factor * atr; bl = hl2 - factor * atr
    fu = np.copy(bu); fl = np.copy(bl); d = np.ones(n, dtype=int)
    start_i = length - 1
    fu[:start_i + 1] = bu[start_i]
    fl[:start_i + 1] = bl[start_i]
    for i in range(start_i + 1, n):
        fu[i] = bu[i] if (bu[i] < fu[i-1] or c[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = bl[i] if (bl[i] > fl[i-1] or c[i-1] < fl[i-1]) else fl[i-1]
        if d[i-1] == 1 and c[i] < fl[i]:
            d[i] = -1
        elif d[i-1] == -1 and c[i] > fu[i]:
            d[i] = 1
        else:
            d[i] = d[i-1]
    return [{"ts": rows[i]["ts"], "dir": int(d[i]),
             "line": float(fl[i] if d[i] == 1 else fu[i])}
            for i in range(start_i, n)]


def session_vwap_series(rows: list[dict]) -> list[dict]:
    """UTC-day session VWAP series (hlc3, volume-weighted, resets 00:00 UTC)."""
    out: list[dict] = []
    day = None
    pv = v = 0.0
    for r in rows:
        d = r["ts"] // 86_400_000
        if d != day:
            day = d
            pv = v = 0.0
        tp = (r["high"] + r["low"] + r["close"]) / 3.0
        vol = r["volume"] or 0.0
        pv += tp * vol
        v += vol
        out.append({"ts": r["ts"], "vwap": (pv / v) if v > 0 else None,
                    "day": int(day)})
    return out


def st_vwap_cross_event(symbol: str, tf_min: int):
    """Detect a CONFIRMED Supertrend<->VWAP line cross on the last CLOSED bar.

    BULLISH: green (dir=+1) ST line crosses VWAP from below.
    BEARISH: red  (dir=-1) ST line crosses VWAP from above.
    Guards: UTC-day VWAP re-anchoring (session reset) is never traded as a
    cross; >2% single-bar VWAP discontinuities are rejected as data artifacts.
    Callers must pass candle_ts as an idempotency key.
    """
    cd = get_candles(symbol, lookback_min=max(300, tf_min * 40),
                     base_interval_min=1, agg_interval_min=tf_min)
    if "error" in cd or cd["count"] < 30:
        return None
    rows = cd["candles"]
    st = supertrend_series(rows)
    vw = session_vwap_series(rows)
    if len(st) < 2 or len(vw) != len(rows):
        return None
    vmap = {v["ts"]: v for v in vw}
    i = len(rows) - 2
    s_i, s_p = st[-2], st[-3]
    v_i, v_p = vmap.get(rows[i]["ts"]), vmap.get(rows[i - 1]["ts"])
    if not v_i or not v_p or v_i["vwap"] is None or v_p["vwap"] is None:
        return None
    if v_i["day"] != v_p["day"]:                       # session boundary
        return None
    if abs(v_i["vwap"] - v_p["vwap"]) / v_p["vwap"] > 0.02:
        return None                                    # discontinuity artifact
    d_prev = s_p["line"] - v_p["vwap"]
    d_now = s_i["line"] - v_i["vwap"]
    if s_i["dir"] == 1 and d_prev < 0 <= d_now:
        return {"direction": "LONG", "candle_ts": rows[i]["ts"],
                "kind": "VWAP_SUPERTREND", "st_dir": 1, "st_line": s_i["line"],
                "vwap": v_i["vwap"], "close": float(rows[i]["close"])}
    if s_i["dir"] == -1 and d_prev > 0 >= d_now:
        return {"direction": "SHORT", "candle_ts": rows[i]["ts"],
                "kind": "VWAP_SUPERTREND", "st_dir": -1, "st_line": s_i["line"],
                "vwap": v_i["vwap"], "close": float(rows[i]["close"])}
    return None


def get_vwap(symbol: str, tf_min: int = 3) -> dict:
    """Current session VWAP state for symbol on tf_min aggregation."""
    cd = get_candles(symbol, lookback_min=max(300, tf_min * 40), base_interval_min=1, agg_interval_min=tf_min)
    if "error" in cd:
        return cd
    vw = session_vwap_series(cd["candles"])
    cur = vw[-1] if vw else None
    if not cur or cur["vwap"] is None:
        return {"error": "insufficient volume for VWAP"}
    px = cd["candles"][-1]["close"]
    return {"symbol": symbol, "timeframe_min": tf_min,
            "vwap": round(cur["vwap"], 6), "price": px,
            "distance_pct": round((px - cur["vwap"]) / cur["vwap"] * 100, 4),
            "above": bool(px > cur["vwap"]),
            "session_day_utc": cur["day"]}


def get_supertrend(symbol: str, tf_min: int = 3) -> dict:
    """Current Supertrend(10,4) state for symbol on tf_min aggregation."""
    cd = get_candles(symbol, lookback_min=max(300, tf_min * 40), base_interval_min=1, agg_interval_min=tf_min)
    if "error" in cd:
        return cd
    d, line = supertrend(cd["candles"])
    if d is None:
        return {"error": "insufficient candles for Supertrend"}
    return {"symbol": symbol, "timeframe_min": tf_min, "direction": d,
            "state": "GREEN" if d == 1 else "RED", "line": round(line, 6),
            "price": cd["candles"][-1]["close"]}


def ema_series(symbol: str, tf_min: int, n: int) -> dict:
    cd = get_candles(symbol, lookback_min=max(300, tf_min * 40), base_interval_min=1, agg_interval_min=tf_min)
    if "error" in cd:
        return cd
    closes = np.array([r["close"] for r in cd["candles"]], float)
    e = ema(closes, n)
    return {"symbol": symbol, "timeframe_min": tf_min, "period": n,
            "value": round(float(e[-1]), 6) if len(closes) >= n else None}


def vwap_regime(symbol: str, tf_min: int = 3,
                min_sep_pct: float | None = None,
                persistence: int | None = None) -> dict:
    """VWAP regime gate - the common directional filter for ALL strategies.

    State machine (documented, configurable):
      CLEAR_ABOVE : price clearly above VWAP, last N completed candle closes
                    all above, no VWAP cross inside the persistence window
                    -> LONG only
      CLEAR_BELOW : mirror image -> SHORT only
      CHOP        : separation < min_sep_pct, OR closes not one-sided,
                    OR a recent VWAP cross -> NO trade

    min_sep_pct default 0.10% and persistence default 3 completed candles
    are documented starting points (config.VWAP_*), not hard-coded law.
    """
    min_sep = config.VWAP_MIN_SEPARATION_PCT if min_sep_pct is None \
        else min_sep_pct
    n = config.VWAP_PERSISTENCE_CANDLES if persistence is None else persistence
    cd = get_candles(symbol, lookback_min=max(300, tf_min * 40),
                     base_interval_min=1, agg_interval_min=tf_min)
    if "error" in cd or cd["count"] < n + 2:
        return {"symbol": symbol, "state": "CHOP",
                "reason": "insufficient data", "eligible": "NONE"}
    rows = cd["candles"]
    vw = session_vwap_series(rows)
    vmap = {v["ts"]: v for v in vw}
    # completed candles only: the last row may still be forming
    completed = [r for r in rows[:-1] if vmap.get(r["ts"], {}).get("vwap")]
    if len(completed) < n + 1:
        return {"symbol": symbol, "state": "CHOP",
                "reason": "insufficient completed candles", "eligible": "NONE"}
    last = completed[-1]
    price = last["close"]
    vwap = vmap[last["ts"]]["vwap"]
    sep = abs(price - vwap) / vwap * 100 if vwap else 0.0
    window = completed[-n:]
    sides = ["ABOVE" if r["close"] > vmap[r["ts"]]["vwap"] else "BELOW"
             for r in window]
    # recent cross: any side flip between consecutive completed candles
    # inside the persistence window (including entry into it)
    prev_side = ("ABOVE" if completed[-n - 1]["close"]
                 > vmap[completed[-n - 1]["ts"]]["vwap"] else "BELOW") \
        if len(completed) > n else sides[0]
    recent_cross = any(s != p for p, s in zip([prev_side] + sides[:-1], sides))
    one_side = len(set(sides)) == 1
    if sep < min_sep:
        state, eligible, reason = "CHOP", "NONE", \
            f"separation {sep:.3f}% < min {min_sep:g}% (too close to VWAP)"
    elif not one_side:
        state, eligible, reason = "CHOP", "NONE", \
            f"last {n} closes mixed ({'/'.join(sides)})"
    elif recent_cross:
        state, eligible, reason = "CHOP", "NONE", \
            "VWAP crossed inside the persistence window"
    else:
        state = "CLEAR_ABOVE" if sides[-1] == "ABOVE" else "CLEAR_BELOW"
        eligible = "LONG" if state == "CLEAR_ABOVE" else "SHORT"
        reason = (f"{n}/{n} completed closes above, no recent cross"
                  if state == "CLEAR_ABOVE" else
                  f"{n}/{n} completed closes below, no recent cross")
    return {"symbol": symbol, "timeframe_min": tf_min, "price": price,
            "vwap": round(vwap, 6),
            "separation_pct": round((price - vwap) / vwap * 100, 4),
            "abs_separation_pct": round(sep, 4),
            "min_sep_pct": min_sep, "persistence": n,
            "closes_side": sides, "recent_cross": recent_cross,
            "state": state, "eligible": eligible, "reason": reason,
            "closes_utc": [datetime.fromtimestamp(r["ts"] / 1000,
                                                  timezone.utc)
                           .strftime("%H:%M") for r in window]}


def aggregate(rows: list[dict], tf_minutes: int, closed_only: bool = False) -> list[dict]:
    """Aggregate 1m rows into tf-minute candles (aligned to epoch grid)."""
    ms = tf_minutes * 60_000
    buckets: dict[int, list] = {}
    bucket_counts: dict[int, int] = {}
    for r in rows:
        k = (r["ts"] // ms) * ms
        b = buckets.get(k)
        if b is None:
            buckets[k] = [r["open"], r["high"], r["low"], r["close"],
                          r["volume"] or 0, r.get("taker_buy") or 0,
                          r.get("trades") or 0]
            bucket_counts[k] = 1
        else:
            b[1] = max(b[1], r["high"]); b[2] = min(b[2], r["low"])
            b[3] = r["close"]; b[4] += r["volume"] or 0
            b[5] += r.get("taker_buy") or 0; b[6] += r.get("trades") or 0
            bucket_counts[k] += 1

    now_ms = int(time.time() * 1000)
    items = sorted(buckets.items())
    if closed_only and items:
        last_k, _ = items[-1]
        if (last_k + ms > now_ms) or (bucket_counts.get(last_k, 0) < tf_minutes):
            items = items[:-1]

    return [{"ts": k, "open": v[0], "high": v[1], "low": v[2], "close": v[3],
             "volume": v[4], "taker_buy": v[5], "trades": v[6]}
            for k, v in items]



# ------------------------------------------------------------------ analytics

def get_candles(symbol: str, lookback_min: int, base_interval_min=1,
                agg_interval_min=None):
    now = int(time.time() * 1000)
    start = now - lookback_min * 60_000
    base_tf = base_interval_min
    raw = db.query_candles(symbol, start - base_tf * 60_000, now)
    if not raw:
        return {"error": "no data retained in the last 24h for this symbol"}
    # resample base->1m grid then aggregate
    rows1m = aggregate(raw, 1)
    out_tf = agg_interval_min or base_tf
    rows = aggregate(rows1m, out_tf) if out_tf > 1 else rows1m
    rows = [r for r in rows if r["ts"] >= start]
    for r in rows:
        r["time_utc"] = datetime.fromtimestamp(r["ts"] / 1000, timezone.utc).isoformat()
    return {"symbol": symbol, "interval_min": out_tf,
            "count": len(rows), "candles": rows}


def get_market_snapshot(symbol: str, lookback_min=30, agg_interval_min=5,
                        indicators=("EMA9", "EMA20"), volume_flow=False,
                        volume_profile=False, order_book=False, exchange=None):
    out: dict = {"symbol": symbol}
    warmup_min = 300                      # >=20 agg-bars for EMA20 even on 5m grid
    cd_full = get_candles(symbol, max(lookback_min, 30) + warmup_min, 1,
                          agg_interval_min)
    if "error" in cd_full:
        return cd_full
    rows_all = cd_full["candles"]
    cutoff_ts = rows_all[-1]["ts"] - lookback_min * 60_000 if rows_all else 0
    rows_window = [r for r in rows_all if r["ts"] >= cutoff_ts]
    cd = {"symbol": symbol, "interval_min": agg_interval_min,
          "count": len(rows_window), "candles": rows_window}
    if "error" in cd:
        return cd
    out["candles"] = cd
    closes = np.array([r["close"] for r in rows_all], float)   # full series for EMAs
    last = rows_window[-1] if rows_window else None
    out["last_price"] = last["close"] if last else None
    ind = {}
    if "EMA9" in indicators:
        e9 = ema(closes, 9)
        ind["EMA9"] = round(float(e9[-1]), 6) if len(closes) >= 9 else None
    if "EMA20" in indicators:
        e20 = ema(closes, 20)
        ind["EMA20"] = round(float(e20[-1]), 6) if len(closes) >= 20 else None
    if "EMA9" in ind and "EMA20" in ind and ind["EMA9"] and ind["EMA20"]:
        ind["EMA_spread"] = round(ind["EMA9"] - ind["EMA20"], 6)
        ind["EMA_state"] = "BULLISH" if ind["EMA9"] > ind["EMA20"] else "BEARISH"
    if "ATR" in indicators or True:
        highs = np.array([r["high"] for r in rows_all], float)
        lows = np.array([r["low"] for r in rows_all], float)
        if len(closes) >= 15:
            tr = np.maximum(highs[1:] - lows[1:],
                            np.maximum(np.abs(highs[1:] - closes[:-1]),
                                       np.abs(lows[1:] - closes[:-1])))
            ind["ATR14_agg"] = round(float(tr[-14:].mean()), 6)
    out["indicators"] = ind
    if volume_flow:
        out["volume_flow"] = get_trade_flow(symbol, lookback_min)
    if volume_profile:
        out["volume_profile"] = get_volume_profile(symbol, lookback_min)
    if order_book:
        out["order_book"] = get_order_book(symbol)
    return out


def get_trade_flow(symbol: str, lookback_min=30):
    now = int(time.time() * 1000)
    rows = db.query_candles(symbol, now - lookback_min * 60_000, now,
                            exchange="BINANCE")
    if not rows:
        return {"error": "flow unavailable: no Binance 1m data (flow methodology "
                         "requires taker-buy volumes)", "total": None}
    total = sum(r["volume"] or 0 for r in rows)
    inflow = sum(r["taker_buy"] or 0 for r in rows)
    outflow = total - inflow
    return {"methodology": "inflow=taker_buy_volume(Binance); outflow=total-inflow "
                           "(aggressive-buy vs aggressive-sell approximation)",
            "window_min": lookback_min, "total": round(total, 4),
            "inflow": round(inflow, 4), "outflow": round(outflow, 4),
            "net_flow": round(inflow - outflow, 4),
            "net_flow_pct": round((inflow - outflow) / total * 100, 2) if total else None}


def get_volume_profile(symbol: str, lookback_min=60, bucket_count=24):
    now = int(time.time() * 1000)
    rows = db.query_candles(symbol, now - lookback_min * 60_000, now)
    if len(rows) < 5:
        return {"error": "insufficient data"}
    hi = max(r["high"] for r in rows); lo = min(r["low"] for r in rows)
    if hi <= lo:
        return {"error": "degenerate range"}
    step = (hi - lo) / bucket_count
    buckets = [0.0] * bucket_count
    for r in rows:
        rng = r["high"] - r["low"]
        if rng <= 0:
            idx = min(bucket_count - 1, int((r["close"] - lo) / step))
            buckets[idx] += r["volume"] or 0
            continue
        # allocate volume uniformly across touched buckets (documented method)
        first = int((r["low"] - lo) / step); lastx = int((r["high"] - lo) / step)
        first = max(0, min(first, bucket_count - 1))
        lastx = max(0, min(lastx, bucket_count - 1))
        per = (r["volume"] or 0) / (lastx - first + 1)
        for bidx in range(first, lastx + 1):
            buckets[bidx] += per
    poc_i = int(np.argmax(buckets))
    poc_price = lo + (poc_i + 0.5) * step
    total = sum(buckets)
    # value area: expand from POC until >=70% volume
    va = {poc_i}; acc = buckets[poc_i]
    lo_i, hi_i = poc_i, poc_i
    while acc < 0.7 * total and (lo_i > 0 or hi_i < bucket_count - 1):
        nxt_l = buckets[lo_i - 1] if lo_i > 0 else -1
        nxt_h = buckets[hi_i + 1] if hi_i < bucket_count - 1 else -1
        if nxt_h >= nxt_l:
            hi_i += 1; acc += max(nxt_h, 0); va.add(hi_i)
        else:
            lo_i -= 1; acc += max(nxt_l, 0); va.add(lo_i)
    return {"window_min": lookback_min, "bucket_size": round(step, 6),
            "POC": round(poc_price, 6),
            "VAH": round(lo + (hi_i + 1) * step, 6),
            "VAL": round(lo + lo_i * step, 6),
            "buckets": [{"price_lo": round(lo + i * step, 6),
                         "volume": round(v, 3)} for i, v in enumerate(buckets)]}


BOOK_CACHE: dict = {"ts": 0, "data": None}


def get_order_book(symbol: str, top_n: int = 10):
    import urllib.request
    now = time.time()
    if BOOK_CACHE["data"] and now - BOOK_CACHE["ts"] < 3:
        return BOOK_CACHE["data"]
    sym = symbol.replace("_USDT", "-USDT") if "_" in symbol else symbol
    url = (f"https://open-api.bingx.com/openApi/swap/v2/quote/depth?"
           f"symbol={sym}&limit=20")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ophelia-cp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read().decode())
        d = body.get("data") or {}
        bids = [(float(p), float(q)) for p, q in (d.get("bids") or [])[:top_n]]
        asks = [(float(p), float(q)) for p, q in (d.get("asks") or [])[:top_n]]
        if not bids or not asks:
            return {"error": "empty order book"}
        bb, ba = bids[0][0], asks[0][0]
        bv = sum(q for _, q in bids); av = sum(q for _, q in asks)
        out = {"best_bid": bb, "best_ask": ba,
               "spread": round(ba - bb, 8),
               "spread_bps": round((ba - bb) / ((ba + bb) / 2) * 1e4, 2),
               "bid_vol_top": round(bv, 4), "ask_vol_top": round(av, 4),
               "imbalance_pct": round((bv - av) / (bv + av) * 100, 2),
               "levels_returned": min(top_n, len(bids), len(asks))}
        BOOK_CACHE.update(ts=now, data=out)
        return out
    except Exception as e:                                        # noqa: BLE001
        return {"error": f"order book unavailable: {str(e)[:120]}"}


def movement_stats(symbol: str, lookback_min=15, agg_interval_min=None):
    cd = get_candles(symbol, lookback_min, 1, agg_interval_min)
    if "error" in cd:
        return cd
    rows = cd["candles"]
    if len(rows) < 2:
        return {"error": "insufficient candles"}
    moves = [abs(r["close"] - rows[i]["close"]) / rows[i]["close"] * 100
             for i, r in enumerate(rows[1:], 1)]
    net = (rows[-1]["close"] / rows[0]["open"] - 1) * 100
    rng = (max(r["high"] for r in rows) - min(r["low"] for r in rows)) \
        / rows[0]["open"] * 100
    return {"window_min": lookback_min, "avg_abs_move_pct": round(float(np.mean(moves)), 4),
            "max_abs_move_pct": round(float(np.max(moves)), 4),
            "net_move_pct": round(net, 4), "range_pct": round(rng, 4),
            "direction": "UP" if net > 0 else ("DOWN" if net < 0 else "FLAT")}


def ema_crossover_estimate(symbol: str, tf_min=5):
    """ESTIMATE ONLY: bars until EMA9/20 cross under constant-price-drift assumption."""
    cd = get_candles(symbol, max(240, tf_min * 60), 1, tf_min)
    if "error" in cd or cd["count"] < 30:
        return {"estimate": None,
                "note": "insufficient data", "type": "ESTIMATE"}
    closes = np.array([r["close"] for r in cd["candles"]], float)
    e9 = ema(closes, 9); e20 = ema(closes, 20)
    d = e9[-1] - e20[-1]
    dp = e9[-2] - e20[-2]
    vel = d - dp                                  # spread velocity per bar
    state = "BULLISH" if d > 0 else "BEARISH"
    if abs(vel) < 1e-12:
        return {"estimate_bars": None, "state": state, "spread": round(d, 6),
                "note": "spread velocity ~0; crossover not imminent on recent slope",
                "type": "ESTIMATE"}
    bars = -d / vel if (d > 0 and vel < 0) or (d < 0 and vel > 0) else None
    out = {"state": state, "spread_now": round(d, 6),
           "spread_velocity_per_bar": round(vel, 6),
           "assumption": "linear extrapolation of last-bar spread change; ESTIMATE NOT GUARANTEE",
           "type": "ESTIMATE"}
    out["estimate_bars"] = (round(abs(bars), 1) if bars is not None and 0 < bars < 500
                            else None)
    if out["estimate_bars"]:
        out["estimate_minutes"] = out["estimate_bars"] * tf_min
        out["would_cross_to"] = "BEARISH" if (d > 0) else "BULLISH"
    return out


def get_structured_volume_telemetry(symbol: str, tf_min: int = 5) -> dict:
    """Calculates distinct, verified volume telemetry:
      - current_candle_volume: USDT notional of CURRENT (incomplete) tf_min candle
      - current_candle_base_volume: base asset quantity of CURRENT tf_min candle
      - timeframe_volume: USDT notional of latest COMPLETED tf_min candle
      - timeframe_base_volume: base asset quantity of latest COMPLETED tf_min candle
      - rolling_volume_1h: confirmed rolling 60m USDT notional volume
      - rolling_base_volume_1h: confirmed rolling 60m base asset volume
      - volume_24h: true confirmed 24h (1440m) cumulative USDT notional volume
      - volume_24h_base: true confirmed 24h (1440m) base asset volume
      - session_volume: USDT notional volume accumulated since 00:00 UTC
      - session_base_volume: base asset volume accumulated since 00:00 UTC
      - rvol: relative volume ratio vs 20-period baseline of completed tf_min candles
    """
    now = int(time.time() * 1000)
    now_dt = datetime.fromtimestamp(now / 1000, timezone.utc)
    session_start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    session_start_ms = int(session_start_dt.timestamp() * 1000)

    base_asset = symbol.split("-")[0].replace("NCCOGOLD2USD", "GOLD").replace("XAU", "GOLD")
    if "GOLD" in symbol.upper() or "XAU" in symbol.upper():
        base_asset = "GOLD"

    raw = db.query_candles(symbol, now - (1440 * 60_000), now)
    if not raw:
        return {
            "current_candle_volume": 0.0,
            "current_candle_base_volume": 0.0,
            "current_candle_label": f"CURRENT {tf_min}m CANDLE",
            "is_current_candle_complete": False,
            "timeframe_volume": 0.0,
            "timeframe_base_volume": 0.0,
            "rolling_volume_1h": 0.0,
            "rolling_base_volume_1h": 0.0,
            "volume_24h": 0.0,
            "volume_24h_base": 0.0,
            "session_volume": 0.0,
            "session_base_volume": 0.0,
            "rvol": 1.0,
            "timeframe_min": tf_min,
            "unit": "USDT",
            "base_asset": base_asset,
            "timestamp_ms": now,
        }

    raw1m = sorted(raw, key=lambda x: x["ts"])
    
    # If the latest candle is older than 10 minutes (historical/offline), anchor to latest candle ts
    latest_ts = raw1m[-1]["ts"] if raw1m else now
    anchor_ms = now if (now - latest_ts) < (10 * 60_000) else latest_ts

    # 1. Rolling 24h (1440m window)
    cutoff_24h = anchor_ms - (1440 * 60_000)
    r24h_bars = [r for r in raw1m if r["ts"] >= cutoff_24h]
    vol_24h_base = sum(float(r.get("volume") or 0.0) for r in r24h_bars)
    vol_24h_usdt = sum(float(r.get("volume") or 0.0) * float(r.get("close") or 0.0) for r in r24h_bars)

    # 2. Rolling 1h (60m window of 1m bars)
    cutoff_1h = anchor_ms - (60 * 60_000)
    r1h_bars = [r for r in raw1m if r["ts"] >= cutoff_1h]
    vol_1h_base = sum(float(r.get("volume") or 0.0) for r in r1h_bars)
    vol_1h_usdt = sum(float(r.get("volume") or 0.0) * float(r.get("close") or 0.0) for r in r1h_bars)

    # 3. Session Volume (since 00:00 UTC)
    anchor_dt = datetime.fromtimestamp(anchor_ms / 1000, timezone.utc)
    session_start_dt = anchor_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    session_start_ms = int(session_start_dt.timestamp() * 1000)
    sess_bars = [r for r in raw1m if r["ts"] >= session_start_ms]
    vol_session_base = sum(float(r.get("volume") or 0.0) for r in sess_bars)
    vol_session_usdt = sum(float(r.get("volume") or 0.0) * float(r.get("close") or 0.0) for r in sess_bars)

    # 4. Current (Incomplete) tf_min Candle vs Timeframe (Completed) Candle
    tf_ms = tf_min * 60_000
    cur_candle_start = (anchor_ms // tf_ms) * tf_ms
    prev_candle_start = cur_candle_start - tf_ms

    cur_bars = [r for r in raw1m if r["ts"] >= cur_candle_start]
    cur_vol_base = sum(float(r.get("volume") or 0.0) for r in cur_bars)
    cur_vol_usdt = sum(float(r.get("volume") or 0.0) * float(r.get("close") or 0.0) for r in cur_bars)

    prev_bars = [r for r in raw1m if prev_candle_start <= r["ts"] < cur_candle_start]
    if prev_bars:
        tf_vol_base = sum(float(r.get("volume") or 0.0) for r in prev_bars)
        tf_vol_usdt = sum(float(r.get("volume") or 0.0) * float(r.get("close") or 0.0) for r in prev_bars)
    else:
        agg_closed = aggregate(raw1m, tf_min, closed_only=True)
        if agg_closed:
            tf_vol_base = float(agg_closed[-1].get("volume") or 0.0)
            tf_vol_usdt = tf_vol_base * float(agg_closed[-1].get("close") or 0.0)
        else:
            tf_vol_base = cur_vol_base
            tf_vol_usdt = cur_vol_usdt

    # 5. RVOL (20-period baseline of completed bars)
    agg_bars = aggregate(raw1m, tf_min, closed_only=True)
    if agg_bars:
        vols_usdt = [float(b.get("volume") or 0.0) * float(b.get("close") or 0.0) for b in agg_bars]
        rvol_val = fast_math.calculate_rvol(vols_usdt, 20)
    else:
        rvol_val = 1.0

    return {
        "current_candle_volume": round(cur_vol_usdt, 2),
        "current_candle_base_volume": round(cur_vol_base, 4),
        "current_candle_label": f"CURRENT {tf_min}m CANDLE",
        "is_current_candle_complete": False,
        "timeframe_volume": round(tf_vol_usdt, 2),
        "timeframe_base_volume": round(tf_vol_base, 4),
        "rolling_volume_1h": round(vol_1h_usdt, 2),
        "rolling_base_volume_1h": round(vol_1h_base, 4),
        "volume_24h": round(vol_24h_usdt, 2),
        "volume_24h_base": round(vol_24h_base, 4),
        "session_volume": round(vol_session_usdt, 2),
        "session_base_volume": round(vol_session_base, 4),
        "rvol": round(rvol_val, 2),
        "timeframe_min": tf_min,
        "unit": "USDT",
        "base_asset": base_asset,
        "timestamp_ms": now,
    }

