"""Diagnose the DS-A anchor mismatch (spec §18: STOP + diagnose, no repair).

Questions answered here:
 Q1. Which Supertrend factor do the vendor Up/Down Trend columns represent?
     (parity vs engine-computed ST length=10, factor ∈ {3.0, 3.5, 4.0})
 Q2. Which entry-definition variant reproduces which historical signal set?
     targets: 121(58L/63S)=F4 set · 177(96L/81S)=F3 set · 183(96L/87S)=Phase2.6 set
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from research.canonical.data_contract import load_canonical_store
from research.canonical.indicators import session_vwap, supertrend

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CANON = os.path.join(ROOT, "research", "data", "canonical", "DS-A.v1_candles.csv")


def parity_stats(mine: np.ndarray, vendor: np.ndarray):
    m = np.isfinite(mine) & np.isfinite(vendor)
    if m.sum() == 0:
        return None
    diff = np.abs(mine[m] - vendor[m])
    rel = diff / vendor[m]
    return {"n_both": int(m.sum()),
            "mean_abs_diff": float(diff.mean()),
            "pct_within_1bp": float((rel <= 1e-4).mean() * 100),
            "pct_within_5bp": float((rel <= 5e-4).mean() * 100)}


def count_variant(up, down, vwap, close, name):
    n = len(close)
    L = S = 0
    for i in range(1, n):
        u0, u1, d0, d1 = up[i-1], up[i], down[i-1], down[i]
        v0, v1, c = vwap[i-1], vwap[i], close[i]
        if np.isfinite(u0) and np.isfinite(u1):
            # a) spec §4 (inclusive touch, close confirm)
            if u0 < v0 and u1 >= v1 and c > v1:
                L += 1
            # b) strict both
            if u0 < v0 and u1 > v1 and c > v1:
                L += 1  # counted separately below via flags instead
        if False:
            pass
    # separate explicit variants:
    def variant(rule):
        cnt_l = cnt_s = 0
        for i in range(1, n):
            u0, u1, d0, d1 = up[i-1], up[i], down[i-1], down[i]
            v0, v1, c = vwap[i-1], vwap[i], close[i]
            okU = np.isfinite(u0) and np.isfinite(u1)
            okD = np.isfinite(d0) and np.isfinite(d1)
            if rule == "spec4":          # inclusive touch + close confirm
                if okU and u0 < v0 and u1 >= v1 and c > v1: cnt_l += 1
                if okD and d0 > v0 and d1 <= v1 and c < v1: cnt_s += 1
            elif rule == "strict":       # strict cross, close confirm
                if okU and u0 < v0 and u1 > v1 and c > v1: cnt_l += 1
                if okD and d0 > v0 and d1 > v1 and c < v1: cnt_s += 1
            elif rule == "noclose":      # inclusive touch, no close confirm
                if okU and u0 < v0 and u1 >= v1: cnt_l += 1
                if okD and d0 > v0 and d1 <= v1: cnt_s += 1
            elif rule == "pine":         # close crosses vwap, trend favorable
                if okU and ((close[i-1] <= v0 and c > v1)): cnt_l += 1
                if okD and ((close[i-1] >= v0 and c < v1)): cnt_s += 1
            elif rule == "flip":         # ST direction flip + close side of vwap
                pass
        return cnt_l, cnt_s

    out = {}
    for r in ("spec4", "strict", "noclose", "pine"):
        cl, cs = variant(r)
        out[r] = f"{cl+cs} ({cl}L/{cs}S)"
    return out


def main():
    df = load_canonical_store(CANON)
    close = df["close"].to_numpy(float)
    otime = df["candle_open_time"].to_numpy()

    up_v = df["up_trend_vendor"].to_numpy(float)
    dn_v = df["down_trend_vendor"].to_numpy(float)
    vw_v = df["vwap_vendor"].to_numpy(float)

    print("=== Q1: vendor line factor parity ===")
    for f in (3.0, 3.5, 4.0):
        direction, active, fl, fu = supertrend(df, 10, f)
        # compare only where vendor has a value AND our direction matches vendor side
        par_up = parity_stats(np.where(direction == 1, active, np.nan), up_v)
        par_dn = parity_stats(np.where(direction == -1, active, np.nan), dn_v)
        fmt = lambda p: ("n=%(n_both)d mean=%(mean_abs_diff).5f within1bp=%(pct_within_1bp).1f%% within5bp=%(pct_within_5bp).1f%%" % p) if p else "no-overlap"
        print(f"ST(10,{f}): UP  {fmt(par_up)}")
        print(f"           DOWN{fmt(par_dn)}")

    print("\n=== Q1b: vendor VWAP session-reset convention ===")
    vw_e = session_vwap(df)
    print("engine VWAP all-NaN (volume absent, S2):", bool(np.isnan(vw_e).all()))
    # reset check: at the first bar of each UTC day, does vendor VWAP == typical price?
    day = otime // 86_400_000
    first_of_day = np.where(np.concatenate(([True], day[1:] != day[:-1])))[0]
    tp = (df["high"].to_numpy(float) + df["low"].to_numpy(float) + close) / 3.0
    diffs = np.abs(vw_v[first_of_day] - tp[first_of_day]) / tp[first_of_day]
    print(f"day-start bars: {len(first_of_day)}; vendor VWAP==TP within 1bp on "
          f"{(diffs <= 1e-4).mean()*100:.1f}%  (100% => resets at 00:00 UTC)")

    print("\n=== Q2: signal-count variants on VENDOR lines ===")
    for name, res in count_variant(up_v, dn_v, vw_v, close, "vendor").items():
        print(f"{name:8s}: {res}")

    print("\nhistorical targets: 121 (58L/63S)=10/4.0 set | 177 (96L/81S)=10/3.0 set | "
          "183 (96L/87S)=Phase2.6 set")


if __name__ == "__main__":
    main()
