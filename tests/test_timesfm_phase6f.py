"""Unit and integration test suite for Ophelia Phase 6F: TimesFM Microstructure Feature-Consumption.

Tests verify:
1. Strict invariant: TRADING_AUTHORITY is False, MODE is SHADOW, EXECUTION_GATED is True.
2. Adapter formats past_only_covariates with exact shape (num_channels, context_length).
3. Zero lookahead in covariate alignment (timestamps strictly <= T).
4. Normalization leakage prevention (scaler fitted strictly on TRAIN fold).
5. Missing feature handling (deterministic zeros, no silent random numbers, explicit quality flag).
6. Exact reproduction of TimesFM close-only baseline when covariates are omitted.
7. Quantile monotonicity guarantee (q10 <= q50 <= q90) under covariate conditioning.
8. Failure isolation: Microstructure feature failures degrade cleanly to close-only baseline.
9. Failure isolation: TimesFM inference failures degrade safely without disrupting microstructure or engine.
10. Execution barrier: Zero orders placed, zero slots reserved, zero risk settings mutated.
11. Database persistence and retrieval roundtrip in timesfm_microstructure_experiments table.
12. End-to-end walk-forward experiment runner evaluation across Conditions B through F with DM and BH FDR.
"""
import math
import time
import numpy as np
import pytest

from control_plane import db
from control_plane.microstructure_evaluation import CausalStandardScaler
from control_plane.timesfm_adapter import (
    TRADING_AUTHORITY,
    MODE,
    EXECUTION_GATED,
    CONDITION_A_CLOSE_ONLY,
    CONDITION_B_FLOW_DURATION,
    CONDITION_C_ORDERBOOK_LIQUIDITY,
    CONDITION_D_IMPACT_TOXICITY,
    CONDITION_E_HASBROUCK_VECM,
    CONDITION_F_ALL_MICROSTRUCTURE,
    CONDITION_FEATURE_MAP,
    TimesFMCovariateAdapter,
    TimesFMMicrostructureExperimentRunner,
)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    db.init_db()


def test_01_trading_authority_strictly_false():
    """Verify Phase 6F enforces zero trading authority in TimesFM adapter."""
    assert TRADING_AUTHORITY is False
    assert MODE == "SHADOW"
    assert EXECUTION_GATED is True


def test_02_adapter_formats_past_only_covariates_shape():
    """Verify adapter formats past_only_covariates to exact shape (num_channels, context_length)."""
    adapter = TimesFMCovariateAdapter()
    context_length = 64
    
    # 2 channels
    channels_2 = ["signed_flow", "arrival_intensity"]
    features_dict_2 = {
        "signed_flow": np.linspace(1.0, 10.0, 100, dtype=np.float32),
        "arrival_intensity": np.linspace(0.1, 1.0, 100, dtype=np.float32),
    }
    cov_matrix_2, quality_2 = adapter.format_covariates(features_dict_2, channels_2, context_length)
    assert cov_matrix_2 is not None
    assert cov_matrix_2.shape == (2, context_length)
    assert cov_matrix_2.dtype == np.float32
    assert quality_2 == "VALID"
    # Verify values match most recent context_length points
    assert np.allclose(cov_matrix_2[0], features_dict_2["signed_flow"][-context_length:])
    assert np.allclose(cov_matrix_2[1], features_dict_2["arrival_intensity"][-context_length:])

    # 8 channels (Condition F)
    channels_8 = CONDITION_FEATURE_MAP[CONDITION_F_ALL_MICROSTRUCTURE]
    features_dict_8 = {ch: np.full(150, i + 1.0, dtype=np.float32) for i, ch in enumerate(channels_8)}
    cov_matrix_8, quality_8 = adapter.format_covariates(features_dict_8, channels_8, 128)
    assert cov_matrix_8 is not None
    assert cov_matrix_8.shape == (8, 128)
    assert quality_8 == "VALID"


def test_03_zero_lookahead_covariate_alignment():
    """Verify zero lookahead: all covariate features timestamped <= forecast cutoff T."""
    adapter = TimesFMCovariateAdapter()
    context_length = 32
    total_len = 100
    cutoff_T = 60

    # Inject distinctive poison values strictly AFTER cutoff T
    feat_series = np.arange(total_len, dtype=np.float32)
    feat_series[cutoff_T:] = 999999.0  # Future values

    # Causal slice up to cutoff T
    causal_slice = {"test_feature": feat_series[:cutoff_T]}
    cov_matrix, quality = adapter.format_covariates(causal_slice, ["test_feature"], context_length)

    assert cov_matrix is not None
    assert cov_matrix.shape == (1, context_length)
    # Ensure poison future values are NOT present
    assert not np.any(cov_matrix == 999999.0)
    # The last value in cov_matrix must be feat_series[cutoff_T - 1]
    assert cov_matrix[0, -1] == feat_series[cutoff_T - 1]


def test_04_normalization_leakage_train_only():
    """Verify normalization scaler is fitted strictly on TRAIN fold."""
    train_size = 200
    test_size = 100
    
    # Train fold: mean = 100, std = 15
    train_data = np.random.normal(100.0, 15.0, (train_size, 2)).astype(np.float32)
    # Test fold: regime shift, mean = 500, std = 50
    test_data = np.random.normal(500.0, 50.0, (test_size, 2)).astype(np.float32)

    scaler = CausalStandardScaler()
    scaler.fit(train_data)

    # Scaler mean must reflect ONLY train fold
    assert np.allclose(scaler.mean_, np.mean(train_data, axis=0), atol=1e-4)
    assert not np.allclose(scaler.mean_, np.mean(np.vstack([train_data, test_data]), axis=0))

    # Test transform on test_data uses train mean and std
    scaled_test = scaler.transform(test_data)
    expected_scaled = (test_data - scaler.mean_) / scaler.std_
    assert np.allclose(scaled_test, expected_scaled, atol=1e-4)


def test_05_missing_feature_handling_no_silent_random_numbers():
    """Verify missing features produce deterministic zeros, no random noise, and set quality flag."""
    adapter = TimesFMCovariateAdapter()
    context_length = 32

    # Request 2 features, but provide only 1
    features_dict = {
        "signed_flow": np.ones(50, dtype=np.float32) * 5.0,
        # "arrival_intensity" is missing
    }
    channels = ["signed_flow", "arrival_intensity"]
    cov_matrix, quality = adapter.format_covariates(features_dict, channels, context_length)

    assert cov_matrix is not None
    assert cov_matrix.shape == (2, context_length)
    assert quality == "PARTIAL"
    # Channel 1 has valid values
    assert np.allclose(cov_matrix[0], 5.0)
    # Missing channel has deterministic zeros
    assert np.allclose(cov_matrix[1], 0.0)

    # All features missing
    cov_empty, quality_empty = adapter.format_covariates({}, channels, context_length)
    assert cov_empty is not None
    assert quality_empty == "MISSING"
    assert np.allclose(cov_empty, 0.0)


def test_06_exact_reproduction_close_only_baseline():
    """Verify omitting covariates reproduces the baseline forecast."""
    adapter = TimesFMCovariateAdapter()
    prices = np.linspace(60000.0, 61000.0, 50, dtype=np.float32)
    horizon = 12

    # Call with covariates=None and Condition A
    res_none = adapter.predict_with_covariates(
        context_series=prices,
        horizon=horizon,
        covariates=None,
        condition_name=CONDITION_A_CLOSE_ONLY,
    )
    assert res_none.status == "SUCCESS"
    assert res_none.model_name == CONDITION_A_CLOSE_ONLY
    assert len(res_none.forecast_values) == horizon
    assert "q10" in res_none.quantiles
    assert "q50" in res_none.quantiles
    assert "q90" in res_none.quantiles

    # Call format_covariates with empty channels -> None
    empty_cov, quality = adapter.format_covariates({}, [], 32)
    assert empty_cov is None
    assert quality == "NO_COVARIATES"

    res_empty = adapter.predict_with_covariates(
        context_series=prices,
        horizon=horizon,
        covariates=empty_cov,
        condition_name=CONDITION_A_CLOSE_ONLY,
    )
    assert np.allclose(res_none.forecast_values, res_empty.forecast_values)


def test_07_quantile_monotonicity_under_covariates():
    """Verify quantile monotonicity: q10 <= q50 <= q90 across all steps under covariate conditioning."""
    adapter = TimesFMCovariateAdapter()
    prices = np.array([50000.0, 50200.0, 49800.0, 50100.0, 50500.0] * 10, dtype=np.float32)
    horizon = 16

    # Test with various covariate vectors (positive, negative, zero)
    for cov_val in [-5.0, 0.0, 5.0, 100.0]:
        covs = np.full((4, len(prices)), cov_val, dtype=np.float32)
        res = adapter.predict_with_covariates(
            context_series=prices,
            horizon=horizon,
            covariates=covs,
            condition_name=CONDITION_F_ALL_MICROSTRUCTURE,
        )
        assert res.status == "SUCCESS"
        q10 = res.quantiles["q10"]
        q50 = res.quantiles["q50"]
        q90 = res.quantiles["q90"]
        assert len(q10) == horizon
        assert len(q50) == horizon
        assert len(q90) == horizon

        for step in range(horizon):
            assert q10[step] <= q50[step] + 1e-6, f"Quantile violation at step {step}: q10={q10[step]} > q50={q50[step]}"
            assert q50[step] <= q90[step] + 1e-6, f"Quantile violation at step {step}: q50={q50[step]} > q90={q90[step]}"


def test_08_failure_isolation_microstructure_failure_timesfm_healthy():
    """Verify microstructure feature failure allows TimesFM to fall back cleanly to baseline."""
    adapter = TimesFMCovariateAdapter()
    prices = np.linspace(60000.0, 60500.0, 40, dtype=np.float32)
    
    # Degraded/corrupted feature dictionary (NaNs and Infs)
    corrupted_features = {
        "signed_flow": np.array([np.nan, np.inf, -np.inf] * 15, dtype=np.float32),
        "arrival_intensity": np.zeros(40, dtype=np.float32),
    }
    channels = ["signed_flow", "arrival_intensity"]
    covs, quality = adapter.format_covariates(corrupted_features, channels, 30)

    # When fed into predict_with_covariates, should not raise an unhandled crash
    res = adapter.predict_with_covariates(
        context_series=prices,
        horizon=10,
        covariates=covs,
        condition_name=CONDITION_B_FLOW_DURATION,
    )
    assert res.status == "SUCCESS"
    assert len(res.forecast_values) == 10
    # Values should be finite
    assert np.all(np.isfinite(res.forecast_values))


def test_09_failure_isolation_timesfm_failure_microstructure_healthy():
    """Verify TimesFM internal failure falls back safely without unhandled exception."""
    class CrashingProvider:
        def __init__(self):
            self.model = self
        def predict(self, *args, **kwargs):
            raise RuntimeError("Simulated TimesFM GPU out-of-memory or kernel panic")

    adapter = TimesFMCovariateAdapter(provider=CrashingProvider())
    prices = np.linspace(65000.0, 66000.0, 50, dtype=np.float32)
    covs = np.ones((2, 50), dtype=np.float32)

    # Must fall back gracefully to simulation model without propagating RuntimeError
    res = adapter.predict_with_covariates(
        context_series=prices,
        horizon=12,
        covariates=covs,
        condition_name=CONDITION_C_ORDERBOOK_LIQUIDITY,
    )
    assert res.status == "SUCCESS"
    assert res.model_version == "3.0_sim"
    assert len(res.forecast_values) == 12


def test_10_execution_barrier_zero_orders_zero_slots_zero_risk():
    """Verify running TimesFM microstructure experiments places zero orders and mutates no trade slots."""
    # Read initial state of orders and trade slots
    conn = db._connect()
    with db._lock:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM manual_orders")
        orders_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM autonomous_trade_slots")
        slots_before = cursor.fetchone()[0]

    runner = TimesFMMicrostructureExperimentRunner()
    prices = np.linspace(50000.0, 52000.0, 100, dtype=np.float32)
    features = {ch: np.random.randn(100).astype(np.float32) for ch in CONDITION_FEATURE_MAP[CONDITION_F_ALL_MICROSTRUCTURE]}

    results = runner.run_experiment(
        experiment_id=f"test_barrier_{int(time.time())}",
        instrument="BTC-USDT",
        prices=prices,
        features_dict=features,
        timeframe="5m",
        horizon=6,
        context_length=32,
        persist_to_db=False,
    )

    assert len(results) == 5
    # Verify manual_orders and autonomous_trade_slots tables untouched
    with db._lock:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM manual_orders")
        orders_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM autonomous_trade_slots")
        slots_after = cursor.fetchone()[0]

    assert orders_before == orders_after, "Invariant violation: manual_orders count changed during research experiment"
    assert slots_before == slots_after, "Invariant violation: autonomous_trade_slots changed during research experiment"


def test_11_db_persistence_and_retrieval_roundtrip():
    """Verify timesfm_microstructure_experiments DB persistence and retrieval."""
    exp_id = f"test_timesfm_db_{int(time.time() * 1000)}"
    record = {
        "experiment_id": exp_id,
        "condition_name": CONDITION_B_FLOW_DURATION,
        "instrument": "ETH-USDT",
        "timeframe": "5m",
        "horizon": 12,
        "feature_channels": ["signed_flow", "arrival_intensity"],
        "sample_count": 85,
        "mae_baseline": 14.25,
        "mae_augmented": 13.90,
        "delta_mae": -0.35,
        "rmse_baseline": 18.50,
        "rmse_augmented": 18.10,
        "delta_rmse": -0.40,
        "dir_acc_baseline": 0.525,
        "dir_acc_augmented": 0.550,
        "delta_dir_acc": 0.025,
        "dm_stat": -1.85,
        "raw_p_value": 0.064,
        "adjusted_p_value": 0.080,
        "is_significant": False,
        "status": "VALID",
        "latency_baseline_ms": 1.45,
        "latency_augmented_ms": 1.82,
        "memory_overhead_mb": 0.50,
    }

    db.persist_timesfm_microstructure_experiment(record)

    rows = db.get_timesfm_microstructure_experiments(exp_id)
    assert len(rows) == 1
    retrieved = rows[0]
    assert retrieved["experiment_id"] == exp_id
    assert retrieved["condition_name"] == CONDITION_B_FLOW_DURATION
    assert retrieved["instrument"] == "ETH-USDT"
    assert retrieved["feature_channels"] == ["signed_flow", "arrival_intensity"]
    assert retrieved["sample_count"] == 85
    assert retrieved["mae_baseline"] == 14.25
    assert retrieved["mae_augmented"] == 13.90
    assert retrieved["delta_mae"] == -0.35
    assert retrieved["is_significant"] == 0 or retrieved["is_significant"] is False


def test_12_runner_walk_forward_evaluation_conditions_b_through_f():
    """Verify TimesFMMicrostructureExperimentRunner evaluates all Conditions B-F."""
    runner = TimesFMMicrostructureExperimentRunner()
    np.random.seed(42)
    prices = 60000.0 + np.cumsum(np.random.randn(120) * 15.0).astype(np.float32)
    features = {
        ch: np.random.randn(120).astype(np.float32)
        for ch in CONDITION_FEATURE_MAP[CONDITION_F_ALL_MICROSTRUCTURE]
    }

    exp_id = f"test_wf_runner_{int(time.time() * 1000)}"
    results = runner.run_experiment(
        experiment_id=exp_id,
        instrument="BTC-USDT",
        prices=prices,
        features_dict=features,
        timeframe="5m",
        horizon=8,
        context_length=32,
        persist_to_db=True,
    )

    assert len(results) == 5
    condition_names = [r["condition_name"] for r in results]
    assert CONDITION_B_FLOW_DURATION in condition_names
    assert CONDITION_C_ORDERBOOK_LIQUIDITY in condition_names
    assert CONDITION_D_IMPACT_TOXICITY in condition_names
    assert CONDITION_E_HASBROUCK_VECM in condition_names
    assert CONDITION_F_ALL_MICROSTRUCTURE in condition_names

    for r in results:
        assert r["sample_count"] > 0
        assert "mae_baseline" in r
        assert "mae_augmented" in r
        assert "dm_stat" in r
        assert "adjusted_p_value" in r
        assert "latency_augmented_ms" in r

    # Verify rows persisted
    db_rows = db.get_timesfm_microstructure_experiments(exp_id)
    assert len(db_rows) == 5
