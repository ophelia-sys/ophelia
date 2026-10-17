"""Ophelia Phase 6E: Integrated Microstructure Empirical Evaluation Framework.

Strictly RESEARCH_ONLY mode (zero trading authority).
Authoritative implementation of:
1. Research Experiment Registry & Immutable Tracking in SQLite.
2. Chronological Train/Val/Test Splitter with Purged and Embargoed Windows.
3. 8-Module Microstructure Feature Extraction & Baseline Forecasting Suite.
4. Diebold-Mariano Forecast Comparison with Newey-West/HAC Standard Errors.
5. Benjamini-Hochberg False Discovery Rate (FDR) Multiple Testing Correction.
6. Market Regime Segmentation (Volatility, Liquidity) & Cross-Asset Robustness.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from control_plane import db
from models.microstructure import (
    AblationResult,
    CrossAssetResult,
    EvaluationMetrics,
    ExperimentMetadata,
    RegimeResult,
)

# STRICT TRADING AUTHORITY INVARIANT: RESEARCH ONLY
TRADING_AUTHORITY = False
EXECUTION_GATED = True


# -----------------------------------------------------------------------------
# 1. Temporal Splitting with Purge and Embargo Windows
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SplitIndices:
    """Chronological split index ranges with purge and embargo."""
    train_indices: np.ndarray
    val_indices: np.ndarray
    test_indices: np.ndarray
    purge_steps: int
    embargo_steps: int


class TemporalSplitter:
    """Strict chronological splitter preventing forward label leakage."""

    @staticmethod
    def split(
        n_samples: int,
        train_ratio: float = 0.60,
        val_ratio: float = 0.20,
        test_ratio: float = 0.20,
        horizon_steps: int = 5,
        purge_steps: Optional[int] = None,
        embargo_steps: Optional[int] = None,
    ) -> SplitIndices:
        """Partition n_samples into train, validation, and test chronologically.
        
        Purge window: removes the final `purge_steps` from train and val to prevent
        forward-looking target overlap into subsequent partitions.
        Embargo window: removes `embargo_steps` from the start of val and test to
        eliminate residual autocorrelation and market impact decay.
        """
        if n_samples < 50:
            raise ValueError(f"Insufficient sample count for temporal split: {n_samples} < 50")
        if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-4:
            raise ValueError(f"Split ratios must sum to 1.0: {train_ratio + val_ratio + test_ratio}")

        p_steps = horizon_steps if purge_steps is None else purge_steps
        e_steps = max(1, int(math.ceil(horizon_steps * 0.5))) if embargo_steps is None else embargo_steps

        raw_train_end = int(n_samples * train_ratio)
        raw_val_end = int(n_samples * (train_ratio + val_ratio))

        train_end = max(0, raw_train_end - p_steps)
        train_idx = np.arange(0, train_end, dtype=int)

        val_start = raw_train_end + e_steps
        val_end = max(val_start, raw_val_end - p_steps)
        val_idx = np.arange(val_start, val_end, dtype=int) if val_start < val_end else np.array([], dtype=int)

        test_start = raw_val_end + e_steps
        test_idx = np.arange(test_start, n_samples, dtype=int) if test_start < n_samples else np.array([], dtype=int)

        if len(train_idx) == 0 or len(test_idx) == 0:
            raise ValueError(
                f"Sample size {n_samples} too small for horizon={horizon_steps}, "
                f"purge={p_steps}, embargo={e_steps}"
            )

        return SplitIndices(
            train_indices=train_idx,
            val_indices=val_idx,
            test_indices=test_idx,
            purge_steps=p_steps,
            embargo_steps=e_steps,
        )


class CausalStandardScaler:
    """Standard scaler strictly fitted on training partition to prevent lookahead."""

    def __init__(self, eps: float = 1e-8):
        self.eps = eps
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "CausalStandardScaler":
        X = np.asarray(X, dtype=float)
        self.mean_ = np.nanmean(X, axis=0)
        self.std_ = np.nanstd(X, axis=0)
        self.std_ = np.where(self.std_ < self.eps, 1.0, self.std_)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            raise ValueError("Scaler must be fitted before transforming")
        X = np.asarray(X, dtype=float)
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)


# -----------------------------------------------------------------------------
# 2. Statistical Comparison Suite (Diebold-Mariano & Benjamini-Hochberg)
# -----------------------------------------------------------------------------

def norm_cdf(z: float) -> float:
    """Exact standard normal cumulative distribution using math.erf."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class DieboldMarianoTest:
    """Diebold-Mariano (1995) test with Newey-West/HAC variance estimation."""

    @staticmethod
    def compute(
        e1: np.ndarray,
        e2: np.ndarray,
        horizon_steps: int = 1,
        loss_type: str = "MAE",
    ) -> Dict[str, float]:
        """Compute Diebold-Mariano test comparing baseline (e1) vs candidate (e2).
        
        loss_type: 'MAE' (|e|) or 'MSE' (e^2).
        Positive DM statistic indicates candidate model has lower loss than baseline.
        """
        e1 = np.asarray(e1, dtype=float)
        e2 = np.asarray(e2, dtype=float)
        if len(e1) != len(e2):
            raise ValueError(f"Error arrays must have identical length: {len(e1)} != {len(e2)}")
        T = len(e1)
        if T < 10:
            return {"dm_stat": 0.0, "p_value": 1.0, "mean_diff": 0.0, "hac_std": 1.0}

        if loss_type.upper() == "MAE":
            d = np.abs(e1) - np.abs(e2)
        elif loss_type.upper() == "MSE":
            d = (e1 ** 2) - (e2 ** 2)
        else:
            raise ValueError(f"Unsupported loss_type: {loss_type}")

        d_bar = float(np.mean(d))
        d_centered = d - d_bar

        # Autocovariance gamma_0
        gamma_0 = float(np.dot(d_centered, d_centered) / T)

        # HAC Bartlett kernel out to max(1, horizon_steps - 1)
        h = max(1, int(horizon_steps))
        gamma_sum = 0.0
        for k in range(1, h):
            weight = 1.0 - (k / float(h))
            gamma_k = float(np.dot(d_centered[k:], d_centered[:-k]) / T)
            gamma_sum += 2.0 * weight * gamma_k

        lr_var = (gamma_0 + gamma_sum) / float(T)
        if lr_var <= 1e-12:
            lr_var = max(1e-12, gamma_0 / float(T))

        hac_std = math.sqrt(lr_var)
        dm_stat = d_bar / hac_std if hac_std > 1e-12 else 0.0

        # Two-sided p-value against N(0, 1)
        p_val = 2.0 * (1.0 - norm_cdf(abs(dm_stat)))
        p_val = max(0.0, min(1.0, p_val))

        return {
            "dm_stat": float(round(dm_stat, 4)),
            "p_value": float(round(p_val, 6)),
            "mean_diff": float(round(d_bar, 6)),
            "hac_std": float(round(hac_std, 6)),
        }


class BenjaminiHochberg:
    """Benjamini-Hochberg (1995) procedure for False Discovery Rate (FDR) control."""

    @staticmethod
    def adjust(
        p_values: Sequence[float],
        alpha: float = 0.05,
    ) -> List[Tuple[float, float, bool]]:
        """Return list of (raw_p, adjusted_p, is_significant) matching original order."""
        m = len(p_values)
        if m == 0:
            return []

        # Sort indices by raw p-value
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        adj_p = [0.0] * m

        # Step-up adjustment: q_(i) = min_{k >= i} (m / k * p_(k))
        running_min = 1.0
        for rank in range(m, 0, -1):
            idx, p = indexed[rank - 1]
            q = (float(m) / float(rank)) * p
            running_min = min(running_min, q)
            adj_p[idx] = min(1.0, max(0.0, running_min))

        results = []
        for i in range(m):
            raw = p_values[i]
            q = adj_p[i]
            sig = bool(q <= alpha)
            results.append((float(round(raw, 6)), float(round(q, 6)), sig))
        return results


# -----------------------------------------------------------------------------
# 3. Microstructure Feature Extractor & Module Groups
# -----------------------------------------------------------------------------

MODULE_FEATURE_GROUPS: Dict[str, List[str]] = {
    "FLOW_GROUP": ["signed_flow", "flow_innovation", "flow_zscore"],
    "DURATION_GROUP": ["duration_delta_t", "arrival_intensity", "duration_zscore"],
    "OBI_GROUP": ["obi_l1", "obi_l5", "obi_l10"],
    "LIQUIDITY_GROUP": ["relative_spread", "spread_stress", "depth_stress"],
    "IMPACT_GROUP": ["kyle_lambda", "impact_asymmetry", "impact_r2"],
    "TOXICITY_GROUP": ["vpin_imbalance", "adverse_price_response", "flow_intensity"],
    "HASBROUCK_GROUP": ["cumulative_impact_H20", "variance_share_flow", "permanent_impact"],
    "VECM_GROUP": ["beta_coeff", "alpha_1", "alpha_2", "bounded_speed_share_1", "bounded_speed_share_2"],
}

# Coherent super-groups for structured ablation
COHERENT_SUPER_GROUPS: Dict[str, List[str]] = {
    "FLOW_AND_DURATION": MODULE_FEATURE_GROUPS["FLOW_GROUP"] + MODULE_FEATURE_GROUPS["DURATION_GROUP"],
    "BOOK_AND_LIQUIDITY": MODULE_FEATURE_GROUPS["OBI_GROUP"] + MODULE_FEATURE_GROUPS["LIQUIDITY_GROUP"],
    "IMPACT_AND_TOXICITY": MODULE_FEATURE_GROUPS["IMPACT_GROUP"] + MODULE_FEATURE_GROUPS["TOXICITY_GROUP"],
    "ECONOMETRIC_GROUP": MODULE_FEATURE_GROUPS["HASBROUCK_GROUP"] + MODULE_FEATURE_GROUPS["VECM_GROUP"],
    "ALL_MICROSTRUCTURE": [
        f for group in MODULE_FEATURE_GROUPS.values() for f in group
    ],
}


# -----------------------------------------------------------------------------
# 4. Baseline Forecasting Models & Evaluator
# -----------------------------------------------------------------------------

class MetricsCalculator:
    """Comprehensive evaluation metrics."""

    @staticmethod
    def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(np.abs(y_true - y_pred)))

    @staticmethod
    def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(math.sqrt(np.mean((y_true - y_pred) ** 2)))

    @staticmethod
    def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        sign_true = np.sign(y_true)
        sign_pred = np.sign(y_pred)
        matches = (sign_true == sign_pred)
        return float(np.mean(matches))

    @staticmethod
    def rank_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Spearman rank correlation coefficient."""
        if len(y_true) < 3:
            return 0.0
        
        def _rank(a: np.ndarray) -> np.ndarray:
            temp = np.argsort(a)
            ranks = np.empty_like(temp, dtype=float)
            ranks[temp] = np.arange(len(a), dtype=float) + 1.0
            return ranks

        rx = _rank(y_true)
        ry = _rank(y_pred)
        std_x = np.std(rx)
        std_y = np.std(ry)
        if std_x < 1e-12 or std_y < 1e-12:
            return 0.0
        corr = np.corrcoef(rx, ry)[0, 1]
        return float(corr) if not np.isnan(corr) else 0.0

    @staticmethod
    def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, tau: float = 0.5) -> float:
        diff = y_true - y_pred
        loss = np.maximum(tau * diff, (tau - 1.0) * diff)
        return float(np.mean(loss))


class L2RidgeRegressor:
    """Fast deterministic closed-form Ridge Regression with L2 regularization."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.weights_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "L2RidgeRegressor":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        N, D = X.shape
        # Add intercept column
        X_design = np.hstack([np.ones((N, 1), dtype=float), X])
        # Regularization matrix (do not regularize intercept)
        reg = self.alpha * np.eye(D + 1, dtype=float)
        reg[0, 0] = 0.0
        # Solve (X^T X + alpha I) w = X^T y
        XtX = np.dot(X_design.T, X_design) + reg
        Xty = np.dot(X_design.T, y)
        w = np.linalg.solve(XtX, Xty)
        self.intercept_ = float(w[0])
        self.weights_ = w[1:]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.weights_ is None:
            raise ValueError("Model must be fitted before predict")
        X = np.asarray(X, dtype=float)
        return self.intercept_ + np.dot(X, self.weights_)


# -----------------------------------------------------------------------------
# 5. Integrated Microstructure Empirical Evaluation Harness
# -----------------------------------------------------------------------------

class MicrostructureEvaluationHarness:
    """Orchestrates comprehensive multi-module ablation, testing, and registry."""

    def __init__(
        self,
        experiment_id: str,
        instrument: str = "BTC-USDT",
        venue: str = "BINGX",
        asset_class: str = "CRYPTO",
        forecast_horizon_steps: int = 5,
        sampling_interval_ms: int = 1000,
    ):
        self.experiment_id = experiment_id
        self.instrument = instrument
        self.venue = venue
        self.asset_class = asset_class
        self.forecast_horizon_steps = forecast_horizon_steps
        self.sampling_interval_ms = sampling_interval_ms

    def run_evaluation(
        self,
        features_dict: Dict[str, np.ndarray],
        prices: np.ndarray,
        timestamps_ms: np.ndarray,
        volumes: Optional[np.ndarray] = None,
        train_ratio: float = 0.60,
        val_ratio: float = 0.20,
        test_ratio: float = 0.20,
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        """Execute chronological evaluation, baselines, ablations, and regime analysis."""
        N = len(prices)
        if N < 60:
            raise ValueError(f"Insufficient sample count for evaluation: {N} < 60")

        # 1. Target generation: forward log return y_{t+h} = ln(P_{t+h} / P_t)
        h = self.forecast_horizon_steps
        forward_returns = np.zeros(N, dtype=float)
        for t in range(N - h):
            p_t = prices[t]
            p_th = prices[t + h]
            if p_t > 0 and p_th > 0:
                forward_returns[t] = math.log(p_th / p_t)
            else:
                forward_returns[t] = 0.0

        # Valid range for training is 0 to N - h
        valid_N = N - h
        valid_prices = prices[:valid_N]
        valid_returns = forward_returns[:valid_N]
        valid_ts = timestamps_ms[:valid_N]

        # 2. Strict chronological split with purge and embargo
        splits = TemporalSplitter.split(
            n_samples=valid_N,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            horizon_steps=h,
        )

        train_idx = splits.train_indices
        test_idx = splits.test_indices

        y_train = valid_returns[train_idx]
        y_test = valid_returns[test_idx]

        # 3. Construct Baselines
        # Baseline 1: Naive Persistence (0 return expected)
        y_pred_naive = np.zeros_like(y_test)
        e_naive = y_test - y_pred_naive

        # Baseline 2: EMA Baseline of past returns
        past_returns = np.zeros(valid_N, dtype=float)
        past_returns[1:] = np.diff(np.log(np.maximum(valid_prices, 1e-8)))
        ema_returns = np.zeros(valid_N, dtype=float)
        alpha_ema = 2.0 / (10.0 + 1.0)
        for i in range(1, valid_N):
            ema_returns[i] = alpha_ema * past_returns[i] + (1.0 - alpha_ema) * ema_returns[i - 1]
        y_pred_ema = ema_returns[test_idx]
        e_ema = y_test - y_pred_ema

        # Baseline 3: Momentum Baseline (rolling return over h steps)
        mom_returns = np.zeros(valid_N, dtype=float)
        for i in range(h, valid_N):
            mom_returns[i] = math.log(valid_prices[i] / valid_prices[i - h])
        y_pred_mom = mom_returns[test_idx]
        e_mom = y_test - y_pred_mom

        # Collect Baseline Metrics
        baseline_metrics: Dict[str, EvaluationMetrics] = {}
        for b_name, preds, errs in [
            ("NAIVE_PERSISTENCE", y_pred_naive, e_naive),
            ("EMA_BASELINE", y_pred_ema, e_ema),
            ("MOMENTUM_BASELINE", y_pred_mom, e_mom),
        ]:
            b_met = EvaluationMetrics(
                experiment_id=self.experiment_id,
                model_name=b_name,
                feature_group="BASELINE_CONTROL",
                horizon=h * self.sampling_interval_ms // 1000,
                mae=MetricsCalculator.mae(y_test, preds),
                rmse=MetricsCalculator.rmse(y_test, preds),
                directional_accuracy=MetricsCalculator.directional_accuracy(y_test, preds),
                rank_ic=MetricsCalculator.rank_ic(y_test, preds),
                pinball_loss_p50=MetricsCalculator.pinball_loss(y_test, preds, 0.5),
                sample_count=len(y_test),
            )
            baseline_metrics[b_name] = b_met

        # 4. Evaluate Feature Groups
        all_groups = {**MODULE_FEATURE_GROUPS, **COHERENT_SUPER_GROUPS}
        group_metrics: Dict[str, EvaluationMetrics] = {}
        group_errors: Dict[str, np.ndarray] = {}

        for group_name, feat_names in all_groups.items():
            # Build feature matrix
            cols = []
            for fn in feat_names:
                if fn in features_dict:
                    cols.append(features_dict[fn][:valid_N])
                else:
                    # Missing feature: fill with column mean on train or NaN tracking
                    cols.append(np.zeros(valid_N, dtype=float))
            X_all = np.column_stack(cols)

            X_train = X_all[train_idx]
            X_test = X_all[test_idx]

            # Scale strictly on train
            scaler = CausalStandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Fit Ridge Model
            model = L2RidgeRegressor(alpha=1.0)
            model.fit(X_train_scaled, y_train)
            preds = model.predict(X_test_scaled)
            errs = y_test - preds

            group_errors[group_name] = errs
            g_met = EvaluationMetrics(
                experiment_id=self.experiment_id,
                model_name="RIDGE_L2",
                feature_group=group_name,
                horizon=h * self.sampling_interval_ms // 1000,
                mae=MetricsCalculator.mae(y_test, preds),
                rmse=MetricsCalculator.rmse(y_test, preds),
                directional_accuracy=MetricsCalculator.directional_accuracy(y_test, preds),
                rank_ic=MetricsCalculator.rank_ic(y_test, preds),
                pinball_loss_p50=MetricsCalculator.pinball_loss(y_test, preds, 0.5),
                sample_count=len(y_test),
            )
            group_metrics[group_name] = g_met

        # 5. Compute Diebold-Mariano Tests vs Naive Baseline & Benjamini-Hochberg FDR
        ablation_raw: List[Dict[str, Any]] = []
        raw_p_values: List[float] = []

        naive_mae = baseline_metrics["NAIVE_PERSISTENCE"].mae
        naive_rmse = baseline_metrics["NAIVE_PERSISTENCE"].rmse
        naive_dir_acc = baseline_metrics["NAIVE_PERSISTENCE"].directional_accuracy

        for group_name, g_met in group_metrics.items():
            errs = group_errors[group_name]
            dm = DieboldMarianoTest.compute(
                e1=e_naive,
                e2=errs,
                horizon_steps=h,
                loss_type="MAE",
            )
            raw_p = dm["p_value"]
            raw_p_values.append(raw_p)

            delta_mae = g_met.mae - naive_mae
            delta_rmse = g_met.rmse - naive_rmse
            delta_dir_acc = g_met.directional_accuracy - naive_dir_acc

            ablation_raw.append({
                "group_name": group_name,
                "delta_mae": delta_mae,
                "delta_rmse": delta_rmse,
                "delta_dir_acc": delta_dir_acc,
                "dm_stat": dm["dm_stat"],
                "raw_p_value": raw_p,
            })

        # Apply FDR correction
        fdr_results = BenjaminiHochberg.adjust(raw_p_values, alpha=0.05)
        ablation_results: List[AblationResult] = []
        for i, ab in enumerate(ablation_raw):
            raw_p, adj_p, is_sig = fdr_results[i]
            res = AblationResult(
                experiment_id=self.experiment_id,
                baseline_name="NAIVE_PERSISTENCE",
                feature_group=ab["group_name"],
                horizon=h * self.sampling_interval_ms // 1000,
                delta_mae=float(round(ab["delta_mae"], 6)),
                delta_rmse=float(round(ab["delta_rmse"], 6)),
                delta_dir_acc=float(round(ab["delta_dir_acc"], 4)),
                dm_stat=float(round(ab["dm_stat"], 4)),
                raw_p_value=raw_p,
                adjusted_p_value=adj_p,
                is_significant=is_sig,
            )
            ablation_results.append(res)

        # 6. Regime Robustness Segmentation
        # Split test partition into volatility regimes (low, normal, high) based on rolling volatility
        test_prices = valid_prices[test_idx]
        test_vol = np.zeros(len(test_prices), dtype=float)
        for i in range(5, len(test_prices)):
            test_vol[i] = float(np.std(test_prices[i-5:i]))

        q33 = float(np.quantile(test_vol, 0.33))
        q66 = float(np.quantile(test_vol, 0.66))

        regime_results: List[RegimeResult] = []
        for reg_name, mask in [
            ("LOW_VOLATILITY", test_vol <= q33),
            ("NORMAL_VOLATILITY", (test_vol > q33) & (test_vol <= q66)),
            ("HIGH_VOLATILITY", test_vol > q66),
        ]:
            if np.sum(mask) >= 5:
                reg_y_true = y_test[mask]
                for g_name in ["FLOW_GROUP", "ALL_MICROSTRUCTURE"]:
                    g_errs = group_errors[g_name][mask]
                    reg_mae = float(np.mean(np.abs(g_errs)))
                    regime_results.append(RegimeResult(
                        experiment_id=self.experiment_id,
                        regime_name=reg_name,
                        feature_group=g_name,
                        metric_name="MAE",
                        metric_value=float(round(reg_mae, 6)),
                        sample_count=int(np.sum(mask)),
                    ))

        # 7. Cross-Asset Result Representation
        cross_asset_results: List[CrossAssetResult] = [
            CrossAssetResult(
                experiment_id=self.experiment_id,
                instrument=self.instrument,
                asset_class=self.asset_class,
                feature_group=ab.feature_group,
                metric_name="DELTA_MAE",
                metric_value=ab.delta_mae,
                sample_count=len(y_test),
            )
            for ab in ablation_results
        ]

        # 8. Immutable Experiment Registration in SQLite
        exp_meta = ExperimentMetadata(
            experiment_id=self.experiment_id,
            dataset_id=f"dataset_{self.instrument.lower()}_{len(prices)}ticks",
            instrument=self.instrument,
            venue=self.venue,
            asset_class=self.asset_class,
            start_ts=int(timestamps_ms[0]),
            end_ts=int(timestamps_ms[-1]),
            sampling_interval_ms=self.sampling_interval_ms,
            forecast_horizon_s=h * self.sampling_interval_ms // 1000,
            feature_schema_version="v1.1",
            methodology_versions="MICROSTRUCTURE_EVAL_V1",
            code_commit="phase6e_production",
            config_hash=hashlib.sha256(f"{self.experiment_id}_{h}_{len(prices)}".encode()).hexdigest()[:16],
            mode="RESEARCH",
        )

        if persist_to_db:
            db.persist_microstructure_experiment(exp_meta.to_dict())

            # Persist metrics
            metrics_payload = []
            for bm in baseline_metrics.values():
                metrics_payload.extend(bm.to_dict_list())
            for gm in group_metrics.values():
                metrics_payload.extend(gm.to_dict_list())
            db.persist_microstructure_metrics(metrics_payload)

            # Persist ablations
            db.persist_microstructure_ablation_results([ab.to_dict() for ab in ablation_results])

            # Persist regimes
            db.persist_microstructure_regime_results([rr.to_dict() for rr in regime_results])

            # Persist cross-asset
            db.persist_microstructure_cross_asset_results([ca.to_dict() for ca in cross_asset_results])

        return {
            "experiment": exp_meta.to_dict(),
            "baseline_metrics": {k: v.to_dict_list() for k, v in baseline_metrics.items()},
            "group_metrics": {k: v.to_dict_list() for k, v in group_metrics.items()},
            "ablations": [ab.to_dict() for ab in ablation_results],
            "regimes": [rr.to_dict() for rr in regime_results],
            "cross_asset": [ca.to_dict() for ca in cross_asset_results],
        }
