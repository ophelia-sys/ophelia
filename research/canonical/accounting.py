"""Accounting: cost lines, P&L layers, R, breakeven table (spec §10-§13)."""
from __future__ import annotations

from typing import Dict, List

import numpy as np

FUNDING_STATUS = "NOT_MODELED"   # D17


def trade_ledger_rows(core_trades, cfg) -> List[dict]:
    """One row per trade × exit policy × slippage scenario (spec §23)."""
    rows: List[dict] = []
    fee_frac = 2.0 * cfg.fee_rate_per_side_bps * 1e-4
    for t in core_trades:
        it = t.intent
        d = it.direction
        dir_s = "LONG" if d == 1 else "SHORT"
        for pname, po in t.outcomes.items():
            gross_frac = 0.0
            if po.reason != "CENSORED":
                gross_frac = d * (po.exit_price / t.entry_price_theoretical - 1.0)
            realized_R = po.realized_R if po.reason != "CENSORED" else None
            hold_min = ((po.exit_time_ms - t.entry_time_ms) / 60_000.0)
            for s in cfg.slippage_scenarios_bps:
                slip_frac = 2.0 * s * 1e-4
                net_frac = gross_frac - slip_frac - fee_frac
                rows.append({
                    "signal_id": it.signal_id,
                    "data_source": f"{it.dataset_id}.{it.dataset_version}",
                    "strategy_id": it.strategy_id,
                    "direction": dir_s,
                    "signal_time_ms": it.signal_time_ms,
                    "entry_time_ms": t.entry_time_ms,
                    "entry_price_theoretical": t.entry_price_theoretical,
                    "entry_price_modeled": t.entry_price_theoretical * (1 - d * s * 1e-4),
                    "slippage_scenario_bps_per_side": s,
                    "exit_policy": pname,
                    "is_primary_policy": pname == t.primary_policy,
                    "target_price": po.target_price,
                    "exit_time_ms": po.exit_time_ms,
                    "exit_price": po.exit_price,
                    "exit_reason": "STOP" if po.reason == "LOSS" else (
                        "TARGET" if po.reason == "WIN" else "CENSORED"),
                    "realized_price_return_gross_bps": gross_frac * 1e4,
                    "fees_bps": fee_frac * 1e4,
                    "slippage_bps_total": slip_frac * 1e4,
                    "funding_status": FUNDING_STATUS,
                    "realized_price_return_net_bps": net_frac * 1e4,
                    "realized_R@policy": realized_R,
                    "pnl_notional_usd": net_frac * cfg_reference_notional(),
                    "margin_roi_pct_ref10x": net_frac * 1000.0,
                    "holding_minutes": hold_min if po.reason != "CENSORED" else np.nan,
                })
        # diagnostics block (per trade, scenario-independent) stored once via primary row
    return rows


def cfg_reference_notional() -> float:
    from research.canonical import REFERENCE_NOTIONAL_USD
    return REFERENCE_NOTIONAL_USD


def breakeven_table(risk_bps_by_trade: np.ndarray) -> List[dict]:
    """Theoretical breakeven win rate p*=(1+c)/(k+c) per §13."""
    out = []
    avg_risk_bps = float(np.mean(risk_bps_by_trade)) if len(risk_bps_by_trade) else float("nan")
    for cost in (0.0, 10.0, 12.0, 14.0, 16.0):
        c = cost / avg_risk_bps if avg_risk_bps and avg_risk_bps > 0 else float("nan")
        for k in (1.0, 1.5, 2.0, 3.0):
            out.append({
                "round_trip_cost_bps": cost,
                "avg_risk_bps": avg_risk_bps,
                "cost_over_risk_c": c,
                "target_kR": k,
                "breakeven_win_rate": (1.0 + c) / (k + c) if c == c else None,
            })
    return out
