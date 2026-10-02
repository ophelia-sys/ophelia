"""Phase 6C Microstructure Research Test Suite.

Validates all 25 required acceptance criteria for:
- Phase 6B.1 Statistical Baseline Correction (raw observables on N=1 vs None baseline metrics until N>=5)
- Module 5: Empirical Price Impact (Kyle-inspired, strict forward causality, no lookahead, stability, asymmetry)
- Module 6: Toxicity & Adverse Flow (VPIN-inspired, interpretable submetrics, observable behavior only)
- Data Quality, Temporal Causality, Provenance, and Research Isolation
"""
import time
import pytest
from fastapi.testclient import TestClient

from models.microstructure import (
    FreshnessState,
    OrderBookLevel,
    OrderBookSnapshot,
    PriceImpactObservation,
    QualityState,
    ToxicityObservation,
    TradeTick,
)
from control_plane.microstructure_engine import (
    MicrostructureService,
    OrderBookImbalanceEngine,
    PriceImpactEngine,
    SpreadLiquidityStressEngine,
    ToxicityEngine,
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
    now = int(time.time() * 1000)
    if ts is not None and ts < 1_000_000_000_000:
        event_ts = now - 10000 + ts
    else:
        event_ts = ts if ts is not None else now
    b = bids if bids is not None else [
        OrderBookLevel(price=50000.0 - i * 0.5, quantity=1.0 + i * 0.2) for i in range(10)
    ]
    a = asks if asks is not None else [
        OrderBookLevel(price=50000.5 + i * 0.5, quantity=1.0 + i * 0.2) for i in range(10)
    ]
    return OrderBookSnapshot(
        instrument=instrument,
        venue=venue,
        event_timestamp=event_ts,
        received_timestamp=now,
        bids=b,
        asks=a,
        sequence_num=seq,
    )


def _make_tick(
    instrument="BTC-USDT",
    venue="BINGX",
    ts=None,
    price=50000.0,
    qty=1.0,
    aggressor="BUY",
    trade_id=None,
):
    now = int(time.time() * 1000)
    if ts is not None and ts < 1_000_000_000_000:
        event_ts = now - 10000 + ts
    else:
        event_ts = ts if ts is not None else now
    return TradeTick(
        instrument=instrument,
        venue=venue,
        event_timestamp=event_ts,
        received_timestamp=now,
        price=price,
        quantity=qty,
        aggressor_side=aggressor,
        trade_id=trade_id,
    )


# ==============================================================================
# PHASE 6B.1 STATISTICAL BASELINE CORRECTION TESTS
# ==============================================================================

def test_01_phase6b1_order_book_persistence_null_at_n1():
    """Phase 6B.1: OBI persistence must return None on N=1 until N >= 5."""
    engine = OrderBookImbalanceEngine(instrument="BTC-USDT", min_persistence_samples=5)
    snap = _make_snapshot(ts=1000)
    obs = engine.process_snapshot(snap)

    assert obs.obi_top is not None
    assert obs.bid_depth > 0.0
    assert obs.ask_depth > 0.0
    # Baseline-derived persistence must be None, NOT 0.0
    assert obs.imbalance_persistence is None


def test_02_phase6b1_spread_liquidity_null_baseline_at_n1():
    """Phase 6B.1: Raw observables valid at N=1, baseline metrics strictly None and NOT_AVAILABLE."""
    engine = SpreadLiquidityStressEngine(instrument="BTC-USDT", min_baseline_samples=5)
    snap = _make_snapshot(ts=1000)
    obs = engine.process_snapshot(snap)

    # Raw observables exist immediately
    assert obs.spread == pytest.approx(0.5, rel=1e-3)
    assert obs.mid_price == pytest.approx(50000.25, rel=1e-3)
    assert obs.relative_spread is not None
    assert obs.relative_spread > 0.0

    # Baseline-derived metrics MUST be None / NOT_AVAILABLE
    assert obs.expected_spread is None
    assert obs.spread_zscore is None
    assert obs.spread_percentile is None
    assert obs.spread_stress is None
    assert obs.depth_stress is None
    assert obs.book_thinning is None
    assert obs.liquidity_stress is None
    assert obs.liquidity_recovery_state == "NOT_AVAILABLE"
    assert obs.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE


def test_03_phase6b1_spread_baseline_computed_at_n5():
    """Phase 6B.1: After 5 snapshots, baseline metrics compute from prior distribution."""
    engine = SpreadLiquidityStressEngine(instrument="BTC-USDT", min_baseline_samples=5)
    for i in range(5):
        engine.process_snapshot(_make_snapshot(ts=1000 + i * 100))

    # 6th snapshot has 5 prior observations
    obs6 = engine.process_snapshot(_make_snapshot(ts=1600))
    assert obs6.expected_spread is not None
    assert obs6.spread_zscore is not None
    assert obs6.spread_percentile is not None
    assert obs6.spread_stress is not None
    assert obs6.depth_stress is not None
    assert obs6.book_thinning is not None
    assert obs6.liquidity_stress is not None
    assert obs6.liquidity_recovery_state in ("NORMAL", "THINNING", "STRESSED", "RECOVERING")
    assert obs6.provenance.quality_state == QualityState.VALID


def test_04_phase6b1_obi_persistence_computed_at_n5():
    """Phase 6B.1: After 5 snapshots, imbalance persistence is calculated."""
    engine = OrderBookImbalanceEngine(instrument="BTC-USDT", min_persistence_samples=5)
    for i in range(5):
        engine.process_snapshot(_make_snapshot(ts=1000 + i * 100))

    obs = engine.process_snapshot(_make_snapshot(ts=1600))
    assert obs.imbalance_persistence is not None
    assert isinstance(obs.imbalance_persistence, float)


# ==============================================================================
# PHASE 6C MODULE 5: EMPIRICAL PRICE IMPACT TESTS
# ==============================================================================

def test_05_price_impact_strict_forward_causality():
    """Module 5: Return horizon begins strictly AFTER the flow observation."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=3)

    # Tick 1: flow at t=1000, price=50000.0
    engine.process_tick(_make_tick(ts=1000, price=50000.0, qty=1.0, aggressor="BUY"))
    # Tick 2: arrives at t=1001, price=50010.0.
    # Evaluated pair: flow from Tick 1 (+1.0), forward return = (50010 - 50000)/50000 = +0.0002
    engine.process_tick(_make_tick(ts=1001, price=50010.0, qty=2.0, aggressor="BUY"))
    assert len(engine.evaluated_pairs) == 1
    flow, ret, qty, is_buy = engine.evaluated_pairs[0]
    assert flow == 1.0
    assert ret == pytest.approx(0.0002, rel=1e-4)


def test_06_price_impact_no_future_leakage():
    """Module 5: Future price movement beyond forward horizon does not contaminate historical pair."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=2)

    engine.process_tick(_make_tick(ts=1000, price=50000.0, qty=1.0, aggressor="BUY"))
    engine.process_tick(_make_tick(ts=1001, price=50010.0, qty=1.0, aggressor="BUY"))
    # Tick 1 forward return is evaluated
    pair1_ret = engine.evaluated_pairs[0][1]

    # Extreme price spike in Tick 3 (t=1002, price=99999.0)
    engine.process_tick(_make_tick(ts=1002, price=99999.0, qty=1.0, aggressor="BUY"))

    # Tick 1 pair return must remain strictly (50010 - 50000)/50000 and unchanged
    assert engine.evaluated_pairs[0][1] == pair1_ret
    assert engine.evaluated_pairs[0][1] == pytest.approx(0.0002, rel=1e-4)


def test_07_price_impact_minimum_sample_requirement():
    """Module 5: Impact metrics return None when sample count < min_sample_size."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=20)
    for i in range(10):
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=50000.0 + i, qty=1.0, aggressor="BUY"))

    assert obs.impact_coefficient is None
    assert obs.impact_stability is None
    assert obs.impact_asymmetry is None
    assert obs.buy_impact is None
    assert obs.sell_impact is None
    assert obs.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE


def test_08_price_impact_kyle_lambda_and_direction():
    """Module 5: Buyer aggressive flow followed by positive forward returns produces positive lambda."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=20)

    # 35 ticks alternating buy/sell with positive correlation to forward price changes
    p = 50000.0
    for i in range(35):
        side = "BUY" if i % 2 == 0 else "SELL"
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=p, qty=1.0, aggressor=side))
        dp = 2.0 if side == "BUY" else -2.0
        p += dp

    assert obs.impact_coefficient is not None
    assert obs.impact_coefficient > 0.0
    assert obs.impact_direction == 1
    assert obs.provenance.quality_state == QualityState.VALID


def test_09_price_impact_stability_r2():
    """Module 5: Highly correlated flow-return produces high stability R^2."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=10, min_side_samples=3)

    p = 50000.0
    for i in range(25):
        side = "BUY" if i % 2 == 0 else "SELL"
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=p, qty=1.0, aggressor=side))
        dp = 5.0 if side == "BUY" else -5.0
        p += dp

    assert obs.impact_stability is not None
    assert 0.0 <= obs.impact_stability <= 1.0
    assert obs.impact_stability > 0.5


def test_10_price_impact_buy_and_sell_separation():
    """Module 5: Separately estimates buy-flow and sell-flow impact."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=10, min_side_samples=5)

    p = 50000.0
    for i in range(25):
        side = "BUY" if i % 2 == 0 else "SELL"
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=p, qty=1.0, aggressor=side))
        dp = 4.0 if side == "BUY" else -2.0  # Asymmetric price reaction
        p += dp

    assert obs.buy_impact is not None
    assert obs.sell_impact is not None


def test_11_price_impact_asymmetry_undersampled_none():
    """Module 5: When one side lacks min_side_samples, asymmetry returns None."""
    engine = PriceImpactEngine(instrument="BTC-USDT", horizon_steps=1, min_sample_size=10, min_side_samples=5)

    # 15 buy ticks, 0 sell ticks
    p = 50000.0
    for i in range(15):
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=p, qty=1.0, aggressor="BUY"))
        p += 1.0

    assert obs.buy_impact is not None
    assert obs.sell_impact is None
    assert obs.impact_asymmetry is None


def test_12_price_impact_duplicate_rejection():
    """Module 5: Duplicate ticks rejected with DUPLICATE quality state."""
    engine = PriceImpactEngine(instrument="BTC-USDT")
    tick = _make_tick(trade_id="TR-12345", ts=1000)
    engine.process_tick(tick)
    dup_obs = engine.process_tick(tick)

    assert dup_obs.provenance.quality_state == QualityState.DUPLICATE
    assert dup_obs.impact_coefficient is None


def test_13_price_impact_future_timestamp_rejected():
    """Module 5: Future timestamps > 60s ahead rejected."""
    engine = PriceImpactEngine(instrument="BTC-USDT")
    now_ms = int(time.time() * 1000)
    tick = _make_tick(ts=now_ms + 120000)
    obs = engine.process_tick(tick)

    assert obs.provenance.quality_state == QualityState.OUT_OF_ORDER
    assert obs.impact_coefficient is None


def test_14_price_impact_out_of_order_rejected():
    """Module 5: Out of order timestamps rejected."""
    engine = PriceImpactEngine(instrument="BTC-USDT")
    engine.process_tick(_make_tick(ts=2000))
    obs = engine.process_tick(_make_tick(ts=1000))

    assert obs.provenance.quality_state == QualityState.OUT_OF_ORDER


def test_15_price_impact_invalid_qty_price_rejected():
    """Module 5: Zero or negative quantity/price rejected with DEGRADED state."""
    engine = PriceImpactEngine(instrument="BTC-USDT")
    obs1 = engine.process_tick(_make_tick(qty=0.0))
    obs2 = engine.process_tick(_make_tick(price=-10.0))

    assert obs1.provenance.quality_state == QualityState.DEGRADED
    assert obs2.provenance.quality_state == QualityState.DEGRADED


# ==============================================================================
# PHASE 6C MODULE 6: TOXICITY & ADVERSE FLOW TESTS
# ==============================================================================

def test_16_toxicity_submetrics_present():
    """Module 6: Exposes interpretable submetrics first."""
    engine = ToxicityEngine(instrument="BTC-USDT", min_sample_size=5)
    for i in range(8):
        obs = engine.process_tick(
            _make_tick(ts=1000 + i * 100, price=50000.0 + i, qty=1.0, aggressor="BUY"),
            spread_stress_context=1.2,
            depth_stress_context=0.8,
        )

    assert obs.flow_intensity is not None
    assert obs.adverse_price_response is not None
    assert obs.trade_arrival_stress is not None
    assert obs.spread_stress_context == 1.2
    assert obs.depth_stress_context == 0.8
    assert obs.toxicity_metric is not None
    assert obs.methodology_version == "VPIN_INSPIRED_RESEARCH"


def test_17_toxicity_minimum_sample_requirement():
    """Module 6: Minimum sample check returns None/INSUFFICIENT_SAMPLE."""
    engine = ToxicityEngine(instrument="BTC-USDT", min_sample_size=20)
    for i in range(10):
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=50000.0, qty=1.0, aggressor="BUY"))

    assert obs.toxicity_metric is None
    assert obs.toxicity_state == "INSUFFICIENT_SAMPLE"
    assert obs.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE


def test_18_toxicity_vpin_calculation():
    """Module 6: VPIN volume imbalance fraction correctly bounded [0, 1]."""
    engine = ToxicityEngine(instrument="BTC-USDT", min_sample_size=10, num_buckets=5)
    for i in range(20):
        side = "BUY" if i % 2 == 0 else "SELL"
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=50000.0, qty=1.0, aggressor=side))

    assert obs.toxicity_metric is not None
    assert 0.0 <= obs.toxicity_metric <= 1.0


def test_19_toxicity_adverse_price_response():
    """Module 6: Positive net flow with falling prices gives positive adverse price response."""
    engine = ToxicityEngine(instrument="BTC-USDT", min_sample_size=5)
    p = 50000.0
    for i in range(8):
        p -= 10.0  # price falls despite buyer flow
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=p, qty=1.0, aggressor="BUY"))

    assert obs.flow_intensity > 0.0
    # Adverse response should be positive (move was adverse to flow)
    assert obs.adverse_price_response > 0.0


def test_20_toxicity_regime_classification():
    """Module 6: High volume imbalance fraction maps to TOXIC state."""
    engine = ToxicityEngine(instrument="BTC-USDT", min_sample_size=10, num_buckets=5)
    # 25 all-BUY trades -> pure one-sided volume imbalance
    for i in range(25):
        obs = engine.process_tick(_make_tick(ts=1000 + i * 100, price=50000.0 + i, qty=10.0, aggressor="BUY"))

    assert obs.toxicity_metric is not None
    assert obs.toxicity_metric > 0.70
    assert obs.toxicity_state == "TOXIC"


def test_21_toxicity_contextual_stress_preserved():
    """Module 6: Spread and depth stress from Module 4 pass through to toxicity observation."""
    engine = ToxicityEngine(instrument="BTC-USDT", min_sample_size=5)
    obs = engine.process_tick(
        _make_tick(ts=1000),
        spread_stress_context=2.45,
        depth_stress_context=1.85,
    )
    assert obs.spread_stress_context == 2.45
    assert obs.depth_stress_context == 1.85


# ==============================================================================
# API, RESEARCH ISOLATION & PERSISTENCE TESTS
# ==============================================================================

def test_22_api_microstructure_price_impact_and_toxicity_endpoints():
    """API: New endpoints require authentication and return research mode."""
    client = TestClient(app)

    # 1. Unauthenticated fails
    assert client.get("/api/microstructure/price-impact").status_code in (401, 403)
    assert client.get("/api/microstructure/toxicity").status_code in (401, 403)

    # 2. Authenticated succeeds
    admin = db.get_user_by_id(1)
    token = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    r_pi = client.get("/api/microstructure/price-impact?instrument=BTC-USDT", headers=headers)
    assert r_pi.status_code == 200
    assert r_pi.json()["mode"] == "RESEARCH"
    assert "impact_coefficient" in r_pi.json()

    r_tox = client.get("/api/microstructure/toxicity?instrument=BTC-USDT", headers=headers)
    assert r_tox.status_code == 200
    assert r_tox.json()["mode"] == "RESEARCH"
    assert "toxicity_state" in r_tox.json()


def test_23_api_microstructure_summary_all_6_modules():
    """API: Summary endpoint returns Modules 1 through 6."""
    client = TestClient(app)
    admin = db.get_user_by_id(1)
    token = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/microstructure/summary?instrument=BTC-USDT", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "trade_flow" in data
    assert "trade_duration" in data
    assert "order_book" in data
    assert "liquidity_stress" in data
    assert "price_impact" in data
    assert "toxicity" in data
    assert data["mode"] == "RESEARCH"


def test_24_microstructure_research_isolation_zero_orders():
    """Research Isolation: Processing microstructure events must never place orders or alter capacity."""
    c = db._connect()
    orders_before = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]

    svc = MicrostructureService.get_instance()
    for i in range(10):
        svc.process_tick(_make_tick(ts=1000 + i * 100, price=50000.0 + i, qty=1.0, aggressor="BUY"))

    orders_after = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]
    assert orders_after == orders_before


def test_25_db_persistence_and_recovery():
    """DB: Price Impact and Toxicity records persist and can be retrieved."""
    now = int(time.time() * 1000)
    pi_id = db.persist_microstructure_price_impact({
        "instrument": "PERSIST-TEST",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now,
        "impact_coefficient": 0.000123,
        "impact_direction": 1,
        "sample_count": 25,
        "quality_state": "VALID"
    })
    tox_id = db.persist_microstructure_toxicity({
        "instrument": "PERSIST-TEST",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now,
        "toxicity_metric": 0.42,
        "toxicity_state": "NORMAL",
        "sample_count": 25,
        "quality_state": "VALID"
    })
    assert pi_id > 0
    assert tox_id > 0

    saved_pi = db.get_latest_microstructure_price_impact("PERSIST-TEST")
    saved_tox = db.get_latest_microstructure_toxicity("PERSIST-TEST")

    assert saved_pi["impact_coefficient"] == pytest.approx(0.000123, rel=1e-5)
    assert saved_tox["toxicity_metric"] == pytest.approx(0.42, rel=1e-5)
    assert saved_pi["mode"] == "RESEARCH"
    assert saved_tox["mode"] == "RESEARCH"
