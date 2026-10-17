"""Unit tests for 21-Point Live Readiness Preflight & Deep Reconciliation."""

import pytest
from control_plane import core, db, config


def test_preflight_21_points_structure():
    """Verify that run_preflight executes the authoritative 21-point checklist."""
    res = core.run_preflight(user_id=1)
    
    assert "checklist" in res
    assert "items" in res
    checklist = res["checklist"]
    assert len(checklist) == 21
    assert res["items_count"] == 21
    assert res["passed_count"] + res["failed_count"] == 21

    # Check key items exist
    items = [item["item"] for item in checklist]
    expected_items = [
        "BingX API Authentication",
        "Exchange Connectivity",
        "API Credentials & Signatures",
        "Active Signed Balance Query",
        "Futures Trading Permissions",
        "Withdrawal Permission Absence Check",
        "Minimum Trading Capital",
        "Available Margin Threshold",
        "Active Position Deep Reconciliation",
        f"Concurrency Limit (MAX_OPEN_TRADES = {res['configured_max_open_trades']})",
        "Single Position Per Symbol Constraint",
        "Fail-Closed Risk Barrier",
        "Deterministic Stop Loss Enforced",
        "Canonical Target Geometry",
        "Execution Engine Health",
        "Local Position Journal Integrity",
        "System Clock & UTC Drift Sync",
        "Market Ingestion Feed Freshness",
        "Universal Watchlist Dynamic Discovery",
        f"Ollama LLM Host ({config.LLM_PRIMARY})",
        "TradingAgents Framework v0.4.0",
    ]

    for expected in expected_items:
        assert expected in items, f"Missing required preflight item: {expected}"

    # Verify fail-closed defaults
    assert res["shadow_enforced"] is True
    assert res["live_enabled"] is False
    assert res["execution_blocked"] is True
    assert res["max_open_trades"] == 4
