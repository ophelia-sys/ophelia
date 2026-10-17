"""Unit tests for Cross-Venue Basis Engine and Execution Translation.

Layer: tests/test_cross_venue_basis.py
"""
import time
import pytest
from models.instrument import CanonicalInstrument, MappingStatus
from control_plane.cross_venue_basis import (
    CrossVenueBasisEngine,
    CrossVenueBasisSnapshot,
)


def test_basis_engine_aligned():
    engine = CrossVenueBasisEngine(history_size=50)
    now_ms = 1700000000000
    snap = engine.compute_basis(
        symbol="BTC",
        binance_price=86000.0,
        bingx_price=86010.0,  # 0.0116% diff
        binance_ts_ms=now_ms - 500,
        bingx_ts_ms=now_ms - 400,
        now_ms=now_ms,
    )
    assert snap.symbol == "BTC"
    assert snap.basis_abs == 10.0
    assert snap.basis_pct == pytest.approx(0.0116, abs=0.001)
    assert snap.state == "ALIGNED"
    assert snap.binance_data_age_ms == 500
    assert snap.bingx_data_age_ms == 400


def test_basis_engine_states():
    engine = CrossVenueBasisEngine(history_size=50)
    now_ms = 1700000000000

    # Normal basis (0.10%)
    snap_norm = engine.compute_basis("ETH", 3000.0, 3003.0, now_ms - 100, now_ms - 100, now_ms=now_ms)
    assert snap_norm.state == "NORMAL_BASIS"

    # Elevated basis (0.30%)
    snap_elev = engine.compute_basis("SOL", 150.0, 150.45, now_ms - 100, now_ms - 100, now_ms=now_ms)
    assert snap_elev.state == "ELEVATED_BASIS"

    # Dislocated basis (0.80%)
    snap_disloc = engine.compute_basis("XRP", 1.00, 1.008, now_ms - 100, now_ms - 100, now_ms=now_ms)
    assert snap_disloc.state == "DISLOCATED"

    # Stale data (>10s)
    snap_stale = engine.compute_basis("BTC", 86000.0, 86010.0, now_ms - 15000, now_ms - 15000, now_ms=now_ms)
    assert snap_stale.state == "STALE"

    # Not available (price <= 0)
    snap_na = engine.compute_basis("BTC", 0.0, 86010.0, now_ms, now_ms, now_ms=now_ms)
    assert snap_na.state == "NOT_AVAILABLE"


def test_rolling_zscore_computation():
    engine = CrossVenueBasisEngine(history_size=50)
    base_ts = 1700000000000
    # Feed 15 steady observations around 0.02%
    for i in range(15):
        engine.compute_basis("BTC", 100.0, 100.02, base_ts + i * 1000, base_ts + i * 1000, now_ms=base_ts + i * 1000)

    # Now inject a deviation to 0.15%
    snap = engine.compute_basis("BTC", 100.0, 100.15, base_ts + 15000, base_ts + 15000, now_ms=base_ts + 15000)
    assert snap.basis_zscore is not None
    assert snap.basis_zscore > 1.0  # Significant upward excursion


def test_translate_signal_to_execution_approved():
    engine = CrossVenueBasisEngine.get_instance()
    now_ms = int(time.time() * 1000)
    engine.compute_basis("BTC", 86000.0, 86015.0, now_ms - 200, now_ms - 200, now_ms=now_ms)

    inst = CanonicalInstrument.from_dict({
        "display_symbol": "BTC",
        "canonical_instrument_id": "CRYPTO:BTC-USDT",
        "bingx_symbol": "BTC-USDT",
        "bingx_precision": 1,
        "quantity_precision": 4,
        "bingx_min_quantity": 0.001,
        "bingx_min_notional": 5.0,
        "bingx_status": "TRADABLE",
        "mapping_status": "TRADABLE_BOTH",
    })

    res = engine.translate_signal_to_execution(
        signal_price=86000.0,
        canonical_inst=inst,
        intended_quantity=0.01,
        side="BUY"
    )
    assert res["status"] == "APPROVED"
    assert res["is_valid"] is True
    assert res["bingx_execution_price"] == 86015.0  # Fills against BingX execution price
    assert res["notional"] == 860.15


def test_translate_signal_to_execution_rejected_on_dislocation():
    engine = CrossVenueBasisEngine.get_instance()
    now_ms = int(time.time() * 1000)
    # 2% dislocation between Binance and BingX
    engine.compute_basis("BTC", 86000.0, 87720.0, now_ms - 200, now_ms - 200, now_ms=now_ms)

    inst = CanonicalInstrument.from_dict({
        "display_symbol": "BTC",
        "canonical_instrument_id": "CRYPTO:BTC-USDT",
        "bingx_symbol": "BTC-USDT",
        "bingx_precision": 1,
        "quantity_precision": 4,
        "bingx_min_quantity": 0.001,
        "bingx_min_notional": 5.0,
        "bingx_status": "TRADABLE",
        "mapping_status": "TRADABLE_BOTH",
    })

    res = engine.translate_signal_to_execution(
        signal_price=86000.0,
        canonical_inst=inst,
        intended_quantity=0.01,
        side="BUY"
    )
    assert res["status"] == "REJECTED"
    assert res["is_valid"] is False
    assert any("DISLOCATED" in r for r in res["reasons"])
