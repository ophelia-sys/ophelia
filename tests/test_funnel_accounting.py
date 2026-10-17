"""Unit tests for Causal Funnel Accounting and Reconciliation in Ophelia Strategy Lab.

Requirements:
1. Every risk-valid candidate must have exactly ONE terminal accounting reason.
2. Terminal states supported:
   - simulated_executions
   - capacity_blocked
   - same_symbol_blocked
   - candidate_expired
   - invalidated_by_structure
3. UI counts and metrics reconcile strictly from canonical event records (candidate_records),
   NOT independently calculated or hardcoded counters.
4. Total candidates == sum of all terminal states (Reconciliation Invariant).
"""

import pytest
from control_plane.strategy_lab import StrategyResearchLab


def test_funnel_accounting_reconciliation_all_terminal_states():
    """Verify that multiple terminal outcomes reconcile accurately to total risk-valid candidates."""
    # Setup lab with max_open_trades = 1
    lab = StrategyResearchLab(symbols=["BTC-USDT", "ETH-USDT"], timeframes=[5], hours=12)
    lab.max_open_trades = 1

    base_ts = 1700000000000

    # Provide 1m candles so that executed trades can progress
    lab.raw_1m_by_symbol["BTC-USDT"] = [
        {"ts": base_ts + 60_000, "open": 80000.0, "high": 80800.0, "low": 79900.0, "close": 80800.0, "volume": 10.0, "closed": True},
        {"ts": base_ts + 120_000, "open": 80800.0, "high": 81000.0, "low": 80700.0, "close": 80900.0, "volume": 10.0, "closed": True},
    ]
    lab.raw_1m_by_symbol["ETH-USDT"] = [
        {"ts": base_ts + 60_000, "open": 3000.0, "high": 3050.0, "low": 2980.0, "close": 3050.0, "volume": 10.0, "closed": True},
    ]

    signals = [
        # Candidate 1: Valid LONG on BTC, will execute
        {
            "candidate_id": "cand-btc-1",
            "symbol": "BTC-USDT",
            "timeframe": 5,
            "timestamp": base_ts,
            "direction": "LONG",
            "entry_price": 80000.0,
            "sl": 79200.0,
            "tp1": 80800.0,
            "tp1_pct": 100.0,
        },
        # Candidate 2: Blocked by SAME SYMBOL while BTC trade 1 is open
        {
            "candidate_id": "cand-btc-2",
            "symbol": "BTC-USDT",
            "timeframe": 5,
            "timestamp": base_ts + 30_000,
            "direction": "LONG",
            "entry_price": 80200.0,
            "sl": 79500.0,
            "tp1": 81000.0,
        },
        # Candidate 3: Blocked by CAPACITY while BTC trade 1 is open (max_open_trades=1)
        {
            "candidate_id": "cand-eth-1",
            "symbol": "ETH-USDT",
            "timeframe": 5,
            "timestamp": base_ts + 30_000,
            "direction": "LONG",
            "entry_price": 3000.0,
            "sl": 2950.0,
            "tp1": 3050.0,
        },
        # Candidate 4: Pre-invalidated by structure before fill
        {
            "candidate_id": "cand-btc-3",
            "symbol": "BTC-USDT",
            "timeframe": 5,
            "timestamp": base_ts + 200_000,
            "direction": "SHORT",
            "entry_price": 81000.0,
            "invalidated": True,
            "invalidation_reason": "Opposing liquidity swept prior to retest",
        },
        # Candidate 5: Expired before fill confirmation
        {
            "candidate_id": "cand-eth-2",
            "symbol": "ETH-USDT",
            "timeframe": 5,
            "timestamp": base_ts + 250_000,
            "direction": "LONG",
            "entry_price": 3100.0,
            "expired": True,
        }
    ]

    metrics = lab.simulate_strategy(signals, "Funnel Test Strategy", "EXP_FUNNEL_TEST")

    # Assert total candidates
    assert metrics.funnel_accounting is not None
    fa = metrics.funnel_accounting
    assert fa["risk_valid_candidates"] == 5

    # Check terminal breakdowns
    assert fa["simulated_executions"] == 1
    assert fa["same_symbol_blocked"] == 1
    assert fa["capacity_blocked"] == 1
    assert fa["invalidated_by_structure"] == 1
    assert fa["candidate_expired"] == 1

    # Invariant: sum of all terminal states == total candidates
    total_terminal = (
        fa["simulated_executions"]
        + fa["same_symbol_blocked"]
        + fa["capacity_blocked"]
        + fa["invalidated_by_structure"]
        + fa["candidate_expired"]
    )
    assert total_terminal == fa["risk_valid_candidates"]
    assert fa["reconciled"] is True

    # Assert canonical event records
    assert metrics.candidate_records is not None
    assert len(metrics.candidate_records) == 5

    reasons = {r["candidate_id"]: r["terminal_state"] for r in metrics.candidate_records}
    assert reasons["cand-btc-1"] == "SIMULATED_EXECUTION"
    assert reasons["cand-btc-2"] == "SAME_SYMBOL_BLOCKED"
    assert reasons["cand-eth-1"] == "CAPACITY_BLOCKED"
    assert reasons["cand-btc-3"] == "INVALIDATED_BY_STRUCTURE"
    assert reasons["cand-eth-2"] == "CANDIDATE_EXPIRED"
