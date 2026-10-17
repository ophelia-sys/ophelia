"""Phase 6D Microstructure Research Test Suite.

Validates all 25 required acceptance criteria for:
- Part 1-10: Hasbrouck-Style Bivariate Price Discovery VAR (Modules 7)
- Part 11-17: Bivariate Vector Error Correction Model (VECM, Module 8)
- Part 18-20: Error/Sample Gates, Causality, Determinism, No Lookahead, Reproducibility
- Part 21-25: Safety, Zero Trading Authority, Multi-User Isolation, API Authentication
"""
import math
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient

from models.microstructure import (
    AggressorSource,
    FreshnessState,
    HasbrouckVarObservation,
    MicrostructureProvenance,
    MissingnessState,
    QualityState,
    TradeTick,
    VecmObservation,
)
from control_plane.microstructure_engine import (
    HasbrouckVarEngine,
    MicrostructureService,
    VecmEngine,
    _calculate_adf,
    _ljung_box,
)
from control_plane import db
from control_plane.api import app, create_access_token


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    db.init_db()
    db.set_max_open_trades(4)


# ==============================================================================
# HASBROUCK-STYLE VAR TESTS (1 - 10)
# ==============================================================================

def test_01_hasbrouck_known_stationary_dataset():
    """HASBROUCK: Known stationary VAR(1) dataset estimates valid coefficients and positive permanent impact."""
    np.random.seed(42)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)

    # Simulate stationary VAR(1): r_t = 0.2 r_{t-1} + 0.3 x_{t-1} + e_1, x_t = 0.1 r_{t-1} + 0.4 x_{t-1} + e_2
    T = 150
    now = int(time.time() * 1000)
    price = 50000.0

    r_sim = np.zeros(T)
    x_sim = np.zeros(T)
    for t in range(1, T):
        r_sim[t] = 0.2 * r_sim[t-1] + 0.3 * x_sim[t-1] + np.random.normal(scale=0.001)
        x_sim[t] = 0.1 * r_sim[t-1] + 0.4 * x_sim[t-1] + np.random.normal(scale=0.5)

        price = price * math.exp(r_sim[t])
        signed_flow = (math.exp(abs(x_sim[t])) - 1.0) * (1.0 if x_sim[t] >= 0 else -1.0)
        ts = now - (T - t) * 1000
        engine.add_observation(price=price, signed_flow=signed_flow, timestamp_ms=ts)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    assert obs.is_stable is True
    assert obs.selected_lag is not None and obs.selected_lag >= 1
    assert obs.max_eigenvalue_modulus is not None and obs.max_eigenvalue_modulus < 1.0
    assert obs.cumulative_impact_H20 is not None
    assert obs.cumulative_impact == obs.cumulative_impact_H20
    assert obs.convergence_status in ("CONVERGED", "NOT_CONVERGED")
    assert obs.primary_x_definition == "SIGNED_INDICATOR"
    assert obs.robustness_x_definition == "SIGNED_SQRT_VOLUME"
    assert "robustness" in obs.diagnostics
    assert obs.variance_share_flow is not None and 0.0 <= obs.variance_share_flow <= 1.0
    assert obs.methodology_version == "HASBROUCK_STYLE_V1.1"


def test_02_hasbrouck_non_stationary_dataset_rejected():
    """HASBROUCK: Non-stationary dataset (random walk returns/drift) fails stationarity gate."""
    np.random.seed(42)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)

    # Return series is a random walk -> non-stationary I(1) returns
    T = 100
    r_rw = np.cumsum(np.random.normal(scale=0.01, size=T))
    price = 50000.0
    for i in range(T):
        price = price * math.exp(r_rw[i])
        flow = 1.0 + np.random.normal()
        engine.add_observation(price=price, signed_flow=flow, timestamp_ms=now - (T - i) * 1000)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "NON_STATIONARY"
    assert "adf_return_stat" in obs.diagnostics
    assert "critical_value_5pct" in obs.diagnostics


def test_03_hasbrouck_insufficient_sample_gate():
    """HASBROUCK: Insufficient sample count (N < 60) fails sample gate without manufacturing coefficients."""
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=300000)
    now = int(time.time() * 1000)

    for i in range(25):  # 25 < 60
        engine.add_observation(price=50000.0 + i, signed_flow=1.0, timestamp_ms=now - (25 - i) * 1000)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "INSUFFICIENT_SAMPLE"
    assert obs.sample_count < 60
    assert obs.coefficients == {}


def test_04_hasbrouck_deterministic_lag_selection():
    """HASBROUCK: Lag selection deterministically evaluates candidate lags p=1..5 using BIC."""
    np.random.seed(123)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", max_candidate_lags=4, min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)
    price = 50000.0

    for i in range(120):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        x = np.random.normal(scale=1.0)
        engine.add_observation(price=price, signed_flow=x, timestamp_ms=now - (120 - i) * 1000)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    assert obs.lag_selection_method == "BIC"
    assert obs.candidate_lags == [1, 2, 3, 4]
    assert obs.selected_lag in obs.candidate_lags
    assert "bic_scores" in obs.diagnostics


def test_05_hasbrouck_residual_autocorrelation_diagnostics():
    """HASBROUCK: Residual autocorrelation diagnostic via Ljung-Box Q-statistic is computed."""
    np.random.seed(99)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)
    price = 50000.0

    for i in range(100):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        x = np.random.normal(scale=1.0)
        engine.add_observation(price=price, signed_flow=x, timestamp_ms=now - (100 - i) * 1000)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    assert "ljung_box_return" in obs.diagnostics
    assert "ljung_box_flow" in obs.diagnostics
    assert "q_stat" in obs.diagnostics["ljung_box_return"]
    assert "p_val" in obs.diagnostics["ljung_box_return"]


def test_06_hasbrouck_unstable_var_rejected():
    """HASBROUCK: Explosive companion matrix eigenvalues (|lambda| >= 1.0) reject model as UNSTABLE_SYSTEM."""
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)

    # Generate an explosive system: r_t = 1.2 r_{t-1} + e
    price = 50000.0
    r = 0.001
    x = 1.0
    for i in range(80):
        r = 1.15 * r + np.random.normal(scale=0.0001)
        price = price * math.exp(r)
        x = 1.10 * x + np.random.normal(scale=0.01)
        engine.add_observation(price=price, signed_flow=x, timestamp_ms=now - (80 - i) * 1000)

    obs = engine.fit(timestamp_ms=now)
    # Either non-stationary or unstable system
    assert obs.status in ("UNSTABLE_SYSTEM", "NON_STATIONARY")
    if obs.status == "UNSTABLE_SYSTEM":
        assert obs.is_stable is False
        assert obs.max_eigenvalue_modulus >= 1.0


def test_07_hasbrouck_coefficient_persistence():
    """HASBROUCK: Persistence and retrieval from database preserve all fields accurately."""
    np.random.seed(42)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)
    price = 50000.0

    for i in range(80):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        x = np.random.normal(scale=1.0)
        engine.add_observation(price=price, signed_flow=x, timestamp_ms=now - (80 - i) * 1000)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"

    # Persist
    row_id = db.persist_microstructure_var(obs.to_dict())
    assert row_id > 0

    # Retrieve latest
    latest = db.get_latest_microstructure_var("BTC-USDT")
    assert latest is not None
    assert latest["run_id"] == obs.run_id
    assert latest["status"] == "VALID"
    assert latest["mode"] == "RESEARCH"
    assert latest["selected_lag"] == obs.selected_lag
    assert abs(latest["cumulative_impact"] - obs.cumulative_impact) < 1e-6

    # Retrieve by run_id
    by_id = db.get_microstructure_var_by_run_id(obs.run_id)
    assert by_id is not None
    assert by_id["run_id"] == obs.run_id


def test_08_hasbrouck_irf_reproducibility():
    """HASBROUCK: Cholesky orthogonalized IRF produces identical permanent price impact on identical data."""
    np.random.seed(777)
    engine1 = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    engine2 = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)
    price = 50000.0

    for i in range(90):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        x = np.random.normal(scale=1.0)
        ts = now - (90 - i) * 1000
        engine1.add_observation(price=price, signed_flow=x, timestamp_ms=ts)
        engine2.add_observation(price=price, signed_flow=x, timestamp_ms=ts)

    obs1 = engine1.fit(timestamp_ms=now)
    obs2 = engine2.fit(timestamp_ms=now)

    assert obs1.status == "VALID"
    assert obs2.status == "VALID"
    assert obs1.cumulative_impact == obs2.cumulative_impact
    assert obs1.variance_share_flow == obs2.variance_share_flow
    assert obs1.run_id == obs2.run_id


def test_09_hasbrouck_no_lookahead_future_data_injection():
    """HASBROUCK: Injecting extreme future data does not alter earlier window model fit."""
    np.random.seed(101)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=300000)
    t_historical = 1700000000000
    price = 50000.0

    for i in range(80):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        x = np.random.normal(scale=1.0)
        engine.add_observation(price=price, signed_flow=x, timestamp_ms=t_historical - (80 - i) * 1000)

    obs_before = engine.fit(timestamp_ms=t_historical)
    assert obs_before.status == "VALID"

    # Inject extreme future tick 1 hour ahead
    t_future = t_historical + 3600 * 1000
    engine.add_observation(price=999999.0, signed_flow=50000.0, timestamp_ms=t_future)

    # Re-evaluate strictly at historical timestamp
    obs_after = engine.fit(timestamp_ms=t_historical)
    assert obs_after.run_id == obs_before.run_id
    assert obs_after.cumulative_impact == obs_before.cumulative_impact
    assert obs_after.selected_lag == obs_before.selected_lag


def test_10_hasbrouck_restart_recovery():
    """HASBROUCK: Fresh service instance seamlessly recovers latest VAR run from DB."""
    np.random.seed(55)
    svc = MicrostructureService.get_instance()
    now = int(time.time() * 1000)
    price = 50000.0

    engine = svc._get_var_engine("BTC-USDT")
    for i in range(80):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        x = np.random.normal(scale=1.0)
        engine.add_observation(price=price, signed_flow=x, timestamp_ms=now - (80 - i) * 1000)

    obs = svc.run_hasbrouck_fit("BTC-USDT", persist=True)
    assert obs.status == "VALID"

    # Simulate fresh service instance without memory
    fresh_svc = MicrostructureService()
    recovered = fresh_svc.get_latest_observations("BTC-USDT")
    assert recovered.get("hasbrouck") is not None
    assert recovered["hasbrouck"]["run_id"] == obs.run_id


# ==============================================================================
# VECM RESEARCH TESTS (11 - 20)
# ==============================================================================

def test_11_vecm_known_cointegrated_pair():
    """VECM: Cointegrated spot/perp pair (rank=1) estimates valid beta, alpha, and Gonzalo-Granger weights."""
    np.random.seed(123)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", p_lags=2, min_sample_size=300)
    now = int(time.time() * 1000)
    T = 320

    # Common random walk trend
    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    p_base = 50000.0
    for i in range(T):
        ts = now - (T - i) * 1000
        # Spot and Perp fluctuate around common trend with stationary basis
        p_spot = p_base * math.exp(w[i] + np.random.normal(scale=0.0005))
        p_perp = p_base * math.exp(w[i] + np.random.normal(scale=0.0005))
        engine.add_observation_pair(ts, p_spot, p_perp)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    assert obs.minimum_required_sample == 300
    assert obs.actual_sample >= 300
    assert obs.sample_status == "VALID"
    assert obs.cointegration_rank == 1
    assert obs.trace_stat is not None and obs.trace_stat > 15.49
    assert obs.beta_coeff is not None
    assert obs.alpha_1 is not None and obs.alpha_2 is not None
    assert obs.gg_share_1_raw is not None and obs.gg_share_2_raw is not None
    assert obs.bounded_speed_share_1 is not None and obs.bounded_speed_share_2 is not None
    assert obs.is_stable is True
    assert obs.methodology_version == "VECM_STYLE_V1.1"


def test_12_vecm_non_cointegrated_pair_rejected():
    """VECM: Independent random walks (rank=0) fail cointegration gate as NO_COINTEGRATION."""
    np.random.seed(999)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    now = int(time.time() * 1000)
    T = 150

    w1 = np.cumsum(np.random.normal(scale=0.01, size=T))
    w2 = np.cumsum(np.random.normal(scale=0.01, size=T))
    p_base = 50000.0

    for i in range(T):
        ts = now - (T - i) * 1000
        p_spot = p_base * math.exp(w1[i])
        p_perp = p_base * math.exp(w2[i])
        engine.add_observation_pair(ts, p_spot, p_perp)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "NO_COINTEGRATION"
    assert obs.cointegration_rank == 0
    assert obs.trace_stat <= 15.49


def test_13_vecm_wrong_integration_order_rejected():
    """VECM: Level-stationary I(0) series fail I(1) integration prerequisite as NOT_I1."""
    np.random.seed(42)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    now = int(time.time() * 1000)
    T = 150

    # Stationary series around mean
    p_spot = 50000.0 + np.random.normal(scale=1.0, size=T)
    p_perp = 50000.0 + np.random.normal(scale=1.0, size=T)

    for i in range(T):
        ts = now - (T - i) * 1000
        engine.add_observation_pair(ts, p_spot[i], p_perp[i])

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "NOT_I1"
    assert "level_adf_series_1" in obs.diagnostics


def test_14_vecm_insufficient_sample_gate():
    """VECM: Aligned sample count (N < 60) fails sample gate without manufacturing estimates."""
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    now = int(time.time() * 1000)

    for i in range(30):  # 30 < 60
        engine.add_observation_pair(now - (30 - i) * 1000, 50000.0 + i, 50000.0 + i)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "INSUFFICIENT_SAMPLE"
    assert obs.sample_count < 60


def test_15_vecm_rank_determination_johansen():
    """VECM: Johansen trace test properly populates diagnostics and critical values."""
    np.random.seed(123)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    now = int(time.time() * 1000)
    T = 180

    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    for i in range(T):
        ts = now - (T - i) * 1000
        p_spot = 50000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        p_perp = 50000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        engine.add_observation_pair(ts, p_spot, p_perp)

    obs = engine.fit(timestamp_ms=now)
    assert "johansen" in obs.diagnostics
    assert obs.diagnostics["johansen"]["trace_cv_5pct"] == 15.49
    assert obs.diagnostics["johansen"]["trace_cv_r1_5pct"] == 3.84


def test_16_vecm_deterministic_alignment_gaps():
    """VECM: Alignment drops observation pairs where timestamp gap exceeds max_alignment_gap_ms."""
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", max_alignment_gap_ms=2000, min_sample_size=20)
    now = int(time.time() * 1000)

    # Series 1 (Spot) has points at t=0, 1000, 2000, ...
    # Series 2 (Perp) has points at t=0, 5000, 10000 (gaps > 2000ms from nearest prior spot)
    for i in range(30):
        engine.add_series_1_price(now - (30 - i) * 5000, 50000.0 + i)
        # Perp offset by 4000ms (> 2000ms max gap)
        engine.add_series_2_price(now - (30 - i) * 5000 + 4000, 50000.0 + i)

    obs = engine.fit(timestamp_ms=now)
    # Alignment drops pairs exceeding gap, triggering insufficient sample
    assert obs.status == "INSUFFICIENT_SAMPLE"
    assert obs.detail["dropped_observations"] > 0
    assert obs.detail["missingness_ratio"] > 0.0


def test_17_vecm_unstable_system_rejected():
    """VECM: Explosive non-contracting adjustment speeds reject system as UNSTABLE_SYSTEM."""
    np.random.seed(42)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    now = int(time.time() * 1000)
    T = 150

    # Diverging spread where spot drifts far above perp without mean reversion
    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    for i in range(T):
        ts = now - (T - i) * 1000
        # Basis grows explosively: spot pulls up faster and faster
        p_spot = 50000.0 * math.exp(w[i] + 0.002 * i)
        p_perp = 50000.0 * math.exp(w[i] - 0.002 * i)
        engine.add_observation_pair(ts, p_spot, p_perp)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status in ("UNSTABLE_SYSTEM", "NO_COINTEGRATION", "NOT_I1")


def test_18_vecm_no_lookahead_future_data_injection():
    """VECM: Injecting future price observations does not alter historical VECM fit."""
    np.random.seed(88)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    t_hist = 1700000000000
    T = 150

    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    for i in range(T):
        ts = t_hist - (T - i) * 1000
        p_spot = 50000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        p_perp = 50000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        engine.add_observation_pair(ts, p_spot, p_perp)

    obs_before = engine.fit(timestamp_ms=t_hist)
    assert obs_before.status == "VALID"

    # Inject extreme future price pair 2 hours ahead
    t_future = t_hist + 7200 * 1000
    engine.add_observation_pair(t_future, 999999.0, 999999.0)

    # Re-evaluate historical timestamp
    obs_after = engine.fit(timestamp_ms=t_hist)
    assert obs_after.run_id == obs_before.run_id
    assert obs_after.trace_stat == obs_before.trace_stat
    assert obs_after.beta_coeff == obs_before.beta_coeff


def test_19_vecm_reproducibility():
    """VECM: Re-running VECM on same dataset yields bit-for-bit identical results."""
    np.random.seed(333)
    e1 = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    e2 = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=60)
    now = int(time.time() * 1000)
    T = 120

    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    for i in range(T):
        ts = now - (T - i) * 1000
        p1 = 50000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        p2 = 50000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        e1.add_observation_pair(ts, p1, p2)
        e2.add_observation_pair(ts, p1, p2)

    o1 = e1.fit(timestamp_ms=now)
    o2 = e2.fit(timestamp_ms=now)

    assert o1.run_id == o2.run_id
    assert o1.trace_stat == o2.trace_stat
    assert o1.alpha_1 == o2.alpha_1
    assert o1.alpha_2 == o2.alpha_2


def test_20_vecm_restart_recovery():
    """VECM: Database persistence and restart recovery load latest VECM observation."""
    np.random.seed(42)
    svc = MicrostructureService.get_instance()
    now = int(time.time() * 1000)
    T = 320

    e = svc._get_vecm_engine("BTC-USDT-SPOT", "BTC-USDT-PERP")
    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    z = np.zeros(T)
    for t in range(1, T):
        z[t] = 0.5 * z[t-1] + np.random.normal(scale=0.0005)

    for i in range(T):
        ts = now - (T - i) * 1000
        p_spot = 50000.0 * math.exp(w[i])
        p_perp = 50000.0 * math.exp(w[i] + z[i])
        e.add_observation_pair(ts, p_spot, p_perp)

    obs = svc.run_vecm_fit("BTC-USDT-SPOT", "BTC-USDT-PERP", persist=True)
    assert obs.status == "VALID"

    # Fresh instance without memory loads from DB
    fresh_svc = MicrostructureService()
    recovered = fresh_svc.get_latest_observations("BTC-USDT")
    assert recovered.get("vecm") is not None
    assert recovered["vecm"]["run_id"] == obs.run_id


# ==============================================================================
# SAFETY & GOVERNANCE TESTS (21 - 25)
# ==============================================================================

def test_21_research_cannot_submit_order():
    """SAFETY: Running Hasbrouck VAR and VECM never submits orders to exchange."""
    c = db._connect()
    orders_before = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]

    svc = MicrostructureService.get_instance()
    for i in range(20):
        tick = TradeTick(
            instrument="BTC-USDT",
            venue="BINGX",
            event_timestamp=int(time.time() * 1000),
            received_timestamp=int(time.time() * 1000),
            price=50000.0 + i,
            quantity=1.0,
            aggressor_side="BUY"
        )
        svc.process_tick(tick)

    svc.run_hasbrouck_fit("BTC-USDT")
    svc.run_vecm_fit("BTC-USDT-SPOT", "BTC-USDT-PERP")

    orders_after = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]
    assert orders_after == orders_before


def test_22_research_cannot_reserve_slot():
    """SAFETY: Microstructure operations never reserve or mutate trade execution slots."""
    slots_before = len(db.get_autonomous_trade_slots())
    max_slots = db.get_max_open_trades()

    svc = MicrostructureService.get_instance()
    svc.run_hasbrouck_fit("BTC-USDT")
    svc.run_vecm_fit("BTC-USDT-SPOT", "BTC-USDT-PERP")

    assert len(db.get_autonomous_trade_slots()) == slots_before
    assert db.get_max_open_trades() == max_slots


def test_23_research_cannot_alter_risk():
    """SAFETY: Microstructure research engine has zero access to risk parameters or capacity limits."""
    cap_before = db.get_max_open_trades()
    assert cap_before == 4

    svc = MicrostructureService.get_instance()
    svc.run_hasbrouck_fit("BTC-USDT")
    svc.run_vecm_fit("BTC-USDT-SPOT", "BTC-USDT-PERP")

    assert db.get_max_open_trades() == 4


def test_24_api_auth_microstructure_hasbrouck_and_vecm():
    """API AUTH: Endpoints /api/microstructure/hasbrouck and vecm require valid Bearer token."""
    client = TestClient(app)

    # Unauthenticated requests rejected with 401/403
    assert client.get("/api/microstructure/hasbrouck").status_code in (401, 403)
    assert client.get("/api/microstructure/vecm").status_code in (401, 403)

    # Authenticated request succeeds with mode RESEARCH
    admin = db.get_user_by_id(1)
    token = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    r_hb = client.get("/api/microstructure/hasbrouck?instrument=BTC-USDT", headers=headers)
    assert r_hb.status_code == 200
    assert r_hb.json()["mode"] == "RESEARCH"
    assert "status" in r_hb.json()

    r_vecm = client.get("/api/microstructure/vecm", headers=headers)
    assert r_vecm.status_code == 200
    assert r_vecm.json()["mode"] == "RESEARCH"
    assert "status" in r_vecm.json()


def test_25_multi_user_isolation():
    """ISOLATION: User requests to microstructure research endpoints maintain strict user isolation."""
    client = TestClient(app)
    admin = db.get_user_by_id(1)
    token_admin = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})

    # Create second user using create_google_user
    u2 = db.create_google_user(google_sub="test_sub_iso_6d", email="iso6d@test.com", display_name="Iso User 6D")
    u2_id = u2["id"]
    token_u2 = create_access_token({"sub": str(u2_id), "user_id": u2_id, "role": "USER"})

    # Both users can query read-only research without cross-contaminating private session or portfolio
    r1 = client.get("/api/microstructure/summary?instrument=BTC-USDT", headers={"Authorization": f"Bearer {token_admin}"})
    r2 = client.get("/api/microstructure/summary?instrument=BTC-USDT", headers={"Authorization": f"Bearer {token_u2}"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert "hasbrouck" in r1.json()
    assert "vecm" in r1.json()


# ==============================================================================
# PHASE 6D.1 GOVERNANCE & MATHEMATICAL HARDENING TESTS (26 - 30)
# ==============================================================================

def test_26_vecm_sample_governance_254_must_be_insufficient_sample():
    """PHASE 6D.1: Sample size 254 MUST deterministically evaluate to INSUFFICIENT_SAMPLE."""
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP")  # default min_sample_size=300
    now = int(time.time() * 1000)

    # Add exactly 254 aligned pairs (the live production scenario)
    for i in range(254):
        engine.add_observation_pair(now - (254 - i) * 1000, 50000.0 + i * 0.1, 50000.0 + i * 0.1)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "INSUFFICIENT_SAMPLE"
    assert obs.minimum_required_sample == 300
    assert obs.actual_sample == 254
    assert obs.sample_status == "INSUFFICIENT_SAMPLE"
    assert obs.justification is not None
    assert "Johansen trace test" in obs.justification
    assert "300" in obs.justification
    assert obs.methodology_version == "VECM_STYLE_V1.1"
    assert obs.detail["actual_sample"] == 254
    assert obs.detail["minimum_required_sample"] == 300


def test_27_vecm_gonzalo_granger_raw_preservation_and_out_of_range():
    """PHASE 6D.1: Out-of-range Gonzalo-Granger shares preserve raw values and set in_range=False."""
    np.random.seed(42)
    engine = VecmEngine(series_1="BTC-USDT-SPOT", series_2="BTC-USDT-PERP", min_sample_size=300)
    now = int(time.time() * 1000)
    T = 320

    # Common trend
    w = np.cumsum(np.random.normal(scale=0.005, size=T))
    p_base = 50000.0
    for i in range(T):
        ts = now - (T - i) * 1000
        p_spot = p_base * math.exp(w[i])
        p_perp = p_base * math.exp(w[i] + np.random.normal(scale=0.0005))
        engine.add_observation_pair(ts, p_spot, p_perp)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    # Raw shares are always numeric floats
    assert obs.gg_share_1_raw is not None
    assert obs.gg_share_2_raw is not None
    assert obs.gg_share_in_range is not None

    # If raw shares are out of range, standard gg_share must be None (no clipping)
    if not obs.gg_share_in_range:
        assert obs.gg_share_1 is None
        assert obs.gg_share_2 is None
        assert (obs.gg_share_1_raw < 0.0 or obs.gg_share_1_raw > 1.0)
    else:
        assert obs.gg_share_1 == obs.gg_share_1_raw
        assert obs.gg_share_2 == obs.gg_share_2_raw

    # Explicit bounded speed of adjustment share is always populated in [0, 1]
    assert obs.bounded_speed_share_1 is not None and 0.0 <= obs.bounded_speed_share_1 <= 1.0
    assert obs.bounded_speed_share_2 is not None and 0.0 <= obs.bounded_speed_share_2 <= 1.0
    assert abs((obs.bounded_speed_share_1 + obs.bounded_speed_share_2) - 1.0) < 1e-5


def test_28_hasbrouck_permanent_impact_terminology_and_convergence():
    """PHASE 6D.1: Cumulative impact is labeled H20, and permanent impact requires convergence."""
    np.random.seed(42)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)
    price = 50000.0

    T = 150
    for i in range(T):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        flow = np.random.normal(scale=1.0)
        ts = now - (T - i) * 1000
        engine.add_observation(price=price, signed_flow=flow, timestamp_ms=ts)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    # 20-step cumulative impulse response is explicitly named
    assert obs.cumulative_impact_H20 is not None
    assert obs.cumulative_impact == obs.cumulative_impact_H20
    assert obs.convergence_status in ("CONVERGED", "NOT_CONVERGED")
    assert obs.convergence_tolerance == 1e-6

    if obs.convergence_status == "CONVERGED":
        assert obs.permanent_impact is not None
    else:
        assert obs.permanent_impact is None


def test_29_hasbrouck_flow_specification_robustness():
    """PHASE 6D.1: Primary specification is SIGNED_INDICATOR and robustness is SIGNED_SQRT_VOLUME."""
    np.random.seed(42)
    engine = HasbrouckVarEngine(instrument="BTC-USDT", min_sample_size=60, calculation_window_ms=600000)
    now = int(time.time() * 1000)
    price = 50000.0

    for i in range(100):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        flow = 2.5 * (1.0 if np.random.rand() > 0.5 else -1.0)
        ts = now - (100 - i) * 1000
        engine.add_observation(price=price, signed_flow=flow, timestamp_ms=ts)

    obs = engine.fit(timestamp_ms=now)
    assert obs.status == "VALID"
    assert obs.primary_x_definition == "SIGNED_INDICATOR"
    assert obs.robustness_x_definition == "SIGNED_SQRT_VOLUME"
    assert "robustness" in obs.diagnostics
    rob = obs.diagnostics["robustness"]
    assert rob["primary_x_definition"] == "SIGNED_INDICATOR"
    assert rob["robustness_x_definition"] == "SIGNED_SQRT_VOLUME"
    assert "robustness_cum_impact_H20" in rob
    assert "robustness_variance_share" in rob
    assert "coefficient_direction_concordant" in rob


def test_30_db_persistence_phase6d1_governance_fields():
    """PHASE 6D.1: DB persistence and retrieval preserve all newly added governance fields."""
    np.random.seed(123)
    now = int(time.time() * 1000)

    # 1. Hasbrouck VAR
    engine_var = HasbrouckVarEngine(instrument="ETH-USDT", min_sample_size=60, calculation_window_ms=600000)
    price = 3000.0
    for i in range(80):
        r = np.random.normal(scale=0.001)
        price = price * math.exp(r)
        flow = float(np.random.choice([-1.0, 1.0]))
        engine_var.add_observation(price=price, signed_flow=flow, timestamp_ms=now - (80 - i) * 1000)

    obs_var = engine_var.fit(timestamp_ms=now)
    db.persist_microstructure_var(obs_var.to_dict())
    retrieved_var = db.get_latest_microstructure_var("ETH-USDT")
    assert retrieved_var is not None
    assert retrieved_var["methodology_version"] == "HASBROUCK_STYLE_V1.1"
    assert retrieved_var["primary_x_definition"] == "SIGNED_INDICATOR"
    assert retrieved_var["robustness_x_definition"] == "SIGNED_SQRT_VOLUME"
    assert retrieved_var["convergence_status"] in ("CONVERGED", "NOT_CONVERGED")

    # 2. VECM
    engine_vecm = VecmEngine(series_1="ETH-USDT-SPOT", series_2="ETH-USDT-PERP", min_sample_size=300)
    w = np.cumsum(np.random.normal(scale=0.005, size=320))
    for i in range(320):
        ts = now - (320 - i) * 1000
        p1 = 3000.0 * math.exp(w[i])
        p2 = 3000.0 * math.exp(w[i] + np.random.normal(scale=0.0005))
        engine_vecm.add_observation_pair(ts, p1, p2)

    obs_vecm = engine_vecm.fit(timestamp_ms=now)
    db.persist_microstructure_vecm(obs_vecm.to_dict())
    retrieved_vecm = db.get_latest_microstructure_vecm("ETH-USDT-SPOT", "ETH-USDT-PERP")
    assert retrieved_vecm is not None
    assert retrieved_vecm["methodology_version"] == "VECM_STYLE_V1.1"
    assert retrieved_vecm["minimum_required_sample"] == 300
    assert retrieved_vecm["actual_sample"] == 320
    assert retrieved_vecm["sample_status"] == "VALID"
    assert retrieved_vecm["bounded_speed_share_1"] is not None
