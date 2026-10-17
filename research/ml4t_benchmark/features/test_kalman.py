import numpy as np
import pytest

from kalman import apply_kalman_local_linear, select_fold_local_qr

def kalman_local_linear_reference(
    prices: np.ndarray,
    observation_noise: float = 1.0,
    level_noise: float = 0.01,
    slope_noise: float = 0.001,
) -> dict:
    """
    Exact mathematical reference from ML4T kalman_local_linear, unmodified,
    except skipping np.isnan check because reference assumes clean data.
    """
    n = len(prices)
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q = np.array([[level_noise, 0.0], [0.0, slope_noise]])
    R = np.array([[observation_noise]])

    x = np.array([prices[0], 0.0])
    P = np.eye(2) * 10.0

    levels = np.zeros(n)
    slopes = np.zeros(n)
    innovations = np.zeros(n)
    uncertainties = np.zeros(n)

    for t in range(n):
        x_pred = F @ x
        P_pred = F @ P @ F.T + Q

        y = prices[t] - H @ x_pred
        S = H @ P_pred @ H.T + R

        K = P_pred @ H.T @ np.linalg.inv(S)

        x = x_pred + K @ y
        P = (np.eye(2) - K @ H) @ P_pred

        levels[t] = x[0]
        slopes[t] = x[1]
        innovations[t] = y[0]
        uncertainties[t] = P[0, 0]

    return {
        "level": levels,
        "slope": slopes,
        "innovation": innovations,
        "uncertainty": uncertainties,
    }


def test_repository_parity():
    """A. Repository parity test"""
    np.random.seed(42)
    prices = np.cumsum(np.random.normal(0, 1, 1000))
    
    R = 1.0
    Q_level = 0.01
    Q_slope = 0.001
    
    ref = kalman_local_linear_reference(prices, R, Q_level, Q_slope)
    slopes, innovations, uncertainties = apply_kalman_local_linear(prices, R, Q_level, Q_slope)
    
    np.testing.assert_allclose(slopes, ref["slope"], rtol=1e-5, atol=1e-8)
    np.testing.assert_allclose(innovations, ref["innovation"], rtol=1e-5, atol=1e-8)
    np.testing.assert_allclose(uncertainties, ref["uncertainty"], rtol=1e-5, atol=1e-8)


def test_measurement_update_and_causality():
    """C. Measurement update & D. Future perturbation causality"""
    np.random.seed(42)
    prices_base = np.cumsum(np.random.normal(0, 1, 1000))
    
    slopes_base, inn_base, unc_base = apply_kalman_local_linear(prices_base, 1.0, 0.01, 0.001)
    
    # Perturb the future at t >= 500
    prices_perturbed = prices_base.copy()
    prices_perturbed[500:] += 1000.0
    
    slopes_pert, inn_pert, unc_pert = apply_kalman_local_linear(prices_perturbed, 1.0, 0.01, 0.001)
    
    # Features before 500 must be exactly identical
    np.testing.assert_array_equal(slopes_base[:500], slopes_pert[:500])
    np.testing.assert_array_equal(inn_base[:500], inn_pert[:500])
    np.testing.assert_array_equal(unc_base[:500], unc_pert[:500])
    
    # Features at 500 should diverge (or at least innovations should)
    assert not np.allclose(inn_base[500:], inn_pert[500:])


def test_missing_data_prediction_recursion():
    """E. Missing-data prediction recursion"""
    # 2. CORRECT THE MISSING-DATA COVARIANCE TEST
    # 3. GAP STATE-MEAN TEST
    np.random.seed(42)
    prices = np.cumsum(np.random.normal(0, 1, 100))
    prices[50:60] = np.nan
    
    slopes, innovations, uncertainties = apply_kalman_local_linear(prices, 1.0, 0.01, 0.001)
    
    # Check that measurement update is skipped (innovation is NaN)
    assert np.all(np.isnan(innovations[50:60]))
    
    # Check that slope remains perfectly constant (slope_t = slope_prev)
    assert np.all(slopes[50:60] == slopes[49])
    
    # Check covariance recursion: P_t|t-1 = F P_{t-1|t-1} F^T + Q
    # We only have uncertainty (P00) available, but P00 should grow. 
    # Because P11 = P11_prev + Q11, and P01 = P01_prev + P11_prev, P00 grows quadratically.
    # Just verify that it is strictly monotonically increasing and not equal to a fixed increment.
    unc_gap = uncertainties[50:60]
    diffs = np.diff(unc_gap)
    assert np.all(diffs > 0)
    # Ensure it's not just growing by a fixed amount (Q_level)
    assert not np.allclose(diffs, diffs[0])


def test_missing_data_recovery():
    """F. Missing-data recovery"""
    np.random.seed(42)
    prices = np.cumsum(np.random.normal(0, 1, 100))
    prices[50:60] = np.nan
    
    slopes, innovations, uncertainties = apply_kalman_local_linear(prices, 1.0, 0.01, 0.001)
    
    # Check that when data resumes at 60, innovations are valid again
    assert not np.isnan(innovations[60])
    assert not np.isnan(slopes[60])


def test_initialization():
    """G. Initialization"""
    prices = np.array([100.0, 101.0, 102.0])
    slopes, innovations, uncertainties = apply_kalman_local_linear(prices, 1.0, 0.01, 0.001)
    
    # Step 0: x0 = 100.0, x1 = 0.0, P00 = 10, etc.
    # Predict step for t=0:
    # x_pred0 = 100.0
    # P_pred00 = 10 + 0 + 0 + 10 + 0.01 = 20.01
    # y = 100.0 -> inn = 0.0
    # S = 20.01 + 1.0 = 21.01
    # K0 = 20.01 / 21.01
    # P00 = (1 - K0) * 20.01 = (1/21.01) * 20.01 = 0.9524036...
    assert innovations[0] == 0.0
    assert slopes[0] == 0.0
    np.testing.assert_allclose(uncertainties[0], 20.01 - (20.01**2 / 21.01), rtol=1e-5)


def test_determinism():
    """H. Determinism"""
    np.random.seed(42)
    prices = np.cumsum(np.random.normal(0, 1, 100))
    
    sl1, in1, un1 = apply_kalman_local_linear(prices, 1.0, 0.01, 0.001)
    sl2, in2, un2 = apply_kalman_local_linear(prices, 1.0, 0.01, 0.001)
    
    np.testing.assert_array_equal(sl1, sl2)
    np.testing.assert_array_equal(in1, in2)
    np.testing.assert_array_equal(un1, un2)


def test_fold_local_qr_selection():
    """K. Fold-local Q/R isolation"""
    np.random.seed(42)
    # Generate a trend with a specific noise characteristic
    prices = np.cumsum(np.random.normal(0, 1, 1000))
    
    grid = [
        {"observation_noise": 1.0, "level_noise": 0.1, "slope_noise": 0.01}, # Fast
        {"observation_noise": 1.0, "level_noise": 0.01, "slope_noise": 0.001}, # Slow
    ]
    
    # Test that selection works
    best_config = select_fold_local_qr(prices, grid, validation_fraction=0.2)
    
    assert "observation_noise" in best_config
    assert "level_noise" in best_config
    assert "slope_noise" in best_config
    
if __name__ == "__main__":
    pytest.main(["-v", __file__])
