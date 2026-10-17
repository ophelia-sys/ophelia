"""LONG-HISTORY extension of the FROZEN Adaptive EMA 1m/5m experiment.

Reuses research.experiments.ADAPTIVE_EMA_1M_5M.exp_adaptive_ema_1m_5m (X.*) verbatim:
same EMAs, same regime features/thresholds, same causal interpretations,
same stop/target/reversal accounting, same STOP-FIRST ambiguity.

Additions here are REPORTING ONLY: month-chunked resumable download,
quarterly walk-forward tables, classifier health (switches/day, state durations),
max losing streak / max drawdown.
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
sys.path.insert(0, os.path.join(HERE))          # sibling experiment folder
XDIR = os.path.abspath(os.path.join(HERE))
if XDIR not in sys.path:
    sys.path.insert(0, XDIR)

import exp_adaptive_ema_1m_5m as X              # noqa: E402  (frozen rules module)
from exp_adaptive_ema_1m_5m import (            # noqa: E402
    POLICIES, aggregate_5m, ema, regime_series, wilder_atr, stats_block)

SYMBOL = "XRPUSDT"
TF_MS = 60_000
START_MS = 1_725_148_800_000          # 2024-09-01 00:00:00 UTC
END_MS_EXCL = 1_785_542_400_000       # 2026-08-01 00:00:00 UTC
CACHE_DIR = os.path.join(HERE, "cache_1m")


def http_get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-emalong/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(min(2.0 * (i + 1), 15.0))
    raise RuntimeError(f"fetch failed: {last}")


def month_bounds(start_ms, end_ms_excl):
    cur = start_ms
    while cur < end_ms_excl:
        dt = datetime.fromtimestamp(cur / 1000, timezone.utc)
        ny, nm = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
        nxt = int(datetime(ny, nm, 1, tzinfo=timezone.utc).timestamp() * 1000)
        yield cur, min(nxt, end_ms_excl)
        cur = nxt


def fetch_month(a_ms, b_ms_excl) -> pd.DataFrame:
    os.makedirs(CACHE_DIR, exist_ok=True)
    tag = datetime.fromtimestamp(a_ms / 1000, timezone.utc).strftime("%Y%m")
    path = os.path.join(CACHE_DIR, f"xrp_1m_{tag}.csv")
    if os.path.exists(path):
        df = pd.read_csv(path)
        df["candle_open_time"] = df["candle_open_time"].astype("int64")
        return df
    rows, t = [], a_ms
    while t < b_ms_excl:
        kl = http_get(f"https://fapi.binance.com/fapi/v1/klines?symbol={SYMBOL}"
                      f"&interval=1m&startTime={t}&endTime={b_ms_excl - 1}&limit=1500")
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
        time.sleep(0.10)
    df = pd.DataFrame(rows).drop_duplicates("candle_open_time").sort_values("candle_open_time")
    df.reset_index(drop=True).to_csv(path, index=False)
    print(f"  cached {tag}: {len(df)} bars", flush=True)
    return df


def load_all() -> pd.DataFrame:
    parts = [fetch_month(a, b) for a, b in month_bounds(START_MS, END_MS_EXCL)]
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates("candle_open_time").sort_values("candle_open_time").reset_index(drop=True)
    # drop any stragglers outside window
    df = df[(df.candle_open_time >= START_MS) & (df.candle_open_time < END_MS_EXCL)]
    return df


def max_streak_dd(net: np.ndarray):
    eq = np.cumsum(net)
    dd = float(np.min(eq - np.maximum.accumulate(eq))) if len(eq) else None
    best = cur = 0
    for x in (net <= 0):
        cur = cur + 1 if x else 0
        best = max(best, cur)
    return best, dd


def main() -> int:
    t0 = time.time()
    df1 = load_all()
    TIME = df1["candle_open_time"].to_numpy(np.int64)
    o1 = df1["open"].to_numpy(float); h1 = df1["high"].to_numpy(float)
    l1 = df1["low"].to_numpy(float); c1 = df1["close"].to_numpy(float)
    df5 = aggregate_5m(df1)
    span_days = (TIME[-1] - TIME[0]) / 86_400_000
    print(f"data: {len(df1)} 1m | {len(df5)} 5m | {span_days:.0f} days | "
          f"{datetime.fromtimestamp(int(TIME[0])/1000, timezone.utc):%Y-%m-%d} -> "
          f"{datetime.fromtimestamp(int(TIME[-1])/1000, timezone.utc):%Y-%m-%d} | "
          f"{time.time()-t0:.0f}s", flush=True)

    e9_1, e20_1 = ema(c1, 9), ema(c1, 20)
    c5 = df5["close"].to_numpy(float)
    e9_5, e20_5 = ema(c5, 9), ema(c5, 20)

    def crosses(e9, e20):
        up, dn = [], []
        prev_ok = False
        diff = e9 - e20
        for i in range(1, len(e9)):
            d0, d1 = diff[i - 1], diff[i]
            if np.isnan(d0) or np.isnan(d1):
                continue
            if d0 <= 0 and d1 > 0:
                up.append(i)
            elif d0 >= 0 and d1 < 0:
                dn.append(i)
        return up, dn

    up1, dn1 = crosses(e9_1, e20_1)
    up5, dn5 = crosses(e9_5, e20_5)
    print(f"crosses: 1m={len(up1)+len(dn1)} 5m={len(up5)+len(dn5)}", flush=True)

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

    # ---- classifier health -------------------------------------------------
    defined5 = reg5[reg5 != "UNDEFINED"]
    code_map = {"RANGE": 0, "MOMENTUM": 1, "TRANSITION": 2}
    codes = pd.Series(defined5).map(code_map).to_numpy()
    changes = np.where(np.diff(codes) != 0)[0] + 1
    n_switch = int(len(changes))
    days_span = span_days
    switch_per_day = n_switch / days_span
    # state durations in 5m bars
    bounds = np.concatenate(([0], changes, [len(defined5)]))
    durs = np.diff(bounds)
    dur_by_state = {}
    for s in ("RANGE", "MOMENTUM", "TRANSITION"):
        mask = defined5[bounds[:-1]] == s
        d_s = durs[mask]
        dur_by_state[s] = {"count": int(mask.sum()),
                           "median_bars": float(np.median(d_s)) if len(d_s) else None,
                           "median_minutes": float(np.median(d_s) * 5) if len(d_s) else None}
    dist = {r: round(float((reg5 == r).mean() * 100), 2) for r in
            ("RANGE", "MOMENTUM", "TRANSITION", "UNDEFINED")}

    # ---- three systems (frozen) --------------------------------------------
    res = {}
    for key, args in (
        ("5M_ONLY", dict(sysname="5M_ONLY", sig_tf="5m", up_idx=up5_1m, dn_idx=dn5_1m,
                         uom=up5_open, dom=dn5_open, mode="FIXED")),
        ("1M_ONLY", dict(sysname="1M_ONLY", sig_tf="1m",
                         up_idx=sorted(up1), dn_idx=sorted(dn1),
                         uom={i: o1[i] for i in up1}, dom={i: o1[i] for i in dn1},
                         mode="FIXED")),
    ):
        res[key] = X.run_system(args["sysname"], args["sig_tf"], args["up_idx"],
                                args["dn_idx"], args["uom"], args["dom"],
                                o1, h1, l1, c1, TIME, reg_at_1m, args["mode"])
    ta1, sa1 = X.run_system("ADAPTIVE", "1m", sorted(up1), sorted(dn1),
                            {i: o1[i] for i in up1}, {i: o1[i] for i in dn1},
                            o1, h1, l1, c1, TIME, reg_at_1m, "ADAPTIVE")
    ta5, sa5 = X.run_system("ADAPTIVE", "5m", up5_1m, dn5_1m, up5_open, dn5_open,
                            o1, h1, l1, c1, TIME, reg_at_1m, "ADAPTIVE")
    systems = {
        "5M_ONLY": {"trades": res["5M_ONLY"][0], "skips": res["5M_ONLY"][1]},
        "1M_ONLY": {"trades": res["1M_ONLY"][0], "skips": res["1M_ONLY"][1]},
        "ADAPTIVE": {"trades": ta1 + ta5, "skips": {k: sa1[k] + sa5[k] for k in sa1}},
    }
    all_rows = []
    for k, v in systems.items():
        for tr in v["trades"]:
            tr["system"] = k
        all_rows += v["trades"]
    adf = pd.DataFrame(all_rows)
    adf.to_csv(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_LONG_ALL_TRADES.csv"), index=False)
    print(f"trades: " + ", ".join(f"{k}={len(v['trades'])}" for k, v in systems.items()),
          flush=True)

    # ---- headline table ------------------------------------------------------
    headline = {}
    for k, v in systems.items():
        st = stats_block(v["trades"])
        prim_mask = np.ones(len(v["trades"]), dtype=bool)
        dfk = pd.DataFrame(v["trades"])
        if len(dfk):
            net1 = dfk["R1.0"].to_numpy(float)
            stk, dd = max_streak_dd(net1)
            st["max_losing_streak_R"] = int(stk)
            st["max_drawdown_R_1x"] = dd
            mfe = dfk.get("exit1.0_price")
        st["signal_tf_split"] = (dfk["signal_tf"].value_counts().to_dict()
                                 if len(dfk) else {})
        headline[k] = st

    # ---- RANGE / MOMENTUM comparisons ---------------------------------------
    def reg_slice(trades, regime):
        df = pd.DataFrame(trades)
        if not len(df):
            return df
        return df[df["regime_at_entry"] == regime]

    cmp_regimes = {}
    for reg in ("RANGE", "MOMENTUM"):
        row = {}
        for k in ("1M_ONLY", "5M_ONLY"):
            g = reg_slice(systems[k]["trades"], reg)
            st = stats_block(g.to_dict("records")) if len(g) else {"trades": 0}
            row[k] = st
        cmp_regimes[reg] = row

    # ---- monthly / quarterly regime distribution -----------------------------
    m5 = pd.to_datetime(df5["candle_open_time"], unit="ms", utc=True)
    per = m5.dt.to_period("M").astype(str)
    q = m5.dt.to_period("Q").astype(str)
    def dist_table(periods):
        tmp = pd.DataFrame({"p": periods, "r": reg5})
        out = []
        for pval, g in tmp.groupby("p"):
            n = len(g)
            out.append({"period": pval, "bars": int(n),
                        "RANGE_pct": round(float((g.r == 'RANGE').mean() * 100), 2),
                        "MOMENTUM_pct": round(float((g.r == 'MOMENTUM').mean() * 100), 2),
                        "TRANSITION_pct": round(float((g.r == 'TRANSITION').mean() * 100), 2),
                        "switches": int((g.r.values[1:] != g.r.values[:-1]).sum())})
        return out
    monthly = dist_table(per)
    quarterly = dist_table(q)

    # ---- quarterly walk-forward per system ------------------------------------
    ent = pd.to_datetime(adf["entry_time_ms"], unit="ms", utc=True)
    adfq = ent.dt.to_period("Q").astype(str)
    wf_rows = []
    for k in ("5M_ONLY", "1M_ONLY", "ADAPTIVE"):
        g_all = adf[adf.system == k].copy()
        g_all["q"] = pd.to_datetime(g_all.entry_time_ms, unit="ms", utc=True).dt.to_period("Q").astype(str)
        for qv, g in g_all.groupby("q"):
            row = {"system": k, "quarter": qv, "trades": int(len(g))}
            for kk in POLICIES:
                row[f"wr_{kk}"] = float((g[f"exit{kk}_reason"] == "TARGET").mean())
                row[f"meanR_{kk}"] = float(g[f"R{kk}"].mean())
            wf_rows.append(row)
    wf = pd.DataFrame(wf_rows)
    wf.to_csv(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_LONG_WALKFORWARD.csv"), index=False)

    results = {
        "meta": {
            "symbol": SYMBOL, "venue": "Binance USD-M perpetual (1m)",
            "window_utc": f"{datetime.fromtimestamp(TIME[0]/1000, timezone.utc).isoformat()} -> "
                          f"{datetime.fromtimestamp(TIME[-1]/1000, timezone.utc).isoformat()}",
            "days": round(span_days, 1), "bars_1m": int(len(df1)), "bars_5m": int(len(df5)),
            "frozen_rules_source": "exp_adaptive_ema_1m_5m.py (unchanged)",
            "interpretations": ["I-1 entry next-open", "I-2 prior-opposite-cross OPEN stop + reversal exit next-open",
                                "I-3 causal rolling median 288", "F-1 all systems execute on 1m stream"],
        },
        "classifier_health": {
            "distribution_pct": dist,
            "switches_total": n_switch,
            "switches_per_day": round(switch_per_day, 2),
            "state_durations": dur_by_state,
            "monthly": monthly,
            "quarterly": quarterly,
        },
        "headline": headline,
        "range_comparison": cmp_regimes["RANGE"],
        "momentum_comparison": cmp_regimes["MOMENTUM"],
        "walkforward_quarterly": wf_rows,
        "signals": {"crosses_1m": len(up1) + len(dn1), "crosses_5m": len(up5) + len(dn5)},
    }
    with open(os.path.join(HERE, "OPHELIA_ADAPTIVE_EMA_LONG_HISTORY_RESULTS.json"),
              "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
        f.write("\n")

    # quick console digest
    for k in ("5M_ONLY", "1M_ONLY", "ADAPTIVE"):
        hh = headline[k]
        print(f"{k}: trades={hh['trades']} wr1={hh.get('wr_1.0',0)*100:.1f}% "
              f"meanR1={hh.get('meanR_1.0',float('nan')):+.3f} "
              f"wr2={hh.get('wr_2.0',0)*100:.1f}% meanR2={hh.get('meanR_2.0',float('nan')):+.3f} "
              f"wr3={hh.get('wr_3.0',0)*100:.1f}% meanR3={hh.get('meanR_3.0',float('nan')):+.3f} "
              f"| tf_split={hh['signal_tf_split']}")
    for reg in ("RANGE", "MOMENTUM"):
        a = cmp_regimes[reg]["1M_ONLY"]; b = cmp_regimes[reg]["5M_ONLY"]
        print(f"{reg}: 1m n={a.get('trades')} meanR1={a.get('meanR_1.0',float('nan')):+.3f} | "
              f"5m n={b.get('trades')} meanR1={b.get('meanR_1.0',float('nan')):+.3f}")
    print(f"classifier: dist={dist} switches/day={switch_per_day:.1f} "
          f"median_dur_min={{k: v['median_minutes'] for k,v in dur_by_state.items()}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
