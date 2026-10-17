"""Canonical metrics (spec §15-§17): GROSS/NET tagged, ESS, deterministic bootstrap."""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ core helpers

def profit_factor(net_bps: np.ndarray) -> Optional[float]:
    wins = net_bps[net_bps > 0].sum()
    losses = -net_bps[net_bps <= 0].sum()
    if losses == 0:
        return None if wins == 0 else float("inf")
    return float(wins / losses)


def max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    run_max = np.maximum.accumulate(equity)
    return float(np.min(equity - run_max))


def max_losing_streak(outcome_flags: np.ndarray) -> int:
    best = cur = 0
    for f in outcome_flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return int(best)


def ess_ar1(series: np.ndarray, lag: int = 1) -> Optional[float]:
    s = np.asarray(series, dtype=float)
    s = s[~np.isnan(s)]
    n = len(s)
    if n < 3 or np.std(s) == 0:
        return None
    rho = float(np.corrcoef(s[:-lag], s[lag:])[0, 1])
    if not np.isfinite(rho):
        return None
    rho = max(min(rho, 0.999), -0.999)
    return float(n * (1 - rho) / (1 + rho))


def _day_index(times_ms: np.ndarray) -> np.ndarray:
    return (times_ms // 86_400_000).astype(np.int64)


def day_block_bootstrap(series: np.ndarray, times_ms: np.ndarray,
                        B: int, seed: int, block_days: int = 1):
    """Moving-block bootstrap over calendar-day clusters. Deterministic via seed."""
    s = np.asarray(series, dtype=float)
    t = np.asarray(times_ms, dtype=np.int64)
    day = _day_index(t) // block_days
    uniq = np.unique(day)
    by_day = [s[day == d] for d in uniq]
    rng = np.random.default_rng(seed)
    means = np.empty(B)
    K = len(uniq)
    for b in range(B):
        pick = rng.integers(0, K, size=K)
        chunks = [by_day[i] for i in pick]
        means[b] = np.concatenate(chunks).mean() if chunks else np.nan
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


# ------------------------------------------------------------------ aggregation

def aggregate(rows: List[dict], cfg, regime_labels: Optional[Dict[str, str]] = None) -> dict:
    """Compute §15 metrics from primary-policy trade-ledger rows (one scenario)."""
    if not rows:
        return {"n_trades": 0}
    df = pd.DataFrame(rows)
    prim = df[df["is_primary_policy"]].copy()
    prim = prim.sort_values(["entry_time_ms", "signal_id"]).reset_index(drop=True)
    resolved = prim[prim["exit_reason"] != "CENSORED"]

    def block(tag: str, sub: pd.DataFrame) -> dict:
        gross = sub["realized_price_return_gross_bps"].to_numpy(float)
        net = sub["realized_price_return_net_bps"].to_numpy(float)
        if len(sub) == 0:
            return {"n_trades": 0}
        eq_net = np.cumsum(net)
        eq_gross = np.cumsum(gross)
        hold_min = sub["holding_minutes"].dropna().to_numpy(float)
        exposure_h = float(hold_min.sum() / 60.0)
        span_days = max((sub["entry_time_ms"].max() - sub["entry_time_ms"].min())
                        / 86_400_000.0, 1e-9)
        out = {
            "n_trades": int(len(sub)),
            "gross_bps_per_trade": float(gross.mean()),
            "net_bps_per_trade": float(net.mean()),
            "median_net_trade_bps": float(np.median(net)),
            "profit_factor_net": profit_factor(net),
            "win_rate_net": float((net > 0).mean()),
            "max_drawdown_net_bps": max_drawdown(eq_net),
            "max_drawdown_gross_bps": max_drawdown(eq_gross),
            "max_losing_streak": max_losing_streak((net <= 0)),
            "trades_per_week": float(len(sub) / (span_days / 7.0)),
            "exposure_hours": exposure_h,
            "net_bps_per_exposure_hour": (float(net.sum() / exposure_h)
                                          if exposure_h > 0 else None),
            "hit_rate_by_policy": {
                p: float((sub[sub["exit_policy"] == p]["exit_reason"] == "TARGET").mean())
                for p in sorted(sub["exit_policy"].unique())
            },
            "mean_R_by_policy": {
                p: (float(sub[sub["exit_policy"] == p]["realized_R@policy"].mean())
                    if sub[sub["exit_policy"] == p]["realized_R@policy"].notna().any()
                    else None)
                for p in sorted(sub["exit_policy"].unique())
            },
            "median_holding_minutes": float(np.median(hold_min)) if len(hold_min) else None,
        }
        return out

    result: Dict[str, dict] = {}
    for s in sorted(prim["slippage_scenario_bps_per_side"].unique()):
        sub = prim[prim["slippage_scenario_bps_per_side"] == s]
        key = f"SLIP{int(s)}"
        result[key] = {
            "ALL": block("ALL", sub),
            "LONG": block("LONG", sub[sub["direction"] == "LONG"]),
            "SHORT": block("SHORT", sub[sub["direction"] == "SHORT"]),
        }
        # ESS + bootstrap on chronological net series (this scenario)
        net = sub["realized_price_return_net_bps"].to_numpy(float)
        times = sub["entry_time_ms"].to_numpy(np.int64)
        for bd in cfg.bootstrap_blocks_days:
            lo, hi = day_block_bootstrap(net, times, cfg.bootstrap_B,
                                         cfg.bootstrap_seed + bd, block_days=bd)
            result[key][f"bootstrap_ci_net_bps_{bd}d"] = [lo, hi]
        result[key]["ess_ar1"] = ess_ar1(net, cfg.ess_autocorr_lag)
        # regime-conditioned (primary scenario only for brevity of ALL block)
        if regime_labels:
            regs = sub["signal_id"].map(regime_labels)
            for r in sorted(set(regs.dropna())):
                result[key][f"REGIME_{r}"] = block(r, sub[regs == r])

    # diagnostics (primary path)
    diag = {
        "mfe_pct_mean": float(prim["mfe_pct"].mean()),
        "mae_pct_mean": float(prim["mae_pct"].mean()),
        "mfe_R_mean": float(prim["mfe_R"].mean()),
        "mae_R_mean": float(prim["mae_R"].mean()),
    }
    return {"scenarios": result, "diagnostics_primary": diag}


def attach_diagnostics(trades, rows: List[dict]) -> List[dict]:
    """Fill per-trade diagnostic columns onto primary rows (MFE/MAE, times)."""
    by_sig = {}
    for t in trades:
        e = t.entry_price_theoretical
        r = t.risk_price if t.risk_price else np.nan
        prim = t.outcomes[t.primary_policy]
        by_sig[t.intent.signal_id] = {
            "mfe_pct": (t.mfe_price / e - 1.0) * t.intent.direction * 100.0,
            "mae_pct": (t.mae_price / e - 1.0) * t.intent.direction * 100.0,
            "mfe_R": abs(t.mfe_price - e) / r,
            "mae_R": abs(t.mae_price - e) / r,
            "time_to_exit_primary_min":
                (prim.exit_time_ms - t.entry_time_ms) / 60_000.0,
            "primary_exit_reason": prim.reason,
        }
    for row in rows:
        if not row["is_primary_policy"]:
            continue
        d = by_sig.get(row["signal_id"], {})
        row["mfe_pct"] = d.get("mfe_pct")
        row["mae_pct"] = d.get("mae_pct")
        row["mfe_R"] = d.get("mfe_R")
        row["mae_R"] = d.get("mae_R")
        row["time_to_exit_primary_min"] = d.get("time_to_exit_primary_min")
    return rows
