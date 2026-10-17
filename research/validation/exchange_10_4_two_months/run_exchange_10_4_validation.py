"""Phase 2.9B - run BOTH exchange datasets through the CANONICAL engine (no new accounting).

Outputs required names into this folder + OPHELIA_EXCHANGE_10_4_RESULTS.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.canonical.config import CanonicalConfig                       # noqa: E402
from research.canonical.runner import run_pipeline                          # noqa: E402

R_TARGETS = (1.0, 1.5, 2.0, 3.0, 5.0)

VENUES = [
    {"key": "bingx", "name": "BINGX",
     "csv": os.path.join(HERE, "bingx_sol_5m_2026_07.csv"),
     "dataset_id": "DS-BINGX-VAL", "dataset_version": "DS-BINGX-VAL.v1"},
    {"key": "binance", "name": "BINANCE",
     "csv": os.path.join(HERE, "binance_sol_5m_2026_06_07.csv"),
     "dataset_id": "DS-BINANCE-VAL", "dataset_version": "DS-BINANCE-VAL.v1"},
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run_venue(v) -> dict:
    df = pd.read_csv(v["csv"])
    df["candle_open_time"] = df["candle_open_time"].astype("int64")
    if "candle_close_time" not in df.columns:
        df["candle_close_time"] = df["candle_open_time"] + 300_000
    cfg = CanonicalConfig(
        dataset_id=v["dataset_id"], dataset_version=v["dataset_version"],
        strategy_id="VWAP_SUPERTREND_ACTIVE_LINE_CROSS_ENGINE",
        indicator_source="ENGINE_COMPUTED", st_factor=4.0, st_length=10,
        r_targets=R_TARGETS, primary_exit_policy="FIXED_R_150")
    out_dir = os.path.join(HERE, f"canonical_run_{v['key']}")
    ds_sha = hashlib.sha256(open(v["csv"], "rb").read()).hexdigest()
    res = run_pipeline(cfg, df, out_dir, dataset_sha256=ds_sha, gates_stats={
        "missing_candle_count": None, "duplicate_timestamp_count": 0,
        "invalid_ohlc_count": 0, "zero_volume_bar_count": 0,
        "volume_available": True})
    return {"cfg": cfg, "res": res}


def risk_geometry(sig_csv_path):
    s = pd.read_csv(sig_csv_path)
    rp = s["risk_pct"].dropna() * 100.0
    if len(rp) == 0:
        return {}
    return {"mean_risk_pct": float(rp.mean()), "median_risk_pct": float(rp.median()),
            "p25_risk_pct": float(rp.quantile(.25)), "p75_risk_pct": float(rp.quantile(.75)),
            "max_risk_pct": float(rp.max()), "n": int(len(rp))}


def policy_table(trades_csv_path):
    t = pd.read_csv(trades_csv_path)
    t = t[t["slippage_scenario_bps_per_side"] == 0.0]
    prim = t[t["is_primary_policy"]]
    rows = []
    for pol, g in t.groupby("exit_policy"):
        resolved = g[g["exit_reason"] != "CENSORED"]
        r = resolved["realized_R@policy"].dropna()
        wins = resolved[resolved["exit_reason"] == "TARGET"]
        rows.append({
            "exit_policy": pol,
            "signals": int(len(g)),
            "resolved": int(len(resolved)),
            "censored": int((g["exit_reason"] == "CENSORED").sum()),
            "hit_rate": float(len(wins) / len(resolved)) if len(resolved) else None,
            "gross_bps_per_trade": float(resolved["realized_price_return_gross_bps"].mean())
                if len(resolved) else None,
            "net_bps_per_trade": float(resolved["realized_price_return_net_bps"].mean())
                if len(resolved) else None,
            "mean_R": float(r.mean()) if len(r) else None,
            "median_R": float(r.median()) if len(r) else None,
            "profit_factor_net": (
                float(resolved.loc[resolved["realized_price_return_net_bps"] > 0,
                                   "realized_price_return_net_bps"].sum() /
                      -resolved.loc[resolved["realized_price_return_net_bps"] <= 0,
                                    "realized_price_return_net_bps"].sum())
                if len(resolved) and (resolved["realized_price_return_net_bps"] <= 0).any()
                else None),
        })
    return rows


def direction_policy_table(trades_csv_path):
    t = pd.read_csv(trades_csv_path)
    t = t[t["slippage_scenario_bps_per_side"] == 0.0]
    rows = []
    for d, gd in t.groupby("direction"):
        for pol, g in gd.groupby("exit_policy"):
            resolved = g[g["exit_reason"] != "CENSORED"]
            if not len(resolved):
                continue
            r = resolved["realized_R@policy"].dropna()
            wins = resolved[resolved["exit_reason"] == "TARGET"]
            rows.append({"direction": d, "exit_policy": pol, "trades": int(len(resolved)),
                         "hit_rate": float(len(wins) / len(resolved)),
                         "net_bps_per_trade": float(resolved["realized_price_return_net_bps"].mean()),
                         "mean_R": float(r.mean()) if len(r) else None})
    return rows


def tails_and_dd(trades_csv_path):
    t = pd.read_csv(trades_csv_path)
    t = t[(t["is_primary_policy"]) & (t["slippage_scenario_bps_per_side"] == 0.0)]
    prim = t.sort_values(["entry_time_ms", "signal_id"])
    mfe = prim["mfe_R"].dropna()
    net = prim["realized_price_return_net_bps"].to_numpy(float)
    eq = np.cumsum(net)
    dd = float(np.min(eq - np.maximum.accumulate(eq))) if len(eq) else None
    streak = best = 0
    for x in (net <= 0):
        streak = streak + 1 if x else 0
        best = max(best, streak)
    return {
        "n_primary_trades": int(len(prim)),
        "mfe_ge_7R_share": float((mfe >= 7).mean()) if len(mfe) else None,
        "mfe_ge_9R_share": float((mfe >= 9).mean()) if len(mfe) else None,
        "mfe_ge_10R_share": float((mfe >= 10).mean()) if len(mfe) else None,
        "max_drawdown_net_bps": dd,
        "max_losing_streak": int(best),
    }


def main() -> int:
    results = {}
    name_map = {
        "bingx": {"signals": "OPHELIA_BINGX_10_4_SIGNALS.csv",
                  "trades": "OPHELIA_BINGX_10_4_TRADES.csv"},
        "binance": {"signals": "OPHELIA_BINANCE_10_4_SIGNALS.csv",
                    "trades": "OPHELIA_BINANCE_10_4_TRADES.csv"},
    }
    for v in VENUES:
        print(f"=== {v['name']} ===", flush=True)
        ran = run_venue(v)
        res = ran["res"]
        sp, tp = res["paths"]["signals"], res["paths"]["trades"]
        shutil.copyfile(sp, os.path.join(HERE, name_map[v["key"]]["signals"]))
        shutil.copyfile(tp, os.path.join(HERE, name_map[v["key"]]["trades"]))
        n_sig = len(res["signals"])
        n_long = sum(1 for s in res["signals"] if s.direction == 1)
        results[v["key"]] = {
            "dataset": v["dataset_id"],
            "total_signals": n_sig, "long_signals": n_long, "short_signals": n_sig - n_long,
            "trades_taken_single_position": len(res["trades"]),
            "anchor_check": str(res["anchor_check"]),
            "invariant_errors": res["invariant_errors"],
            "risk_geometry": risk_geometry(sp),
            "policy_table": policy_table(tp),
            "direction_policy": direction_policy_table(tp),
            "tails": tails_and_dd(tp),
        }
        print(json.dumps(results[v["key"]]["tails"], indent=2))

    # attach cross-venue comparison summary if present
    cmp_path = os.path.join(HERE, "exchange_comparison_summary.json")
    if os.path.exists(cmp_path):
        with open(cmp_path, encoding="utf-8") as f:
            comp = json.load(f)
        slim = {k: comp[k] for k in ("indicator_parity", "signal_comparison",
                                     "timing", "tv_diagnostic_f3", "price_parity",
                                     "volume_ratio_bx_over_bn")}
        results["cross_venue"] = slim

    with open(os.path.join(HERE, "OPHELIA_EXCHANGE_10_4_RESULTS.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
        f.write("\n")
    print("wrote OPHELIA_EXCHANGE_10_4_RESULTS.json")

    for v in VENUES:
        r = results[v["key"]]
        print(f"{v['name']}: signals {r['total_signals']} "
              f"({r['long_signals']}L/{r['short_signals']}S)")
        for row in r["policy_table"]:
            print(f"   {row['exit_policy']:14s} hit={row['hit_rate']} "
                  f"net={row['net_bps_per_trade'] and round(row['net_bps_per_trade'],2)}bp "
                  f"meanR={row['mean_R'] and round(row['mean_R'],3)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
