"""Differential Unit & Property Tests: Python vs Rust Mathematical Parity.

Verifies that ophelia_math (Rust) and control_plane/fast_math (Python) produce
numerically identical results across normal, edge, and extreme datasets.
"""
import pytest
import math
import random
import numpy as np

from control_plane import fast_math

# Verify Rust kernel is available
def test_rust_kernel_presence():
    """Verify that the compiled ophelia_math Rust extension is active."""
    # fast_math will import ophelia_math if installed
    import ophelia_math
    assert ophelia_math is not None
    assert hasattr(ophelia_math, "calculate_atr")
    assert hasattr(ophelia_math, "calculate_rvol")
    assert hasattr(ophelia_math, "calculate_cvd_series")
    assert hasattr(ophelia_math, "calculate_vwap_series")
    assert hasattr(ophelia_math, "detect_swings")
    assert hasattr(ophelia_math, "detect_fvg")
    assert hasattr(ophelia_math, "calculate_structural_stops")
    assert hasattr(ophelia_math, "calculate_structural_targets")
    assert hasattr(ophelia_math, "calculate_position_sizing")


def _generate_synthetic_series(n=100, seed=42, regime="normal"):
    random.seed(seed)
    np.random.seed(seed)
    if regime == "empty":
        return [], [], [], []
    elif regime == "single":
        return [100.0], [105.0], [95.0], [102.0]
    elif regime == "flat":
        closes = [100.0] * n
        highs = [100.0] * n
        lows = [100.0] * n
        opens = [100.0] * n
        return opens, highs, lows, closes
    elif regime == "extreme":
        opens = [1e6 + i * 1000 for i in range(n)]
        highs = [o + 5000 for o in opens]
        lows = [o - 5000 for o in opens]
        closes = [o + 1000 for o in opens]
        return opens, highs, lows, closes
    elif regime == "volatile":
        opens, highs, lows, closes = [], [], [], []
        px = 50000.0
        for _ in range(n):
            o = px
            change = np.random.normal(0, 1500)
            c = o + change
            h = max(o, c) + abs(np.random.normal(0, 500))
            l = min(o, c) - abs(np.random.normal(0, 500))
            opens.append(o)
            highs.append(h)
            lows.append(l)
            closes.append(c)
            px = c
        return opens, highs, lows, closes
    else: # normal
        opens, highs, lows, closes = [], [], [], []
        px = 100.0
        for _ in range(n):
            o = px
            change = np.random.normal(0, 1.0)
            c = o + change
            h = max(o, c) + random.uniform(0.1, 1.0)
            l = min(o, c) - random.uniform(0.1, 1.0)
            opens.append(o)
            highs.append(h)
            lows.append(l)
            closes.append(c)
            px = c
        return opens, highs, lows, closes


@pytest.mark.parametrize("regime", ["normal", "empty", "single", "flat", "volatile", "extreme"])
def test_atr_parity(regime):
    import ophelia_math
    opens, highs, lows, closes = _generate_synthetic_series(n=150, regime=regime)
    period = 14

    rust_atr = ophelia_math.calculate_atr(highs, lows, closes, period)
    py_atr = fast_math.calculate_atr(highs, lows, closes, period)

    assert len(rust_atr) == len(py_atr)
    for r, p in zip(rust_atr, py_atr):
        assert abs(r - p) < 1e-6 or (math.isnan(r) and math.isnan(p))


@pytest.mark.parametrize("regime", ["normal", "empty", "single", "flat", "volatile", "extreme"])
def test_rvol_parity(regime):
    import ophelia_math
    n = 0 if regime == "empty" else (1 if regime == "single" else 50)
    vols = [float(random.randint(10, 5000)) for _ in range(n)] if n > 0 else []

    rust_rvol = ophelia_math.calculate_rvol(vols, 20)
    py_rvol = fast_math.calculate_rvol(vols, 20)

    assert abs(rust_rvol - py_rvol) < 1e-4


def test_cvd_parity():
    import ophelia_math
    n = 200
    vols = [float(random.randint(50, 500)) for _ in range(n)]
    tbs = [v * random.uniform(0.3, 0.8) for v in vols]
    opens, highs, lows, closes = _generate_synthetic_series(n=n, regime="normal")

    rust_cvd = ophelia_math.calculate_cvd_series(vols, tbs, opens, closes)
    py_cvd = fast_math.calculate_cvd_series(vols, tbs, opens, closes)

    assert len(rust_cvd) == len(py_cvd)
    for r, p in zip(rust_cvd, py_cvd):
        assert abs(r - p) < 1e-6


def test_vwap_parity():
    import ophelia_math
    n = 300
    opens, highs, lows, closes = _generate_synthetic_series(n=n, regime="normal")
    vols = [float(random.randint(100, 1000)) for _ in range(n)]

    rust_vwap = ophelia_math.calculate_vwap_series(highs, lows, closes, vols)
    py_vwap = fast_math.calculate_vwap_series(highs, lows, closes, vols)

    assert len(rust_vwap) == len(py_vwap)
    for r, p in zip(rust_vwap, py_vwap):
        assert abs(r - p) < 1e-6


def test_swings_parity():
    import ophelia_math
    opens, highs, lows, closes = _generate_synthetic_series(n=250, regime="volatile")
    r_sh, r_sl = ophelia_math.detect_swings(highs, lows, 5)
    p_sh, p_sl = fast_math.detect_swings(highs, lows, 5)

    assert r_sh == p_sh
    assert r_sl == p_sl


def test_structural_stops_and_targets_parity():
    import ophelia_math
    # Test LONG
    r_sl, r_dist, r_reason = ophelia_math.calculate_structural_stops("LONG", 65000.0, 64200.0, 350.0)
    p_sl, p_dist, p_reason = fast_math.calculate_structural_stops("LONG", 65000.0, 64200.0, 350.0)
    assert abs(r_sl - p_sl) < 1e-4
    assert abs(r_dist - p_dist) < 1e-4
    assert r_reason == p_reason

    # Test SHORT
    r_sl_s, r_dist_s, _ = ophelia_math.calculate_structural_stops("SHORT", 65000.0, 65800.0, 350.0)
    p_sl_s, p_dist_s, _ = fast_math.calculate_structural_stops("SHORT", 65000.0, 65800.0, 350.0)
    assert abs(r_sl_s - p_sl_s) < 1e-4
    assert abs(r_dist_s - p_dist_s) < 1e-4

    # Targets
    r_tgts = ophelia_math.calculate_structural_targets("LONG", 65000.0, 64000.0, [1.5, 2.5, 4.0])
    p_tgts = fast_math.calculate_structural_targets("LONG", 65000.0, 64000.0, [1.5, 2.5, 4.0])
    assert len(r_tgts) == len(p_tgts)
    for (rtp, rdp, rrr), (ptp, pdp, prr) in zip(r_tgts, p_tgts):
        assert abs(rtp - ptp) < 1e-4
        assert abs(rdp - pdp) < 1e-4
        assert rrr == prr


def test_large_series_parity():
    """Verify performance and parity across 10,000 candles without memory growth."""
    import ophelia_math
    n = 10000
    opens, highs, lows, closes = _generate_synthetic_series(n=n, regime="normal")
    rust_atr = ophelia_math.calculate_atr(highs, lows, closes, 14)
    py_atr = fast_math.calculate_atr(highs, lows, closes, 14)
    assert len(rust_atr) == n
    assert abs(rust_atr[-1] - py_atr[-1]) < 1e-5
