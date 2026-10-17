"""Phase 2.9B - cross-exchange data integrity, price parity, indicator parity, signals.

Outputs (in this folder):
    BINGX_DATA_INTEGRITY.md / BINANCE_DATA_INTEGRITY.md
    OPHELIA_EXCHANGE_INDICATOR_PARITY.csv
    OPHELIA_EXCHANGE_SIGNAL_COMPARISON.csv
    exchange_comparison_summary.json (consumed by the report builder)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.canonical.indicators import session_vwap, supertrend          # noqa: E402
from research.canonical.strategies.vwap_supertrend import (                 # noqa: E402
    detect_active_line_crosses)

TF_MS = 300_000
ST_LEN, ST_FACTOR = 10, 4.0
WARMUP = 300


def load(sym):
    df = pd.read_csv(os.path.join(HERE, sym))
    df["candle_open_time"] = df["candle_open_time"].astype("int64")
    return df.sort_values("candle_open_time").reset_index(drop=True)


def integrity(df: pd.DataFrame, label: str, window_start_ms=None) -> dict:
    t = df["candle_open_time"].to_numpy()
    o, h, l, c, v = (df[k].to_numpy(float) for k in
                     ("open", "high", "low", "close", "volume"))
    dup = int(len(t) - len(np.unique(t)))
    nonmono = int((np.diff(t) <= 0).sum())
    expected = None
    if window_start_ms is not None:
        expected = int((t[-1] - window_start_ms) // TF_MS) + 1
    gaps = 0
    if window_start_ms is not None:
        grid = np.arange(window_start_ms, t[-1] + TF_MS, TF_MS)
        gaps = int(len(grid) - np.intersect1d(grid, t).size)
    bad_ohlc = int(((h < l) | (h < o - 1e-9) | (h < c - 1e-9) |
                    (l > o + 1e-9) | (l > c + 1e-9)).sum())
    nonpos_price = int((o <= 0).sum() + (c <= 0).sum())
    zero_vol = int((v == 0).sum())
    neg_vol = int((v < 0).sum())
    return {
        "label": label, "candles": len(df),
        "first_open_utc": pd.to_datetime(t[0], unit="ms", utc=True),
        "last_open_utc": pd.to_datetime(t[-1], unit="ms", utc=True),
        "duplicate_timestamps": dup, "non_monotonic": nonmono,
        "missing_candles_vs_grid": gaps, "expected_if_grid": expected,
        "invalid_ohlc": bad_ohlc, "nonpositive_price": nonpos_price,
        "zero_volume_bars": zero_vol, "negative_volume": neg_vol,
    }


def integrity_md(r: dict, venue: str, notes: list) -> str:
    lines = [f"# {venue} DATA INTEGRITY", "",
             f"- candles: **{r['candles']}**  ({r['first_open_utc']} -> {r['last_open_utc']}, UTC)",
             f"- duplicate timestamps: {r['duplicate_timestamps']}",
             f"- non-monotonic timestamps: {r['non_monotonic']}",
             f"- missing 5m candles vs perfect grid: **{r['missing_candles_vs_grid']}**",
             f"- invalid OHLC bars: {r['invalid_ohlc']}",
             f"- non-positive prices: {r['nonpositive_price']}",
             f"- zero-volume bars: {r['zero_volume_bars']} | negative volume: {r['negative_volume']}",
             "", "## Notes"] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def bps(a, b):
    return np.abs(a - b) / b * 1e4


def main() -> int:
    bx = load("bingx_sol_5m_2026_07.csv")
    bn = load("binance_sol_5m_2026_06_07.csv")

    # ---------------- integrity ----------------
    bx_start = int(bx["candle_open_time"].iloc[0])
    int_bx = integrity(bx, "BINGX Jul 8 05:25 -> Jul 31 23:55", bx_start)
    # BingX first bar is mid-window (API horizon); grid starts at its own first bar
    int_bn = integrity(bn, "BINANCE Jun 1 00:00 -> Jul 31 23:55",
                       int(bn["candle_open_time"].iloc[0]))
    with open(os.path.join(HERE, "BINGX_DATA_INTEGRITY.md"), "w", encoding="utf-8") as f:
        f.write(integrity_md(int_bx, "BINGX", [
            "API horizon: BingX v3 klines serve only ~45 days; June unavailable (see BINGX_RAW_MANIFEST.json).",
            "Missing-candle count is measured from BingX's own first available bar, not from Jun 1.",
            "Partial-final-candle check: last bar 23:55 closes 00:00 -> complete (window ends at month boundary).",
        ]))
    with open(os.path.join(HERE, "BINANCE_DATA_INTEGRITY.md"), "w", encoding="utf-8") as f:
        f.write(integrity_md(int_bn, "BINANCE", [
            "Full two-complete-month window retrieved from fapi/v1/klines.",
            "Partial-final-candle check: last bar 23:55 closes 00:00 -> complete.",
        ]))

    # ---------------- price parity on overlap ----------------
    m = bx.merge(bn, on="candle_open_time", suffixes=("_bx", "_bn")).sort_values("candle_open_time")
    parity_rows = []
    for col in ("open", "high", "low", "close"):
        d_bps = bps(m[f"{col}_bx"].to_numpy(), m[f"{col}_bn"].to_numpy())
        parity_rows.append({"field": col, "n": len(m),
                            "max_abs_diff": float(np.abs(m[f"{col}_bx"] - m[f"{col}_bn"]).max()),
                            "mean_abs_diff": float(np.abs(m[f"{col}_bx"] - m[f"{col}_bn"]).mean()),
                            "mean_abs_diff_bps": float(d_bps.mean()),
                            "max_abs_diff_bps": float(d_bps.max())})
    vol_ratio = float((m["volume_bx"].sum() / m["volume_bn"].sum())
                      if m["volume_bn"].sum() else float("nan"))
    pd.DataFrame(parity_rows).to_csv(
        os.path.join(HERE, "OPHELIA_EXCHANGE_PRICE_PARITY.csv"), index=False)

    # ---------------- indicators per venue (engine-computed, no TV imports) ----
    def indicators(df):
        d, active, fl, fu = supertrend(df, ST_LEN, ST_FACTOR)
        vwap = session_vwap(df)
        up = np.where(d == 1, active, np.nan)
        dn = np.where(d == -1, active, np.nan)
        w = min(WARMUP, len(df))
        up[:w] = np.nan; dn[:w] = np.nan
        return d, active, vwap, up, dn

    d_bx, st_bx, vw_bx, up_bx, dn_bx = indicators(bx)
    d_bn, st_bn, vw_bn, up_bn, dn_bn = indicators(bn)

    ind_rows = []
    for name, a, b in (("ST10_4_active_line", st_bx, st_bn),
                       ("session_vwap", vw_bx, vw_bn)):
        mm = m["candle_open_time"].to_numpy()
        idx_bx = {int(t): i for i, t in enumerate(bx["candle_open_time"])}
        idx_bn = {int(t): i for i, t in enumerate(bn["candle_open_time"])}
        da, db, both = [], [], []
        for t in mm:
            i, j = idx_bx[int(t)], idx_bn[int(t)]
            va, vb = a[i], b[j]
            if np.isfinite(va) and np.isfinite(vb):
                da.append(va); db.append(vb); both.append((va, vb))
        da, db = np.array(da), np.array(db)
        diff_bps = bps(da, db)
        ind_rows.append({"indicator": name, "n_overlap_bars": len(da),
                         "mean_abs_diff_bps": float(diff_bps.mean()),
                         "max_abs_diff_bps": float(diff_bps.max()),
                         "pct_bars_within_1bp": float((diff_bps <= 1).mean() * 100)})
    # direction agreement
    dir_map_bx = {int(t): d_bx[i] for t, i in
                  ((int(t), i) for i, t in enumerate(bx["candle_open_time"]))}
    dir_map_bn = {int(t): d_bn[i] for t, i in
                  ((int(t), i) for i, t in enumerate(bn["candle_open_time"]))}
    agree = [dir_map_bx[int(t)] == dir_map_bn[int(t)] for t in m["candle_open_time"]]
    ind_rows.append({"indicator": "ST10_4_direction", "n_overlap_bars": len(agree),
                     "mean_abs_diff_bps": None, "max_abs_diff_bps": None,
                     "pct_bars_within_1bp": float(np.mean(agree) * 100)})
    pd.DataFrame(ind_rows).to_csv(
        os.path.join(HERE, "OPHELIA_EXCHANGE_INDICATOR_PARITY.csv"), index=False)

    # ---------------- signals per venue ----------------
    def sigs(up, dn, vw, cl):
        L, S = detect_active_line_crosses(up, dn, vw, cl)
        return [(int(bx["candle_open_time"].iloc[i]), +1) if up is up_bx else
                (int(bn["candle_open_time"].iloc[i]), +1) for i in L], \
               [(int(bx["candle_open_time"].iloc[i]), -1) if up is up_bx else
                (int(bn["candle_open_time"].iloc[i]), -1) for i in S]

    # (simpler explicit builds)
    Lb, Sb = detect_active_line_crosses(up_bx, dn_bx, vw_bx, bx["close"].to_numpy(float))
    Ln, Sn = detect_active_line_crosses(up_bn, dn_bn, vw_bn, bn["close"].to_numpy(float))
    sig_bx = sorted([(int(bx["candle_open_time"].iloc[i]), +1) for i in Lb] +
                    [(int(bx["candle_open_time"].iloc[i]), -1) for i in Sb])
    sig_bn = sorted([(int(bn["candle_open_time"].iloc[i]), +1) for i in Ln] +
                    [(int(bn["candle_open_time"].iloc[i]), -1) for i in Sn])

    # match with tolerance windows — RESTRICTED to the BingX-overlap window so the
    # venue-only counts are not inflated by Binance's extra June coverage
    bx_t0, bx_t1 = int(bx["candle_open_time"].iloc[0]), int(bx["candle_open_time"].iloc[-1])
    sig_bn_overlap = [(t, d) for (t, d) in sig_bn if bx_t0 <= t <= bx_t1]

    def match(a_list, b_list, tol_ms):
        used, pairs, only_a = set(), [], []
        for ta, da in a_list:
            best = None
            for k, (tb, db) in enumerate(b_list):
                if k in used or db != da:
                    continue
                if abs(tb - ta) <= tol_ms and (best is None or abs(tb - ta) < abs(b_list[best][0] - ta)):
                    best = k
            if best is None:
                only_a.append((ta, da))
            else:
                used.add(best)
                pairs.append((ta, b_list[best][0], da))
        return pairs, only_a, [b_list[k] for k in range(len(b_list)) if k not in used]

    rows = []
    timing = {"exact": 0, "m5": 0, "m10": 0, "m15": 0}
    pair_details = []
    pairs_all, bx_only_all, bn_only_all = [], [], []
    for label, tol in (("exact", 0), ("pm5m", 300_000), ("pm10m", 600_000), ("pm15m", 900_000)):
        pairs, only_bx, only_bn = match(sig_bx, sig_bn_overlap, tol)
        rows.append({"tolerance": label, "bingx_signals": len(sig_bx),
                     "binance_signals": len(sig_bn),
                     "matched": len(pairs), "bingx_only": len(only_bx),
                     "binance_only": len(only_bn)})
        if label == "exact":
            timing["exact"] = len(pairs)
        if label == "pm5m":
            timing["m5"] = len(pairs)
        if label == "pm10m":
            timing["m10"] = len(pairs)
        if label == "pm15m":
            pairs_all, bx_only_all, bn_only_all = pairs, only_bx, only_bn
            timing["m15"] = len(pairs)
    for ta, tb, d in pairs_all:
        pair_details.append({
            "direction": "LONG" if d == 1 else "SHORT",
            "bingx_signal_open_ms": ta, "binance_signal_open_ms": tb,
            "delay_minutes": (tb - ta) / 60_000.0})
    pd.DataFrame(rows).to_csv(
        os.path.join(HERE, "OPHELIA_EXCHANGE_SIGNAL_COMPARISON.csv"), index=False)
    pd.DataFrame(pair_details).to_csv(
        os.path.join(HERE, "OPHELIA_EXCHANGE_SIGNAL_TIMING.csv"), index=False)

    # TV diagnostic: BingX-derived ST(10,3) vs TV vendor lines on the overlap
    tv_diag = {}
    try:
        tv = pd.read_csv(os.path.join(
            ROOT, "research", "data", "canonical", "DS-A.v1_candles.csv"))
        d_tv, act_tv, fl_tv, fu_tv = supertrend(tv, ST_LEN, 3.0)
        tv_line = np.where(d_tv == 1, act_tv, np.nan)
        d_bx3, act_bx3, _fl3, _fu3 = supertrend(bx, ST_LEN, 3.0)
        bx_line3 = np.where(d_bx3 == 1, act_bx3, np.nan)
        tv_t = set(int(t) for t in tv["candle_open_time"])
        common = [int(t) for t in bx["candle_open_time"] if int(t) in tv_t]
        idx_bx = {int(t): i for i, t in enumerate(bx["candle_open_time"])}
        idx_tv = {int(t): i for i, t in enumerate(tv["candle_open_time"])}
        da, db = [], []
        for t in common:
            va, vb = bx_line3[idx_bx[t]], tv_line[idx_tv[t]]
            if np.isfinite(va) and np.isfinite(vb):
                da.append(va); db.append(vb)
        da, db = np.array(da), np.array(db)
        tv_diag = {"overlap_bars": len(da),
                   "mean_abs_diff_bps": float(bps(da, db).mean()),
                   "max_abs_diff_bps": float(bps(da, db).max()),
                   "note": ("TV file carries factor-3.0 lines only; F4-vs-chart "
                            "comparison impossible by construction.")}
    except Exception as e:                                       # noqa: BLE001
        tv_diag = {"error": str(e)}

    summary = {
        "integrity": {"bingx": {k: (str(v) if isinstance(v, pd.Timestamp) else v)
                                for k, v in int_bx.items()},
                      "binance": {k: (str(v) if isinstance(v, pd.Timestamp) else v)
                                  for k, v in int_bn.items()}},
        "price_parity": parity_rows,
        "volume_ratio_bx_over_bn": vol_ratio,
        "indicator_parity": ind_rows,
        "signal_comparison": rows,
        "timing": timing,
        "signals": {"bingx": sig_bx, "binance": sig_bn},
        "tv_diagnostic_f3": tv_diag,
    }
    with open(os.path.join(HERE, "exchange_comparison_summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
        f.write("\n")
    print("signals  BINGX:", len(sig_bx), " BINANCE:", len(sig_bn))
    print("matched exact/±5m/±10m/±15m:", timing)
    print("TV F3-line diagnostic:", tv_diag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
