import pytest
import numpy as np
import pandas as pd
from research.ml4t_benchmark.features.volatility_regime import FoldLocalGARCH, compute_ewma_volatility

@pytest.fixture
def synthetic_returns():
    np.random.seed(42)
    # Generate 500 periods of noise
    return np.random.normal(0, 0.02, size=500)

def test_garch_determinism(synthetic_returns):
    X_train = synthetic_returns[:400]
    X_test = synthetic_returns[400:]
    
    garch1 = FoldLocalGARCH(p=1, q=1)
    garch1.fit(X_train)
    v1 = garch1.filter_volatility(X_test)
    
    garch2 = FoldLocalGARCH(p=1, q=1)
    garch2.fit(X_train)
    v2 = garch2.filter_volatility(X_test)
    
    np.testing.assert_allclose(v1, v2, err_msg="GARCH is not deterministic.")

def test_garch_causality_future_perturbation(synthetic_returns):
    X_train = synthetic_returns[:400]
    X_test = synthetic_returns[400:].copy()
    
    garch = FoldLocalGARCH(p=1, q=1)
    garch.fit(X_train)
    
    v_orig = garch.filter_volatility(X_test)
    
    # Perturb the future (last 10 rows)
    X_test_perturbed = X_test.copy()
    X_test_perturbed[-10:] += 0.5
    
    v_perturbed = garch.filter_volatility(X_test_perturbed)
    
    # The past (up to -10) should remain EXACTLY identical
    np.testing.assert_allclose(
        v_orig[:-10], 
        v_perturbed[:-10], 
        err_msg="GARCH filter leaked future information backwards."
    )

def test_garch_fold_local_parameter_isolation(synthetic_returns):
    X_train = synthetic_returns[:400]
    X_test = synthetic_returns[400:]
    
    garch = FoldLocalGARCH(p=1, q=1)
    garch.fit(X_train)
    
    omega_before = garch.omega
    alpha_before = garch.alpha
    beta_before = garch.beta
    
    garch.filter_volatility(X_test)
    
    assert garch.omega == omega_before
    assert garch.alpha == alpha_before
    assert garch.beta == beta_before

def test_garch_oos_initialization_continuity(synthetic_returns):
    X_train = synthetic_returns[:400]
    X_test = synthetic_returns[400:]
    
    garch = FoldLocalGARCH(p=1, q=1)
    garch.fit(X_train)
    
    # The very first OOS point uses the last_train_var and last_train_resid_sq
    v_test = garch.filter_volatility(X_test)
    
    expected_var = garch.omega + garch.alpha * garch.last_train_resid_sq + garch.beta * garch.last_train_var
    assert np.isclose(v_test[0], np.sqrt(expected_var)), "OOS continuity failed."

def test_garch_gap_handling(synthetic_returns):
    X_train = synthetic_returns[:400]
    X_test = synthetic_returns[400:].copy()
    
    garch = FoldLocalGARCH(p=1, q=1)
    garch.fit(X_train)
    
    # Inject NaN at index 5
    X_test[5] = np.nan
    v = garch.filter_volatility(X_test)
    
    # v[5] is the volatility for period 5, which depends on r_4. So v[5] is valid.
    # v[6] depends on r_5, which is NaN, so v[6] should be NaN.
    assert not np.isnan(v[5]), "GARCH incorrectly output NaN before the missing input affected the state."
    assert np.isnan(v[6]), "GARCH incorrectly fabricated variance after missing data."

def test_ewma_causality(synthetic_returns):
    series = pd.Series(synthetic_returns)
    v_orig = compute_ewma_volatility(series)
    
    series_perturbed = series.copy()
    series_perturbed.iloc[-10:] += 0.5
    v_perturbed = compute_ewma_volatility(series_perturbed)
    
    pd.testing.assert_series_equal(
        v_orig.iloc[:-10], 
        v_perturbed.iloc[:-10],
        check_exact=True,
        obj="EWMA causality failed"
    )

def test_ewma_gap_handling(synthetic_returns):
    series = pd.Series(synthetic_returns)
    series.iloc[5] = np.nan
    
    v = compute_ewma_volatility(series)
    # Pandas ewm with ignore_na=False decays the weights but doesn't strictly output NaN for the missing row
    # We just assert it doesn't crash and returns a valid series.
    assert len(v) == len(series)
    assert not v.isna().all(), "EWMA resulted in all NaNs."
