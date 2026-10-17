"""Unit tests for Ophelia Priority Classifier with Decoupled Gamma.

Verifies the 7 mandatory scenarios:
1. Trending Gamma: Positive gamma in Trend/Expansion (Gamma context decoupled from regime)
2. Choppy Gamma: Positive gamma in Chop/Mean Reversion
3. Gamma Unavailable: SOL/XRP/GOLD explicitly report 'GAMMA DATA NOT AVAILABLE'
4. Good R:R: Canonical R:R >= 2.0 qualifies for HIGH priority
5. Bad R:R: R:R < 1.0 rejected / disqualified immediately
6. Aligned Direction: Aligned with HTF bias receives positive alignment boost
7. Countertrend: Prohibited in strong trend without explicit permission; lower priority with permission
"""

import pytest
from control_plane.priority_classifier import classify_trade_priority, validate_target_geometry


def test_scenario_1_trending_gamma():
    """Positive gamma in Trend/Expansion: Gamma context does NOT overwrite trend regime or direction."""
    candidate = {
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_price": 80000.0,
        "sl": 79200.0,
        "tp1": 81600.0,  # R:R = 1600 / 800 = 2.0
    }
    context = {
        "market_regime": "TREND / EXPANSION",
        "gamma_regime": "POSITIVE_GAMMA",
        "htf_bias": "LONG",
        "allows_counter_trend": False,
    }
    res = classify_trade_priority(candidate, context)
    assert res["eligible"] is True
    assert res["priority"] == "HIGH"
    assert res["gamma_state"] == "POSITIVE_GAMMA"
    assert res["market_regime"] == "TREND / EXPANSION"
    assert res["htf_alignment"] is True


def test_scenario_2_choppy_gamma():
    """Positive gamma in Chop/Mean Reversion: favors mean reversion setup."""
    candidate = {
        "symbol": "BTC-USDT",
        "direction": "SHORT",
        "entry_price": 80000.0,
        "sl": 80500.0,
        "tp1": 79000.0,  # R:R = 1000 / 500 = 2.0
    }
    context = {
        "market_regime": "CHOP / MEAN REVERSION",
        "gamma_regime": "POSITIVE_GAMMA",
        "htf_bias": "NEUTRAL",
        "allows_counter_trend": True,
    }
    res = classify_trade_priority(candidate, context)
    assert res["eligible"] is True
    assert res["gamma_state"] == "POSITIVE_GAMMA"
    assert res["market_regime"] == "CHOP / MEAN REVERSION"
    assert res["priority"] in ("HIGH", "MEDIUM")


def test_scenario_3_gamma_unavailable():
    """SOL, XRP, and GOLD must explicitly output GAMMA DATA NOT AVAILABLE and not penalize setup."""
    for sym in ["SOL-USDT", "XRP-USDT", "GOLD"]:
        candidate = {
            "symbol": sym,
            "direction": "LONG",
            "entry_price": 100.0,
            "sl": 98.0,
            "tp1": 105.0,  # R:R = 5 / 2 = 2.5
        }
        context = {
            "market_regime": "TREND / EXPANSION",
            "gamma_regime": "POSITIVE_GAMMA",  # Ignored for alt/gold
            "htf_bias": "LONG",
            "allows_counter_trend": False,
        }
        res = classify_trade_priority(candidate, context)
        assert res["eligible"] is True
        assert res["gamma_state"] == "GAMMA DATA NOT AVAILABLE"


def test_scenario_4_good_risk_reward():
    """R:R >= 2.0 qualifies for high priority classification."""
    candidate = {
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_price": 80000.0,
        "sl": 79500.0,   # Risk = 500
        "tp1": 81500.0,  # Reward = 1500 -> R:R = 3.0
    }
    context = {
        "market_regime": "TREND / EXPANSION",
        "gamma_regime": "NEGATIVE_GAMMA",
        "htf_bias": "LONG",
        "allows_counter_trend": False,
    }
    res = classify_trade_priority(candidate, context)
    assert res["eligible"] is True
    assert res["risk_reward"] == 3.0
    assert res["priority"] == "HIGH"


def test_scenario_5_bad_risk_reward():
    """R:R < 1.0 is immediately rejected."""
    candidate = {
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_price": 80000.0,
        "sl": 79000.0,   # Risk = 1000
        "tp1": 80500.0,  # Reward = 500 -> R:R = 0.5
        "strict_rr_gate": True,
    }
    context = {
        "market_regime": "TREND / EXPANSION",
        "gamma_regime": "NEGATIVE_GAMMA",
        "htf_bias": "LONG",
        "allows_counter_trend": False,
    }
    res = classify_trade_priority(candidate, context)
    assert res["eligible"] is False
    assert res["priority"] == "DISQUALIFIED"
    assert res["status"] == "REJECTED_RISK_REWARD"
    assert res["risk_reward"] == 0.5


def test_scenario_6_aligned_direction():
    """Signal aligned with HTF bias receives positive alignment boost."""
    candidate = {
        "symbol": "ETH-USDT",
        "direction": "LONG",
        "entry_price": 3000.0,
        "sl": 2950.0,
        "tp1": 3100.0,  # R:R = 2.0
    }
    context = {
        "market_regime": "TREND / EXPANSION",
        "gamma_regime": "NEGATIVE_GAMMA",
        "htf_bias": "LONG",
        "allows_counter_trend": False,
    }
    res = classify_trade_priority(candidate, context)
    assert res["htf_alignment"] is True
    assert res["is_countertrend"] is False
    assert res["eligible"] is True


def test_scenario_7_countertrend():
    """Countertrend trade without explicit permission is rejected; with permission receives lower priority."""
    candidate = {
        "symbol": "ETH-USDT",
        "direction": "SHORT",
        "entry_price": 3000.0,
        "sl": 3050.0,
        "tp1": 2900.0,  # R:R = 2.0
    }
    # Without permission in strong trend:
    context_strict = {
        "market_regime": "TREND / EXPANSION",
        "gamma_regime": "NEGATIVE_GAMMA",
        "htf_bias": "LONG",
        "allows_counter_trend": False,
    }
    res_strict = classify_trade_priority(candidate, context_strict)
    assert res_strict["eligible"] is False
    assert res_strict["priority"] == "DISQUALIFIED"
    assert res_strict["status"] == "REJECTED_COUNTERTREND"

    # With permission in transition/chop:
    context_permissive = {
        "market_regime": "TRANSITION",
        "gamma_regime": "POSITIVE_GAMMA",
        "htf_bias": "LONG",
        "allows_counter_trend": True,
    }
    res_perm = classify_trade_priority(candidate, context_permissive)
    assert res_perm["eligible"] is True
    assert res_perm["is_countertrend"] is True
    assert res_perm["priority"] in ("MEDIUM", "LOW")
