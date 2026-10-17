"""ADAPTIVE EMA 1M/5M EXPERIMENT - standalone hypothesis test (XRPUSDT, 1 month).

Core question: does 1m EMA9/20 work better inside 5m RANGE conditions while
5m EMA9/20 is used during 5m MOMENTUM?

Documented interpretations (required by the spec's ambiguity clauses):
  I-1 entry : crossover confirmed at candle CLOSE -> entry NEXT candle OPEN.
              (literal "open of crossover candle" is look-ahead; impossible causally)
  I-2 stop  : STATIC stop = OPEN of the most recent PAST opposite-direction crossover
              candle (known at entry). The literal future-reversal-open stop is
              retroactive; its causal analogue is the REVERSAL EXIT:
              opposite cross confirmed at close U -> exit at open[U+1].
  I-3 regime: computed on 5m bars; AvgMove20 percentile replaced by CAUSAL rolling
              median (288x5m = 1 day) - a full-month percentile would look ahead.
  F-1 fairness: ALL systems execute on the SAME 1m stream (same fills, same
              stop-first ambiguity); only the signal timeframe differs.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SYMBOL = "XRPUSDT"
TF_MS = 60_000
DATA_CSV = os.path.join(HERE, "xrpusdt_1m_2026_07.csv")
START_MS = 1_782_864_000_000          # 2026-07-01 00:00 UTC (bugfix: was Jul 2)
END_MS_EXCL = 1_785_542_400_000       # 2026-08-01 00:00 UTC
POLICIES = (1.0, 2.0, 3.0)


# ------------------------------------------------------------------ data

def http_get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-ema/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(min(2.0 * (i + 1), 15.0))
    raise RuntimeError(f"fetch failed: {last}")


def fetch_1m() -> pd.DataFrame:
    if os.path.exists(DATA_CSV):
        df = pd.read_csv(DATA_CSV)
        df["candle_open_time"] = df["candle_open_time"].astype("int64")
        return df.sort_values("candle_open_time").reset_index(drop=True)
    rows, t = [], START_MS
    while t < END_MS_EXCL:
        kl = http_get(f"https://fapi.binance.com/fapi/v1/klines?symbol={SYMBOL}"
                      f"&interval=1m&startTime={t}&endTime={END_MS_EXCL - 1}&limit=1500")
        if not kl:
            break
        for k in kl:
            rows.append({"candle_open_time": int(k[0]), "open": float(k[1]),
                         "high": float(k[2]), "low": float(k[3]),
                         "close": float(k[4]), "volume": float(k[5])})
        nxt = int(kl[-1][0]) + TF_MS
        if nxt <= t:
            break
        t = nxt
        time.sleep(0.12)
    df = pd.DataFrame(rows).drop_duplicates("candle_open_time").sort_values("candle_open_time")
    df = df.reset_index(drop=True)
    df.to_csv(DATA_CSV, index=False)
    return df


def aggregate_5m(df1: pd.DataFrame) -> pd.DataFrame:
    # NOTE (bugfix 2026-08-22): previous version multiplied already-ms timestamps by
    # 300_000, corrupting all 5m timestamps -> 5m systems silently produced 0 trades.
    k = df1["candle_open_time"] // 300_000
    a = df1.groupby(k, as_index=False).agg(
        candle_open_time=("candle_open_time", "first"),
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"))
    return a.sort_values("candle_open_time").reset_index(drop=True)


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


def wilder_atr(h, l, c, n):
    tr = np.empty(len(c))
    tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - pc), np.abs(l[1:] - pc)])
    atr = np.full(len(c), np.nan)
    if len(c) < n:
        return atr
    atr[n - 1] = tr[:n].mean()
    for i in range(n, len(c)):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def regime_series(df5: pd.DataFrame):
    """Causal 5m regime per bar: RANGE / MOMENTUM / TRANSITION (raw states, no tuning)."""
    c = df5["close"].to_numpy(float)
    h = df5["high"].to_numpy(float)
    l = df5["low"].to_numpy(float)
    dm = np.abs(np.diff(c, prepend=c[0]))
    dm[0] = 0.0
    avg_move = pd.Series(dm).rolling(20, min_periods=20).mean().to_numpy()
    net = np.abs(pd.Series(c).shift(20).to_numpy() - c)
    path = pd.Series(dm).rolling(20, min_periods=20).sum().to_numpy()
    er = np.where(path > 0, net / np.where(path == 0, np.nan, path), np.nan)
    vr = wilder_atr(h, l, c, 20) / wilder_atr(h, l, c, 100)
    med = pd.Series(avg_move).rolling(288, min_periods=288).median().to_numpy()
    reg = np.full(len(c), "UNDEFINED", dtype=object)
    defined = ~np.isnan(med) & ~np.isnan(er)
    reg[defined & ((avg_move < med) & (er < 0.20))] = "RANGE"
    reg[defined & ((avg_move >= med) & (er > 0.35))] = "MOMENTUM"
    reg[defined & ~(  ((avg_move < med) & (er < 0.20)) | ((avg_move >= med) & (er > 0.35)) )] = "TRANSITION"
    return reg, avg_move, er, vr


# ------------------------------------------------------------------ simulation

def run_system(sysname, sig_tf, up_idx, dn_idx, up_open_map, dn_open_map,
               o1, h1, l1, c1, TIME, reg_at_1m, mode):
    n = len(TIME)
    trades, skips = [], {"no_stop_ref": 0, "regime_block": 0, "degenerate_r": 0}
    last_up = last_dn = None
    pending = None
    pos = None

    def finalize(p, exit_idx, exit_px, reason):
        d = p["direction"]
        for k in POLICIES:                       # fill remaining policies w/ this exit
            p["pol_exit"].setdefault(k, (exit_idx, exit_px, reason))
        rec = {"system": sysname, "signal_tf": p["sig_tf"],
               "direction": "LONG" if d == 1 else "SHORT",
               "entry_time_ms": int(TIME[p["entry_idx"]]),
               "entry_price": p["entry_px"], "stop_price": p["stop"],
               "R_price": p["R"], "regime_at_entry": p["regime"]}
        for k in POLICIES:
            ei, ep, rs = p["pol_exit"][k]
            rr = d * (ep / p["entry_px"] - 1.0) / p["Rfrac"]
            rec[f"exit{k}_time_ms"] = int(TIME[ei])
            rec[f"exit{k}_price"] = ep
            rec[f"exit{k}_reason"] = rs
            rec[f"R{k}"] = rr
        trades.append(rec)

    for i in range(1, n):
        # 1) pending entry fills at this open
        if pending and pos is None:
            d = pending["direction"]
            entry = o1[i]
            R = abs(entry - pending["stop"])
            Rf = R / entry
            if R <= 0 or Rf > 0.05:
                skips["degenerate_r"] += 1
            else:
                pos = {"direction": d, "entry_idx": i, "entry_px": entry,
                       "stop": pending["stop"], "R": R, "Rfrac": Rf,
                       "sig_tf": pending["sig_tf"], "regime": pending["regime"],
                       "pol_exit": {}}
            pending = None
        # 2) intrabar exits (entry bar included): gap rules then STOP-FIRST tie
        if pos is not None:
            d = pos["direction"]
            op, hi, lo = o1[i], h1[i], l1[i]
            gap_stop = (op <= pos["stop"]) if d == 1 else (op >= pos["stop"])
            stop_hit = (lo <= pos["stop"]) if d == 1 else (hi >= pos["stop"])
            for k in POLICIES:
                if k in pos["pol_exit"]:
                    continue
                tgt = pos["entry_px"] + d * k * pos["R"]
                gap_tgt = (op >= tgt) if d == 1 else (op <= tgt)
                tgt_hit = (hi >= tgt) if d == 1 else (lo <= tgt)
                if gap_stop:
                    pos["pol_exit"][k] = (i, op, "STOP")
                elif gap_tgt and i != pos["entry_idx"]:
                    pos["pol_exit"][k] = (i, op, "TARGET")
                elif stop_hit and tgt_hit:
                    pos["pol_exit"][k] = (i, pos["stop"], "STOP")     # A1 STOP FIRST
                elif stop_hit:
                    pos["pol_exit"][k] = (i, pos["stop"], "STOP")
                elif tgt_hit:
                    pos["pol_exit"][k] = (i, tgt, "TARGET")
            if len(pos["pol_exit"]) == len(POLICIES):
                ei, ep, rs = pos["pol_exit"][POLICIES[0]]
                finalize(pos, ei, ep, rs)
                pos = None
        # 3) reversal exit: opposite cross CONFIRMS at this close -> exit next open
        if pos is not None:
            d = pos["direction"]
            rev = (i in dn_idx) if d == 1 else (i in up_idx)
            if rev and i + 1 < n:
                finalize(pos, i + 1, o1[i + 1], "REVERSAL")
                pos = None
        # 4) new crossover events confirmed at this close
        for ev_dir in (+1, -1):
            ev_set = up_idx if ev_dir == 1 else dn_idx
            if i not in ev_set:
                continue
            if ev_dir == 1:
                last_up = o1[i] if sig_tf == "1m" else up_open_map.get(i, last_up)
            else:
                last_dn = o1[i] if sig_tf == "1m" else dn_open_map.get(i, last_dn)
            if pos is not None or pending is not None:
                continue
            stop_ref = last_dn if ev_dir == 1 else last_up
            if stop_ref is None:
                skips["no_stop_ref"] += 1
                continue
            if mode == "ADAPTIVE":
                want = "RANGE" if sig_tf == "1m" else "MOMENTUM"
                if reg_at_1m[i] != want:
                    skips["regime_block"] += 1
                    continue
            pending = {"direction": ev_dir, "stop": stop_ref, "sig_tf": sig_tf,
                       "regime": reg_at_1m[i]}
    if pos is not None:
        finalize(pos, n - 1, c1[-1], "EOD")
    return trades, skips


# ------------------------------------------------------------------ stats

def stats_block(trades):
    if not trades:
        return {"trades": 0, "long": 0, "short": 0}
    df = pd.DataFrame(trades)
    out = {"trades": int(len(df)),
           "long": int((df["direction"] == "LONG").sum()),
           "short": int((df["direction"] == "SHORT").sum())}
    for k in POLICIES:
        rr = df[f"R{k}"].to_numpy(float)
        wins = (df[f"exit{k}_reason"] == "TARGET").to_numpy()
        losses = (df[f"exit{k}_reason"] == "STOP").to_numpy()
        rf = (df["R_price"] / df["entry_price"]).to_numpy(float)
        cost_R = 10.0 * 1e-4 / rf                     # 10bp round trip expressed in R
        out[f"wr_{k}"] = float(wins.mean())
        out[f"lossrate_{k}"] = float(losses.mean())
        out[f"meanR_{k}"] = float(rr.mean())
        out[f"medianR_{k}"] = float(np.median(rr))
        out[f"net_meanR_{k}@10bp"] = float(np.mean(rr - cost_R))
    return out


# ------------------------------------------------------------------ main

def main() -> int:
    df1 = fetch_1m()
    TIME = df1["candle_open_time"].to_numpy(np.int64)
    o1 = df1["open"].to_numpy(float)
    h1 = df1["high"].to_numpy(float)
    l1 = df1["low"].to_numpy(float)
    c1 = df1["close"].to_numpy(float)
    df5 = aggregate_5m(df1)
    print(f"data: {len(df1)} 1m | {len(df5)} 5m | "
          f"{datetime.fromtimestamp(int(TIME[0]) / 1000, timezone.utc):%Y-%m-%d %H:%M} -> "
          f"{datetime.fromtimestamp(int(TIME[-1]) / 1000, timezone.utc):%Y-%m-%d %H:%M} UTC")

    e9_1, e20_1 = ema(c1, 9), ema(c1, 20)
    e9_5, e20_5 = ema(df5["close"].to_numpy(float), 9), ema(df5["close"].to_numpy(float), 20)

    def crosses(e9, e20):
        up, dn = [], []
        for i in range(1, len(e9)):
            if np.isnan(e9[i]) or np.isnan(e20[i]) or np.isnan(e9[i - 1]) or np.isnan(e20[i - 1]):
                continue
            if e9[i - 1] <= e20[i - 1] and e9[i] > e20[i]:
                up.append(i)
            elif e9[i - 1] >= e20[i - 1] and e9[i] < e20[i]:
                dn.append(i)
        return up, dn

    up1, dn1 = crosses(e9_1, e20_1)
    up5, dn5 = crosses(e9_5, e20_5)

    # map 5m confirmation closes & opens into 1m index space
    close5_ms = df5["candle_open_time"].to_numpy(np.int64) + 300_000
    idx_of = {int(t): i for i, t in enumerate(TIME)}
    o5 = df5["open"].to_numpy(float)
    up5_1m = sorted(idx_of[int(close5_ms[i])] for i in up5 if int(close5_ms[i]) in idx_of)
    dn5_1m = sorted(idx_of[int(close5_ms[i])] for i in dn5 if int(close5_ms[i]) in idx_of)
    up5_open = {idx_of[int(close5_ms[i])]: o5[i] for i in up5 if int(close5_ms[i]) in idx_of}
    dn5_open = {idx_of[int(close5_ms[i])]: o5[i] for i in dn5 if int(close5_ms[i]) in idx_of}

    reg5, avg_move, er5, vr5 = regime_series(df5)
    reg_at_1m = np.full(len(TIME), "UNDEFINED", dtype=object)
    j = -1
    for i, t in enumerate(TIME):
        while j + 1 < len(close5_ms) and int(close5_ms[j + 1]) <= int(t):
            j += 1
        if j >= 0:
            reg_at_1m[i] = reg5[j]

    t_5m, s_5m = run_system("5M_ONLY", "5m", up5_1m, dn5_1m, up5_open, dn5_open,
                            o1, h1, l1, c1, TIME, reg_at_1m, "FIXED")
    up1o = {i: o1[i] for i in up1}
    dn1o = {i: o1[i] for i in dn1}
    t_1m, s_1m = run_system("1M_ONLY", "1m", up1, dn1, up1o, dn1o,
                            o1, h1, l1, c1, TIME, reg_at_1m, "FIXED")
    t_a1, s_a1 = run_system("ADAPTIVE", "1m", up1, dn1, up1o, dn1o,
                            o1, h1, l1, c1, TIME, reg_at_1m, "ADAPTIVE")
    t_a5, s_a5 = run_system("ADAPTIVE", "5m", up5_1m, dn5_1m, up5_open, dn5_open,
                            o1, h1, l1, c1, TIME, reg_at_1m, "ADAPTIVE")
    t_ad = t_a1 + t_a5

    all_trades = pd.DataFrame(t_5m + t_1m + t_ad)
    all_trades.to_csv(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_ALL_TRADES.csv"), index=False)

    comparison = []
    for nm, tl, sk in (("5M_ONLY", t_5m, s_5m), ("1M_ONLY", t_1m, s_1m),
                       ("ADAPTIVE", t_ad, {k: s_a1[k] + s_a5[k] for k in s_a1})):
        comparison.append({"system": nm, **stats_block(tl),
                           "skipped_no_stop_ref": sk["no_stop_ref"],
                           "skipped_regime_block": sk["regime_block"],
                           "skipped_degenerate_r": sk["degenerate_r"]})
    cmp_df = pd.DataFrame(comparison)
    cmp_df.to_csv(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_COMPARISON.csv"), index=False)

    def regime_rows(nm, tl):
        df = pd.DataFrame(tl) if tl else pd.DataFrame(
            columns=["regime_at_entry", "exit1.0_reason", "R1.0",
                     "exit2.0_reason", "R2.0", "exit3.0_reason", "R3.0"])
        out = []
        for reg in ("RANGE", "MOMENTUM", "TRANSITION", "UNDEFINED"):
            g = df[df["regime_at_entry"] == reg]
            row = {"system": nm, "regime": reg, "trades": int(len(g))}
            for k in POLICIES:
                row[f"wr_{k}"] = float((g[f"exit{k}_reason"] == "TARGET").mean()) if len(g) else None
                row[f"meanR_{k}"] = float(g[f"R{k}"].mean()) if len(g) else None
            out.append(row)
        return out

    regime_results = []
    diag_rows = []
    for nm, tl in (("5M_ONLY", t_5m), ("1M_ONLY", t_1m), ("ADAPTIVE", t_ad)):
        regime_results += regime_rows(nm, tl)
    rr = pd.DataFrame(regime_results)
    rr.to_csv(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_REGIME_RESULTS.csv"), index=False)
    # §17 direct diagnostic: fixed systems' performance inside each regime
    for nm, tl in (("1M_ONLY", t_1m), ("5M_ONLY", t_5m)):
        df = pd.DataFrame(tl) if tl else None
        for reg in ("RANGE", "MOMENTUM", "TRANSITION"):
            g = df[df["regime_at_entry"] == reg] if df is not None else df
            row = {"system": nm, "regime": reg, "trades": int(len(g)) if g is not None else 0}
            for k in POLICIES:
                row[f"wr_{k}"] = float((g[f"exit{k}_reason"] == "TARGET").mean()) \
                    if g is not None and len(g) else None
                row[f"meanR_{k}"] = float(g[f"R{k}"].mean()) \
                    if g is not None and len(g) else None
            diag_rows.append(row)
    pd.DataFrame(diag_rows).to_csv(
        os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_DIAGNOSTIC.csv"), index=False)
    pd.DataFrame(diag_rows).to_csv(
        os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_DIAGNOSTIC.csv"), index=False)

    dist = {r: round(float((reg5 == r).mean() * 100), 2) for r in
            ("RANGE", "MOMENTUM", "TRANSITION", "UNDEFINED")}
    switches = int((reg5[1:] != reg5[:-1]).sum() +
                   (reg5[0] != "UNDEFINED"))  # count real state changes incl. first define

    results = {
        "meta": {
            "symbol": SYMBOL,
            "venue": "Binance USD-M perpetual (1m source; 5m aggregated from same feed)",
            "window_utc": "2026-07-01 00:00 -> 2026-07-31 23:59",
            "bars_1m": int(len(df1)), "bars_5m": int(len(df5)),
            "regime_distribution_pct_5m_bars": dist,
            "regime_switches_5m": switches,
            "interpretations": ["I-1 entry next-open after close confirmation",
                                "I-2 static stop = prior opposite cross OPEN; reversal exit = open after opposite cross confirm",
                                "I-3 causal rolling median(288) replaces full-month percentile",
                                "F-1 all systems execute on the same 1m stream"],
        },
        "comparison": comparison,
        "regime_by_system": regime_results,
        "diagnostic_system_x_regime": diag_rows,
        "signals": {"crosses_1m": len(up1) + len(dn1),
                    "crosses_5m": len(up5) + len(dn5)},
    }
    with open(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_RESULTS.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
        f.write("\n")

    show = cmp_df[[c for c in cmp_df.columns if not c.startswith("net_meanR")]]
    print(show.to_string(index=False))
    print("\nregime dist %:", dist, "| switches:", switches)
    print(pd.DataFrame(diag_rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
