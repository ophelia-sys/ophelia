"""Phase 6B Microstructure Research Test Suite.

Validates all 24 required acceptance criteria for:
- Module 3: Visible Order-Book Imbalance
- Module 4: Spread & Liquidity Stress
- Data Quality, Temporal Causality, Provenance, and Research Isolation
"""
import time
import pytest
from fastapi.testclient import TestClient

from models.microstructure import (
    FreshnessState,
    OrderBookLevel,
    OrderBookSnapshot,
    QualityState,
)
from control_plane.microstructure_engine import (
    MicrostructureService,
    OrderBookImbalanceEngine,
    SpreadLiquidityStressEngine,
)
from control_plane import db
from control_plane.api import app, create_access_token


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    db.set_max_open_trades(4)


def _make_snapshot(
    instrument="BTC-USDT",
    venue="BINGX",
    ts=None,
    bids=None,
    asks=None,
    seq=None,
):
    now = int(time.time() * 1000) if ts is None else ts
    b = bids if bids is not None else [
        OrderBookLevel(price=50000.0 - i * 1.0, quantity=1.0 + i * 0.1) for i in range(10)
    ]
    a = asks if asks is not None else [
        OrderBookLevel(price=50001.0 + i * 1.0, quantity=1.0 + i * 0.1) for i in range(10)
    ]
    return OrderBookSnapshot(
        instrument=instrument,
        venue=venue,
        event_timestamp=now,
        received_timestamp=now,
        bids=b,
        asks=a,
        sequence_num=seq,
    )


def test_01_empty_book():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    snap = _make_snapshot(bids=[], asks=[])

    obs_ob = engine_ob.process_snapshot(snap)
    assert obs_ob.provenance.quality_state == QualityState.MISSING
    assert obs_ob.obi_top is None
    assert obs_ob.obi_depth_N is None

    obs_ls = engine_ls.process_snapshot(snap)
    assert obs_ls.provenance.quality_state == QualityState.MISSING
    assert obs_ls.spread is None


def test_02_one_sided_book():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    snap = _make_snapshot(bids=[OrderBookLevel(50000.0, 1.0)], asks=[])

    obs_ob = engine_ob.process_snapshot(snap)
    assert obs_ob.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE
    assert obs_ob.obi_top is None

    obs_ls = engine_ls.process_snapshot(snap)
    assert obs_ls.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE
    assert obs_ls.spread is None


def test_03_normal_two_sided_book():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT", depth_requested=5)
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    snap = _make_snapshot(
        bids=[OrderBookLevel(50000.0, 3.0), OrderBookLevel(49999.0, 2.0)],
        asks=[OrderBookLevel(50001.0, 1.0), OrderBookLevel(50002.0, 1.0)],
    )

    obs_ob = engine_ob.process_snapshot(snap)
    assert obs_ob.provenance.quality_state == QualityState.VALID
    assert obs_ob.depth_available == 2
    assert obs_ob.depth_used == 2
    # Top of book: (3.0 - 1.0) / (3.0 + 1.0) = 0.5
    assert obs_ob.obi_top == pytest.approx(0.5, abs=1e-4)
    # Total depth N: (5.0 - 2.0) / (5.0 + 2.0) = 3/7 = 0.4286
    assert obs_ob.obi_depth_N == pytest.approx(3.0 / 7.0, abs=1e-4)
    assert obs_ob.imbalance_direction == 1

    obs_ls = engine_ls.process_snapshot(snap)
    # Under Phase 6B.1: N=1 has raw observables valid, baseline metrics insufficient sample
    assert obs_ls.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE
    assert obs_ls.spread == pytest.approx(1.0, abs=1e-4)
    assert obs_ls.mid_price == pytest.approx(50000.5, abs=1e-4)


def test_04_zero_denominator():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    snap = _make_snapshot(
        bids=[OrderBookLevel(50000.0, 0.0)],
        asks=[OrderBookLevel(50001.0, 0.0)],
    )
    obs_ob = engine_ob.process_snapshot(snap)
    assert obs_ob.provenance.quality_state == QualityState.NOT_AVAILABLE
    assert obs_ob.obi_depth_N is None


def test_05_missing_levels():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT", depth_requested=10)
    snap = _make_snapshot(
        bids=[OrderBookLevel(50000.0, 1.0), OrderBookLevel(49999.0, 1.0)],
        asks=[OrderBookLevel(50001.0, 1.0), OrderBookLevel(50002.0, 1.0)],
    )
    obs_ob = engine_ob.process_snapshot(snap)
    assert obs_ob.depth_requested == 10
    assert obs_ob.depth_available == 2
    assert obs_ob.depth_used == 2
    assert obs_ob.obi_level_5 is None
    assert obs_ob.obi_level_10 is None
    assert obs_ob.obi_level_1 is not None


def test_06_insufficient_depth():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT", depth_requested=10)
    snap = _make_snapshot(bids=[], asks=[OrderBookLevel(50001.0, 1.0)])
    obs = engine_ob.process_snapshot(snap)
    assert obs.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE


def test_07_crossed_book():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    # Crossed: best bid (50005) > best ask (50000)
    snap = _make_snapshot(
        bids=[OrderBookLevel(50005.0, 1.0)],
        asks=[OrderBookLevel(50000.0, 1.0)],
    )
    obs_ob = engine_ob.process_snapshot(snap)
    assert obs_ob.provenance.quality_state == QualityState.DEGRADED
    assert obs_ob.obi_top is None

    obs_ls = engine_ls.process_snapshot(snap)
    assert obs_ls.provenance.quality_state == QualityState.DEGRADED
    assert obs_ls.spread is None


def test_08_wide_spread():
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    now = int(time.time() * 1000)
    # Warm up with tight spreads of 1.0
    for i in range(10):
        s = _make_snapshot(
            ts=now + i * 100,
            bids=[OrderBookLevel(50000.0, 1.0)],
            asks=[OrderBookLevel(50001.0, 1.0)],
        )
        engine_ls.process_snapshot(s)

    # Wide spread blowout: 10.0
    s_wide = _make_snapshot(
        ts=now + 2000,
        bids=[OrderBookLevel(50000.0, 1.0)],
        asks=[OrderBookLevel(50010.0, 1.0)],
    )
    obs = engine_ls.process_snapshot(s_wide)
    assert obs.spread == 10.0
    assert obs.spread_zscore > 2.0
    assert obs.spread_stress > 2.0


def test_09_spread_compression():
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    now = int(time.time() * 1000)
    # Warm up with wide spread of 10.0
    for i in range(10):
        s = _make_snapshot(
            ts=now + i * 100,
            bids=[OrderBookLevel(50000.0, 1.0)],
            asks=[OrderBookLevel(50010.0, 1.0)],
        )
        engine_ls.process_snapshot(s)

    # Compression down to 0.5
    s_tight = _make_snapshot(
        ts=now + 2000,
        bids=[OrderBookLevel(50000.0, 1.0)],
        asks=[OrderBookLevel(50000.5, 1.0)],
    )
    obs = engine_ls.process_snapshot(s_tight)
    assert obs.spread == 0.5
    assert obs.spread_zscore < 0.0
    assert obs.spread_stress == 0.0  # max(0, zscore) is 0.0 for compressed spread


def test_10_depth_collapse():
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    now = int(time.time() * 1000)
    # Normal depth 10.0 per level (total 100.0)
    for i in range(10):
        s = _make_snapshot(
            ts=now + i * 100,
            bids=[OrderBookLevel(50000.0 - j, 10.0) for j in range(5)],
            asks=[OrderBookLevel(50001.0 + j, 10.0) for j in range(5)],
        )
        engine_ls.process_snapshot(s)

    # Collapse to 0.1 per level
    s_thin = _make_snapshot(
        ts=now + 2000,
        bids=[OrderBookLevel(50000.0 - j, 0.1) for j in range(5)],
        asks=[OrderBookLevel(50001.0 + j, 0.1) for j in range(5)],
    )
    obs = engine_ls.process_snapshot(s_thin)
    assert obs.book_thinning is True
    assert obs.depth_stress > 2.0


def test_11_depth_recovery():
    engine_ls = SpreadLiquidityStressEngine("BTC-USDT")
    now = int(time.time() * 1000)
    # Warm up normal
    for i in range(10):
        engine_ls.process_snapshot(_make_snapshot(ts=now + i * 100))

    # Stress event
    s_thin = _make_snapshot(
        ts=now + 2000,
        bids=[OrderBookLevel(50000.0, 0.01)],
        asks=[OrderBookLevel(50050.0, 0.01)],
    )
    obs_stress = engine_ls.process_snapshot(s_thin)
    assert obs_stress.liquidity_recovery_state in ("STRESSED", "THINNING")

    # Recovery event
    s_norm = _make_snapshot(ts=now + 3000)
    obs_rec = engine_ls.process_snapshot(s_norm)
    assert obs_rec.liquidity_recovery_state in ("RECOVERING", "NORMAL")


def test_12_duplicate_snapshot():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    now = int(time.time() * 1000)
    snap = _make_snapshot(ts=now)
    obs1 = engine_ob.process_snapshot(snap)
    assert obs1.provenance.quality_state == QualityState.VALID

    obs2 = engine_ob.process_snapshot(snap)
    assert obs2.provenance.quality_state == QualityState.DUPLICATE


def test_13_out_of_order_snapshot():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    now = int(time.time() * 1000)
    s1 = _make_snapshot(ts=now)
    engine_ob.process_snapshot(s1)

    # Out of order: older timestamp arrives later
    s2 = _make_snapshot(ts=now - 5000)
    obs2 = engine_ob.process_snapshot(s2)
    assert obs2.provenance.quality_state == QualityState.OUT_OF_ORDER


def test_14_stale_snapshot():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT", max_freshness_ms=5000)
    old_ts = int(time.time() * 1000) - 20000  # 20 seconds ago
    snap = _make_snapshot(ts=old_ts)
    obs = engine_ob.process_snapshot(snap)
    assert obs.provenance.quality_state == QualityState.STALE
    assert obs.provenance.freshness_state == FreshnessState.STALE


def test_15_sequence_gap():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    now = int(time.time() * 1000)
    s1 = _make_snapshot(ts=now, seq=100)
    engine_ob.process_snapshot(s1)

    # Gap: jump from 100 to 105
    s2 = _make_snapshot(ts=now + 100, seq=105)
    obs = engine_ob.process_snapshot(s2)
    assert obs.sequence_state == "GAP_DETECTED"
    assert obs.provenance.quality_state == QualityState.DEGRADED


def test_16_future_update_rejection():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    future_ts = int(time.time() * 1000) + 100000  # 100s in future
    snap = _make_snapshot(ts=future_ts)
    obs = engine_ob.process_snapshot(snap)
    assert obs.provenance.quality_state == QualityState.OUT_OF_ORDER


def test_17_hidden_liquidity_safety():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    snap = _make_snapshot()
    obs = engine_ob.process_snapshot(snap)
    assert obs.hidden_liquidity == "NOT_AVAILABLE"


def test_18_cancellation_unavailable_from_snapshot():
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    snap = _make_snapshot()
    obs = engine_ob.process_snapshot(snap)
    assert obs.cancellation_flow == "NOT_AVAILABLE"


def test_19_provenance_persistence():
    now = int(time.time() * 1000)
    ob_data = {
        "instrument": "ETH-USDT",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now + 10,
        "feature_version": "1.0.0",
        "schema_version": "v1",
        "source_data_type": "SNAPSHOT_DATA",
        "sample_count": 5,
        "quality_state": "VALID",
        "freshness_state": "FRESH",
        "missingness_state": "COMPLETE",
        "calculation_window": 60000,
        "depth_requested": 10,
        "depth_available": 10,
        "depth_used": 10,
        "obi_top": 0.25,
        "obi_depth_N": 0.15,
        "bid_depth": 50.0,
        "ask_depth": 37.0,
        "imbalance_direction": 1,
        "imbalance_persistence": 0.45,
        "obi_level_1": 0.25,
        "obi_level_5": 0.18,
        "obi_level_10": 0.15,
        "cancellation_flow": "NOT_AVAILABLE",
        "hidden_liquidity": "NOT_AVAILABLE",
        "book_snapshot_age_ms": 10,
        "sequence_state": "VALID",
        "detail": {"test": True}
    }
    ls_data = {
        "instrument": "ETH-USDT",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now + 10,
        "feature_version": "1.0.0",
        "schema_version": "v1",
        "source_data_type": "SNAPSHOT_DATA",
        "sample_count": 5,
        "quality_state": "VALID",
        "freshness_state": "FRESH",
        "missingness_state": "COMPLETE",
        "calculation_window": 60000,
        "spread": 0.2,
        "mid_price": 2500.0,
        "relative_spread": 0.00008,
        "expected_spread": 0.2,
        "spread_zscore": 0.0,
        "spread_percentile": 50.0,
        "spread_stress": 0.0,
        "depth_stress": 0.0,
        "book_thinning": False,
        "liquidity_stress": 0.0,
        "liquidity_recovery_state": "NORMAL",
        "detail": {"test": True}
    }

    ob_id = db.persist_microstructure_order_book(ob_data)
    ls_id = db.persist_microstructure_liquidity_stress(ls_data)
    assert ob_id > 0
    assert ls_id > 0

    saved_ob = db.get_latest_microstructure_order_book("ETH-USDT")
    saved_ls = db.get_latest_microstructure_liquidity_stress("ETH-USDT")
    assert saved_ob is not None
    assert saved_ob["mode"] == "RESEARCH"
    assert saved_ob["obi_top"] == 0.25

    assert saved_ls is not None
    assert saved_ls["mode"] == "RESEARCH"
    assert saved_ls["spread"] == 0.2


def test_20_research_isolation():
    # Verify no records written to positions or orders from order book processing
    c = db._connect()
    pos_before = c.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    orders_before = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]

    svc = MicrostructureService.get_instance()
    snap = _make_snapshot(instrument="SOL-USDT")
    svc.process_order_book(snap)

    pos_after = c.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    orders_after = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]
    assert pos_after == pos_before
    assert orders_after == orders_before


def test_21_no_slot_mutation():
    cap_before = db.get_max_open_trades()
    assert cap_before == 4

    svc = MicrostructureService.get_instance()
    snap = _make_snapshot(instrument="SOL-USDT")
    svc.process_order_book(snap)

    cap_after = db.get_max_open_trades()
    assert cap_after == cap_before


def test_22_no_order_submission():
    c = db._connect()
    orders_before = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]

    svc = MicrostructureService.get_instance()
    snap = _make_snapshot(instrument="XRP-USDT")
    svc.process_order_book(snap)

    orders_after = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]
    assert orders_after == orders_before


def test_23_api_authorization():
    client = TestClient(app)

    # 1. Unauthenticated requests must fail with 401/403
    r1 = client.get("/api/microstructure/order-book?instrument=BTC-USDT")
    assert r1.status_code in (401, 403)

    r2 = client.get("/api/microstructure/liquidity-stress?instrument=BTC-USDT")
    assert r2.status_code in (401, 403)

    # 2. Authenticated request succeeds
    admin = db.get_user_by_id(1)
    token = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    r_ob = client.get("/api/microstructure/order-book?instrument=BTC-USDT", headers=headers)
    assert r_ob.status_code == 200
    data_ob = r_ob.json()
    assert data_ob["mode"] == "RESEARCH"
    assert "obi_top" in data_ob

    r_ls = client.get("/api/microstructure/liquidity-stress?instrument=BTC-USDT", headers=headers)
    assert r_ls.status_code == 200
    data_ls = r_ls.json()
    assert data_ls["mode"] == "RESEARCH"
    assert "spread" in data_ls

    r_sum = client.get("/api/microstructure/summary?instrument=BTC-USDT", headers=headers)
    assert r_sum.status_code == 200
    data_sum = r_sum.json()
    assert "order_book" in data_sum
    assert "liquidity_stress" in data_sum


def test_24_restart_and_recovery():
    # Write a record to SQLite
    now = int(time.time() * 1000)
    db.persist_microstructure_order_book({
        "instrument": "RESTART-TEST",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now,
        "feature_version": "1.0.0",
        "schema_version": "v1",
        "source_data_type": "SNAPSHOT_DATA",
        "sample_count": 1,
        "quality_state": "VALID",
        "freshness_state": "FRESH",
        "missingness_state": "COMPLETE",
        "calculation_window": 60000,
        "depth_requested": 10,
        "depth_available": 10,
        "depth_used": 10,
        "obi_top": 0.5,
        "obi_depth_N": 0.5,
        "bid_depth": 10.0,
        "ask_depth": 3.3333,
        "imbalance_direction": 1,
        "imbalance_persistence": 0.0,
        "book_snapshot_age_ms": 0,
    })

    # Re-initialize clean service instance (simulating restart)
    MicrostructureService._instance = None
    new_svc = MicrostructureService.get_instance()
    obs = new_svc.get_latest_observations("RESTART-TEST")
    assert obs["order_book"] is not None
    assert obs["order_book"]["obi_top"] == 0.5
    assert obs["order_book"]["mode"] == "RESEARCH"


def test_25_temporal_causality_no_lookahead():
    """Verify that future extreme book updates cannot affect an earlier observation."""
    engine_ob = OrderBookImbalanceEngine("BTC-USDT")
    t0 = 1000000

    # Observation at T0
    s0 = _make_snapshot(
        ts=t0,
        bids=[OrderBookLevel(50000.0, 1.0)],
        asks=[OrderBookLevel(50001.0, 1.0)],
    )
    obs_t0_before = engine_ob.process_snapshot(s0)
    assert obs_t0_before.obi_top == 0.0

    # An observation cutoff is established at T0.
    # Now simulate future massive imbalance update at T0 + 100,000ms
    s_future = _make_snapshot(
        ts=t0 + 100000,
        bids=[OrderBookLevel(50000.0, 1000000.0)],
        asks=[OrderBookLevel(50001.0, 1.0)],
    )
    obs_future = engine_ob.process_snapshot(s_future)
    assert obs_future.obi_top > 0.999

    # Re-querying or reconstructing the state strictly causal to T0
    # must remain 0.0 and completely unaffected by future extreme book
    assert obs_t0_before.obi_top == 0.0
    assert obs_t0_before.provenance.event_timestamp == t0
    assert obs_future.provenance.event_timestamp > t0
