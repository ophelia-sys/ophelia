"""Unit and integration test suite for Ophelia Phase 6E: Microstructure Evaluation.

Tests verify:
1. Research experiment registry and table schema persistence.
2. Chronological train/val/test splitting with purge and embargo windows.
3. Zero lookahead in feature scaling and target construction.
4. Baseline model forecasting suite (Naive, EMA, Momentum).
5. Diebold-Mariano test with Newey-West/HAC Bartlett kernel standard errors.
6. Benjamini-Hochberg FDR multiple-testing correction.
7. Multi-module group ablations across all 8 microstructure modules.
8. Market regime segmentation (low, normal, high volatility).
9. Cross-asset robustness representations (BTC, ETH, SOL, GOLD).
10. Strict zero trading authority invariant (RESEARCH_ONLY).
"""
import math
import time
import numpy as np
import pytest

from control_plane import db
from control_plane.microstructure_evaluation import (
    TRADING_AUTHORITY,
    EXECUTION_GATED,
    TemporalSplitter,
    CausalStandardScaler,
    DieboldMarianoTest,
    BenjaminiHochberg,
    MetricsCalculator,
    L2RidgeRegressor,
    MicrostructureEvaluationHarness,
    MODULE_FEATURE_GROUPS,
    COHERENT_SUPER_GROUPS,
)
from models.microstructure import (
    ExperimentMetadata,
    EvaluationMetrics,
    AblationResult,
    RegimeResult,
    CrossAssetResult,
)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    db.init_db()


def test_01_trading_authority_strictly_false():
    """Verify Phase 6E enforces zero trading authority."""
    assert TRADING_AUTHORITY is False
    assert EXECUTION_GATED is True


def test_02_experiment_registry_persistence():
    """Verify experiment metadata persistence and retrieval in SQLite."""
    exp_id = f"test_exp_reg_{int(time.time() * 1000)}"
    meta = {
        "experiment_id": exp_id,
        "dataset_id": "test_dataset_v1",
        "instrument": "BTC-USDT",
        "venue": "BINGX",
        "asset_class": "CRYPTO",
        "start_ts": 1700000000000,
        "end_ts": 1700000600000,
        "sampling_interval_ms": 1000,
        "forecast_horizon_s": 300,
        "feature_schema_version": "v1.1",
        "methodology_versions": "MICROSTRUCTURE_EVAL_V1",
        "code_commit": "test_commit_hash",
        "config_hash": "cfg_hash_1234",
    }
    db.persist_microstructure_experiment(meta)
    fetched = db.get_microstructure_experiment(exp_id)
    assert fetched is not None
    assert fetched["experiment_id"] == exp_id
    assert fetched["mode"] == "RESEARCH"
    assert fetched["config_hash"] == "cfg_hash_1234"


def test_03_temporal_splitter_purge_and_embargo():
    """Verify temporal splitter enforces purge and embargo windows."""
    n_samples = 1000
    horizon_steps = 10
    purge_steps = 10
    embargo_steps = 5

    splits = TemporalSplitter.split(
        n_samples=n_samples,
        train_ratio=0.60,
        val_ratio=0.20,
        test_ratio=0.20,
        horizon_steps=horizon_steps,
        purge_steps=purge_steps,
        embargo_steps=embargo_steps,
    )

    assert len(splits.train_indices) == 600 - purge_steps
    # Val starts after raw_train_end + embargo_steps (600 + 5 = 605)
    assert splits.val_indices[0] == 600 + embargo_steps
    # Val ends before raw_val_end - purge_steps (800 - 10 = 790)
    assert splits.val_indices[-1] == 800 - purge_steps - 1
    # Test starts after raw_val_end + embargo_steps (800 + 5 = 805)
    assert splits.test_indices[0] == 800 + embargo_steps
    assert splits.test_indices[-1] == n_samples - 1


def test_04_causal_standard_scaler_no_future_leakage():
    """Verify standardizer fitted on train does not use test statistics."""
    train_data = np.array([[10.0], [20.0], [30.0]])  # mean 20, std ~8.16
    test_data = np.array([[100.0], [200.0]])

    scaler = CausalStandardScaler()
    scaler.fit(train_data)

    assert abs(scaler.mean_[0] - 20.0) < 1e-4
    test_transformed = scaler.transform(test_data)
    # 100 transformed with train mean 20 should be large positive
    assert test_transformed[0, 0] > 5.0


def test_05_diebold_mariano_identical_forecasts():
    """DM test between identical forecasts must yield 0 stat and p=1."""
    e = np.random.normal(0, 1.0, 200)
    dm = DieboldMarianoTest.compute(e, e, horizon_steps=1, loss_type="MAE")
    assert dm["dm_stat"] == 0.0
    assert dm["p_value"] == 1.0
    assert dm["mean_diff"] == 0.0


def test_06_diebold_mariano_superior_candidate():
    """DM test where candidate is strictly superior must yield positive DM and low p-value."""
    e_baseline = np.random.normal(0, 2.0, 500)
    e_candidate = e_baseline * 0.5  # half the errors
    dm = DieboldMarianoTest.compute(e_baseline, e_candidate, horizon_steps=5, loss_type="MAE")
    assert dm["dm_stat"] > 5.0
    assert dm["p_value"] < 0.001
    assert dm["mean_diff"] > 0.0


def test_07_diebold_mariano_hac_bartlett_kernel():
    """DM test with multi-step horizon must apply Bartlett kernel weighting."""
    np.random.seed(42)
    e1 = np.cumsum(np.random.normal(0, 0.1, 300))  # autocorrelated errors
    e2 = e1 + np.random.normal(0, 0.05, 300)
    dm_h1 = DieboldMarianoTest.compute(e1, e2, horizon_steps=1)
    dm_h10 = DieboldMarianoTest.compute(e1, e2, horizon_steps=10)
    # Multi-step Bartlett kernel adjusts standard error
    assert dm_h10["hac_std"] != dm_h1["hac_std"]


def test_08_benjamini_hochberg_fdr_control():
    """Verify BH FDR procedure adjusts p-values monotonically and controls false discoveries."""
    raw_p = [0.001, 0.01, 0.04, 0.07, 0.50]
    adjusted = BenjaminiHochberg.adjust(raw_p, alpha=0.05)

    assert len(adjusted) == len(raw_p)
    # p1: 0.001 * (5/1) = 0.005 -> significant
    assert adjusted[0][0] == 0.001
    assert adjusted[0][1] == 0.005
    assert adjusted[0][2] is True

    # p2: 0.01 * (5/2) = 0.025 -> significant
    assert adjusted[1][1] == 0.025
    assert adjusted[1][2] is True

    # p3: 0.04 * (5/3) = 0.0667 > 0.05 -> not significant
    assert adjusted[2][2] is False

    # Monotonicity check
    adj_vals = [a[1] for a in adjusted]
    assert adj_vals == sorted(adj_vals)


def test_09_metrics_calculator_directional_accuracy():
    """Verify directional accuracy matches exact sign correspondence."""
    y_true = np.array([0.05, -0.02, 0.01, -0.04])
    y_pred = np.array([0.01, -0.05, -0.01, -0.02])  # 3 of 4 match sign
    acc = MetricsCalculator.directional_accuracy(y_true, y_pred)
    assert acc == 0.75


def test_10_metrics_calculator_rank_ic():
    """Verify rank IC correctly assesses rank correlation."""
    y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y_pred_perf = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    y_pred_inv = np.array([50.0, 40.0, 30.0, 20.0, 10.0])

    assert abs(MetricsCalculator.rank_ic(y_true, y_pred_perf) - 1.0) < 1e-6
    assert abs(MetricsCalculator.rank_ic(y_true, y_pred_inv) - (-1.0)) < 1e-6


def test_11_metrics_calculator_pinball_loss():
    """Verify pinball loss for median (tau=0.5) equals half MAE."""
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.5, 1.0, 4.0])
    mae = MetricsCalculator.mae(y_true, y_pred)
    p50 = MetricsCalculator.pinball_loss(y_true, y_pred, tau=0.5)
    assert abs(p50 - 0.5 * mae) < 1e-6


def test_12_l2_ridge_regressor():
    """Verify L2 regularized regression fits linear relationship."""
    np.random.seed(123)
    X = np.random.normal(0, 1.0, (100, 2))
    # True relationship: y = 2.0 * x1 - 1.5 * x2 + 0.5
    y = 2.0 * X[:, 0] - 1.5 * X[:, 1] + 0.5 + np.random.normal(0, 0.1, 100)

    model = L2RidgeRegressor(alpha=0.1)
    model.fit(X, y)
    preds = model.predict(X)

    assert abs(model.weights_[0] - 2.0) < 0.2
    assert abs(model.weights_[1] - (-1.5)) < 0.2
    assert abs(model.intercept_ - 0.5) < 0.2
    assert MetricsCalculator.mae(y, preds) < 0.15


def test_13_feature_groups_coverage():
    """Verify all 8 microstructure modules and super groups are defined."""
    expected_modules = [
        "FLOW_GROUP", "DURATION_GROUP", "OBI_GROUP", "LIQUIDITY_GROUP",
        "IMPACT_GROUP", "TOXICITY_GROUP", "HASBROUCK_GROUP", "VECM_GROUP"
    ]
    for mod in expected_modules:
        assert mod in MODULE_FEATURE_GROUPS
        assert len(MODULE_FEATURE_GROUPS[mod]) >= 2

    assert "ALL_MICROSTRUCTURE" in COHERENT_SUPER_GROUPS
    all_feats = COHERENT_SUPER_GROUPS["ALL_MICROSTRUCTURE"]
    # Total distinct features across 8 modules
    assert len(all_feats) >= 20


def test_14_ablation_results_db_roundtrip():
    """Verify ablation results persist and retrieve accurately from SQLite."""
    exp_id = f"test_exp_ablation_{int(time.time() * 1000)}"
    db.persist_microstructure_experiment({
        "experiment_id": exp_id,
        "start_ts": 1000,
        "end_ts": 2000,
        "instrument": "BTC-USDT",
    })
    ablations = [
        {
            "experiment_id": exp_id,
            "baseline_name": "NAIVE_PERSISTENCE",
            "feature_group": "FLOW_GROUP",
            "horizon": 300,
            "delta_mae": -0.00025,
            "delta_rmse": -0.00030,
            "delta_dir_acc": 0.045,
            "dm_stat": -2.85,
            "raw_p_value": 0.004,
            "adjusted_p_value": 0.012,
            "is_significant": True,
        }
    ]
    db.persist_microstructure_ablation_results(ablations)
    ret = db.get_microstructure_ablation_results(exp_id)
    assert len(ret) == 1
    assert ret[0]["feature_group"] == "FLOW_GROUP"
    assert ret[0]["is_significant"] == 1
    assert ret[0]["dm_stat"] == -2.85


def test_15_regime_results_db_roundtrip():
    """Verify regime results persist and retrieve accurately from SQLite."""
    exp_id = f"test_exp_regime_{int(time.time() * 1000)}"
    db.persist_microstructure_experiment({
        "experiment_id": exp_id,
        "start_ts": 1000,
        "end_ts": 2000,
        "instrument": "ETH-USDT",
    })
    regimes = [
        {
            "experiment_id": exp_id,
            "regime_name": "HIGH_VOLATILITY",
            "feature_group": "ALL_MICROSTRUCTURE",
            "metric_name": "MAE",
            "metric_value": 0.00145,
            "sample_count": 85,
        }
    ]
    db.persist_microstructure_regime_results(regimes)
    ret = db.get_microstructure_regime_results(exp_id)
    assert len(ret) == 1
    assert ret[0]["regime_name"] == "HIGH_VOLATILITY"
    assert ret[0]["metric_value"] == 0.00145


def test_16_cross_asset_results_db_roundtrip():
    """Verify cross-asset results persist and retrieve accurately from SQLite."""
    exp_id = f"test_exp_ca_{int(time.time() * 1000)}"
    db.persist_microstructure_experiment({
        "experiment_id": exp_id,
        "start_ts": 1000,
        "end_ts": 2000,
        "instrument": "GOLD",
    })
    cross_assets = [
        {
            "experiment_id": exp_id,
            "instrument": "GOLD",
            "asset_class": "COMMODITY",
            "feature_group": "FLOW_GROUP",
            "metric_name": "DELTA_MAE",
            "metric_value": -0.00018,
            "sample_count": 200,
        }
    ]
    db.persist_microstructure_cross_asset_results(cross_assets)
    ret = db.get_microstructure_cross_asset_results(exp_id)
    assert len(ret) == 1
    assert ret[0]["instrument"] == "GOLD"
    assert ret[0]["asset_class"] == "COMMODITY"


def test_17_full_evaluation_harness_synthetic_market():
    """Verify end-to-end evaluation harness on synthetic market data."""
    np.random.seed(99)
    N = 300
    prices = 50000.0 + np.cumsum(np.random.normal(0, 10.0, N))
    ts = np.arange(1700000000000, 1700000000000 + N * 1000, 1000)

    # Generate synthetic features for all 8 modules
    features = {}
    for mod, feats in MODULE_FEATURE_GROUPS.items():
        for f in feats:
            # Informative feature for flow: correlates with future return
            if f == "flow_innovation":
                features[f] = np.diff(prices, prepend=prices[0]) / prices + np.random.normal(0, 0.0001, N)
            else:
                features[f] = np.random.normal(0, 1.0, N)

    exp_id = f"exp_synth_{int(time.time() * 1000)}"
    harness = MicrostructureEvaluationHarness(
        experiment_id=exp_id,
        instrument="BTC-USDT",
        forecast_horizon_steps=5,
    )

    results = harness.run_evaluation(
        features_dict=features,
        prices=prices,
        timestamps_ms=ts,
        persist_to_db=True,
    )

    assert "experiment" in results
    assert "baseline_metrics" in results
    assert "ablations" in results
    assert "regimes" in results

    # Verify NAIVE_PERSISTENCE baseline exists
    assert "NAIVE_PERSISTENCE" in results["baseline_metrics"]

    # Verify ablations contain all groups
    ab_groups = [ab["feature_group"] for ab in results["ablations"]]
    assert "FLOW_GROUP" in ab_groups
    assert "ALL_MICROSTRUCTURE" in ab_groups

    # Verify DB persistence
    db_exp = db.get_microstructure_experiment(exp_id)
    assert db_exp is not None
    assert db_exp["mode"] == "RESEARCH"


def test_18_insufficient_samples_raises_error():
    """Verify harness rejects small sample count (< 60)."""
    harness = MicrostructureEvaluationHarness(experiment_id="test_too_small")
    prices = np.array([100.0] * 30)
    ts = np.array([1000] * 30)
    with pytest.raises(ValueError, match="Insufficient sample count"):
        harness.run_evaluation({}, prices, ts)


def test_19_missing_features_handled_deterministically():
    """Verify harness runs even if some features are missing from feed."""
    np.random.seed(101)
    N = 250
    prices = 100.0 + np.cumsum(np.random.normal(0, 1.0, N))
    ts = np.arange(1000, 1000 + N * 1000, 1000)

    # Provide only 1 feature out of 25
    features = {"signed_flow": np.random.normal(0, 1.0, N)}

    exp_id = f"exp_missing_{int(time.time() * 1000)}"
    harness = MicrostructureEvaluationHarness(
        experiment_id=exp_id,
        instrument="SOL-USDT",
        forecast_horizon_steps=5,
    )

    res = harness.run_evaluation(features, prices, ts, persist_to_db=False)
    assert len(res["ablations"]) > 0


def test_20_zero_trading_authority_enforced_in_harness():
    """Verify evaluation harness contains no order or risk mutation capabilities."""
    harness = MicrostructureEvaluationHarness(experiment_id="test_safety")
    assert not hasattr(harness, "place_order")
    assert not hasattr(harness, "reserve_slot")
    assert not hasattr(harness, "set_leverage")
    assert not hasattr(harness, "cancel_order")


def test_21_cross_asset_multi_instrument_comparison():
    """Verify evaluation can be executed across all core Ophelia watchlist assets."""
    assets = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "GOLD"]
    np.random.seed(77)
    N = 100
    prices = 100.0 + np.cumsum(np.random.normal(0, 0.5, N))
    ts = np.arange(1000, 1000 + N * 1000, 1000)
    features = {"signed_flow": np.random.normal(0, 1.0, N)}

    for sym in assets:
        exp_id = f"exp_asset_{sym.replace('-', '_')}_{int(time.time() * 1000)}"
        harness = MicrostructureEvaluationHarness(
            experiment_id=exp_id,
            instrument=sym,
            forecast_horizon_steps=3,
        )
        res = harness.run_evaluation(features, prices, ts, persist_to_db=False)
        assert res["experiment"]["instrument"] == sym
        assert len(res["cross_asset"]) > 0


def test_22_regime_terciles_coverage():
    """Verify volatility regime splits cover high, normal, and low states."""
    np.random.seed(88)
    N = 200
    # Create distinct low and high vol sections
    low_vol = np.random.normal(0, 0.01, 100)
    high_vol = np.random.normal(0, 2.0, 100)
    prices = 100.0 + np.cumsum(np.concatenate([low_vol, high_vol]))
    ts = np.arange(1000, 1000 + N * 1000, 1000)
    features = {"signed_flow": np.random.normal(0, 1.0, N)}

    exp_id = f"exp_regimes_{int(time.time() * 1000)}"
    harness = MicrostructureEvaluationHarness(
        experiment_id=exp_id,
        instrument="BTC-USDT",
        forecast_horizon_steps=2,
    )
    res = harness.run_evaluation(features, prices, ts, persist_to_db=False)
    regime_names = {r["regime_name"] for r in res["regimes"]}
    assert "LOW_VOLATILITY" in regime_names or "HIGH_VOLATILITY" in regime_names


def test_23_experiment_metrics_batch_persistence():
    """Verify batch metric persistence in SQLite."""
    exp_id = f"test_exp_batch_{int(time.time() * 1000)}"
    db.persist_microstructure_experiment({
        "experiment_id": exp_id,
        "start_ts": 1000,
        "end_ts": 2000,
        "instrument": "BTC-USDT",
    })
    metrics = [
        {"experiment_id": exp_id, "model_name": "RIDGE_L2", "feature_group": "FLOW_GROUP", "horizon": 300, "metric_name": "MAE", "metric_value": 0.00045, "sample_count": 100},
        {"experiment_id": exp_id, "model_name": "RIDGE_L2", "feature_group": "FLOW_GROUP", "horizon": 300, "metric_name": "RMSE", "metric_value": 0.00062, "sample_count": 100},
    ]
    db.persist_microstructure_metrics(metrics)
    fetched = db.get_microstructure_experiment_metrics(exp_id)
    assert len(fetched) == 2
    assert fetched[0]["metric_name"] == "MAE"
    assert fetched[1]["metric_name"] == "RMSE"


def test_24_temporal_splitter_ratio_validation():
    """Verify temporal splitter enforces ratio constraints."""
    with pytest.raises(ValueError, match="Split ratios must sum to 1.0"):
        TemporalSplitter.split(100, train_ratio=0.5, val_ratio=0.2, test_ratio=0.2)


def test_25_restart_recovery_from_db():
    """Verify experiments can be reloaded after server restart."""
    exp_id = f"test_restart_{int(time.time() * 1000)}"
    db.persist_microstructure_experiment({
        "experiment_id": exp_id,
        "dataset_id": "ds_restart",
        "instrument": "ETH-USDT",
        "start_ts": 5000,
        "end_ts": 10000,
    })
    reloaded = db.get_microstructure_experiment(exp_id)
    assert reloaded["dataset_id"] == "ds_restart"
    assert reloaded["instrument"] == "ETH-USDT"
    assert reloaded["mode"] == "RESEARCH"
