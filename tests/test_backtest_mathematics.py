"""Unit tests for Ophelia Backtest & Simulation Mathematics.

Verifies:
1. Exact partial exit weighted contributions:
   - TP1 50% at +1.00%, Remainder 50% at 0.00% (Breakeven) -> +0.50%
   - TP1 50% at +1.00%, Remainder 50% at +2.00% (Trailing) -> +1.50%
2. Directional sign convention:
   - SHORT entry 80968.5, exit 80860.29 -> +0.1336% (+0.13% gross)
   - LONG entry 80000.0, exit 80800.0 -> +1.00% gross
3. Cost accounting:
   - Separate Gross Symbol Move %, Fees (10 bps = 0.10%), Slippage (4 bps = 0.04%), Funding (0.00%)
   - Net % = Gross - Costs
"""

import pytest


def compute_price_move_pct(entry_px: float, exit_px: float, direction: str) -> float:
    if entry_px <= 0:
        return 0.0
    if direction == "LONG":
        return ((exit_px - entry_px) / entry_px) * 100.0
    else:
        return ((entry_px - exit_px) / entry_px) * 100.0


def compute_weighted_realized_return(
    entry_px: float,
    direction: str,
    exits: list[dict],
    fee_bps: float = 5.0,
    slippage_bps: float = 2.0,
    funding_rate_pct: float = 0.0
) -> dict:
    total_gross_pct = 0.0
    breakdown = []
    
    for leg in exits:
        exit_px = leg["price"]
        qty_frac = leg["qty_fraction"]
        move_pct = compute_price_move_pct(entry_px, exit_px, direction)
        contrib_pct = move_pct * qty_frac
        total_gross_pct += contrib_pct
        breakdown.append({
            "name": leg.get("name", "EXIT"),
            "price": exit_px,
            "qty_fraction": qty_frac,
            "move_pct": round(move_pct, 4),
            "contribution_pct": round(contrib_pct, 4)
        })
    
    fee_pct = (fee_bps / 10000.0) * 2.0 * 100.0
    slippage_pct = (slippage_bps / 10000.0) * 2.0 * 100.0
    funding_pct = funding_rate_pct
    total_costs_pct = fee_pct + slippage_pct + funding_pct
    net_pct = total_gross_pct - total_costs_pct

    return {
        "gross_symbol_move_pct": round(total_gross_pct, 4),
        "gross_formatted": f"{'+' if total_gross_pct >= 0 else ''}{total_gross_pct:.2f}%",
        "fees_pct": round(fee_pct, 4),
        "slippage_pct": round(slippage_pct, 4),
        "funding_pct": round(funding_pct, 4),
        "net_pnl_pct": round(net_pct, 4),
        "net_formatted": f"{'+' if net_pct >= 0 else ''}{net_pct:.2f}%",
        "breakdown": breakdown
    }


def test_user_example_1_tp1_breakeven():
    # TP1: +1.00% on 50%, Remaining: 0.00% on 50% -> Final Gross: +0.50%
    entry_px = 100.0
    exits = [
        {"name": "TP1", "price": 101.0, "qty_fraction": 0.50},
        {"name": "BREAKEVEN", "price": 100.0, "qty_fraction": 0.50}
    ]
    res = compute_weighted_realized_return(entry_px, "LONG", exits)
    assert res["gross_symbol_move_pct"] == 0.50
    assert res["gross_formatted"] == "+0.50%"


def test_user_example_2_tp1_trailing():
    # TP1: +1.00% on 50%, Remaining trailing: +2.00% on 50% -> Final Gross: +1.50%
    entry_px = 100.0
    exits = [
        {"name": "TP1", "price": 101.0, "qty_fraction": 0.50},
        {"name": "TRAILING", "price": 102.0, "qty_fraction": 0.50}
    ]
    res = compute_weighted_realized_return(entry_px, "LONG", exits)
    assert res["gross_symbol_move_pct"] == 1.50
    assert res["gross_formatted"] == "+1.50%"


def test_screenshot_short_trade_math():
    # User's actual trade from screenshot: Entry 80968.5, Exit 80860.29 on SHORT
    entry_px = 80968.5
    exit_px = 80860.29
    exits = [{"name": "TRAILING_STOPPED", "price": exit_px, "qty_fraction": 1.0}]
    
    res = compute_weighted_realized_return(entry_px, "SHORT", exits, fee_bps=5.0, slippage_bps=2.0)
    
    # 80968.5 - 80860.29 = 108.21. 108.21 / 80968.5 * 100 = 0.133647%
    assert round(res["gross_symbol_move_pct"], 2) == 0.13
    assert res["gross_formatted"] == "+0.13%"
    # Costs: fees = 0.10%, slippage = 0.04% -> net = 0.1336 - 0.14 = -0.0064%
    assert res["net_formatted"] == "-0.01%"
    assert res["fees_pct"] == 0.10
    assert res["slippage_pct"] == 0.04


def test_strategy_lab_raw_symbol_movement_only():
    """Item 2 & OPHELIA Rule: Backtest results must be RAW SYMBOL PRICE MOVEMENT ONLY.
    
    Zero fees, slippage, funding, leverage, margin, or USDT PnL participate in performance.
    """
    from control_plane.strategy_lab import StrategyResearchLab

    lab = StrategyResearchLab(symbols=["BTC-USDT"], timeframes=[5], hours=12)

    # Provide 1m candles for trade progression
    entry_ts = 1700000000000
    lab.candles_by_symbol_tf["BTC-USDT"] = {
        1: [
            {"ts": entry_ts, "open": 80000.0, "high": 80100.0, "low": 79950.0, "close": 80050.0, "volume": 10.0, "closed": True},
            {"ts": entry_ts + 60_000, "open": 80050.0, "high": 81000.0, "low": 80000.0, "close": 80900.0, "volume": 15.0, "closed": True},
        ]
    }

    # Signal with TP1 at 80800.0 (+1.00%), SL at 79200.0 (-1.00%)
    signals = [{
        "symbol": "BTC-USDT",
        "timeframe": 5,
        "timestamp": entry_ts,
        "direction": "LONG",
        "entry_price": 80000.0,
        "sl": 79200.0,
        "tp1": 80800.0,
        "tp2": None,
        "tp3": None,
        "tp1_pct": 100.0,  # 100% exit at TP1
        "regime": "TREND / EXPANSION",
    }]

    metrics = lab.simulate_strategy(signals, "Test Raw Symbol", "TEST_RAW")

    assert metrics.trade_count == 1
    trade = metrics.executed_trades[0]
    # Raw symbol move: (80800 - 80000) / 80000 * 100 = +1.00%
    assert round(trade["gross_ret_pct"], 2) == 1.00
    assert round(trade["net_ret_pct"], 2) == 1.00
    assert trade["fee_pct"] == 0.0
    assert trade["slippage_pct"] == 0.0
    assert trade["funding_pct"] == 0.0
    assert trade["pnl_usd"] == 0.0
    assert round(metrics.net_return_pct, 2) == 1.00

