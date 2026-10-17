import numpy as np
from numba import njit

@njit
def apply_kalman_local_linear(
    prices: np.ndarray,
    observation_noise: float,
    level_noise: float,
    slope_noise: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Applies a Local Linear Trend Kalman Filter to the input series.
    Missing values (NaN) are handled by propagating the state transition
    without performing a measurement update.
    
    State: [level, slope]
    F = [[1, 1],
         [0, 1]]
    H = [1, 0]
    
    Args:
        prices: 1D numpy array of observations (e.g. log close)
        observation_noise: R parameter
        level_noise: Q[0,0] parameter
        slope_noise: Q[1,1] parameter
        
    Returns:
        tuple of (slope, innovation, uncertainty)
    """
    n = len(prices)
    
    slopes = np.full(n, np.nan, dtype=np.float64)
    innovations = np.full(n, np.nan, dtype=np.float64)
    uncertainties = np.full(n, np.nan, dtype=np.float64)
    
    if n == 0:
        return slopes, innovations, uncertainties
        
    # Find first non-NaN price for initialization
    start_idx = 0
    while start_idx < n and np.isnan(prices[start_idx]):
        start_idx += 1
        
    if start_idx == n:
        return slopes, innovations, uncertainties
        
    # Initialize State and Covariance
    x0 = prices[start_idx]
    x1 = 0.0
    
    P00 = 10.0
    P01 = 0.0
    P10 = 0.0
    P11 = 10.0
    
    # Precompute Q and R
    Q00 = level_noise
    Q11 = slope_noise
    R = observation_noise
    
    for t in range(start_idx, n):
        # Predict Step
        # x_{t|t-1} = F * x_{t-1}
        x_pred0 = x0 + x1
        x_pred1 = x1
        
        # P_{t|t-1} = F * P_{t-1} * F^T + Q
        P_pred00 = P00 + P01 + P10 + P11 + Q00
        P_pred01 = P01 + P11
        P_pred10 = P10 + P11
        P_pred11 = P11 + Q11
        
        y_t = prices[t]
        
        if np.isnan(y_t):
            # Missing data: Skip measurement update
            # State coasts on prediction
            x0 = x_pred0
            x1 = x_pred1
            P00 = P_pred00
            P01 = P_pred01
            P10 = P_pred10
            P11 = P_pred11
            
            slopes[t] = x1
            innovations[t] = np.nan
            uncertainties[t] = P00
            
        else:
            # Innovation
            # y_t - H * x_{t|t-1}
            inn = y_t - x_pred0
            
            # Innovation Covariance S = H * P_{t|t-1} * H^T + R = P_pred00 + R
            S = P_pred00 + R
            
            # Kalman Gain K = P_{t|t-1} * H^T / S
            K0 = P_pred00 / S
            K1 = P_pred10 / S
            
            # Update State
            x0 = x_pred0 + K0 * inn
            x1 = x_pred1 + K1 * inn
            
            # Update Covariance P_{t|t} = (I - K * H) * P_{t|t-1}
            P00 = (1.0 - K0) * P_pred00
            P01 = (1.0 - K0) * P_pred01
            P10 = -K1 * P_pred00 + P_pred10
            P11 = -K1 * P_pred01 + P_pred11
            
            slopes[t] = x1
            innovations[t] = inn
            uncertainties[t] = P00

    return slopes, innovations, uncertainties


def select_fold_local_qr(
    prices_train: np.ndarray,
    candidate_grid: list[dict],
    validation_fraction: float = 0.2
) -> dict:
    """
    Selects the best Q/R configuration from a candidate grid using ONLY training data.
    
    Args:
        prices_train: The full chronological training partition.
        candidate_grid: List of dictionaries with keys 'observation_noise', 
                        'level_noise', 'slope_noise'.
        validation_fraction: The last portion of the training data used to validate.
        
    Returns:
        The dictionary of the selected best Q/R parameters.
    """
    n = len(prices_train)
    val_size = int(n * validation_fraction)
    train_size = n - val_size
    
    if val_size < 100:
        # Fallback if training is too small, just return the first
        return candidate_grid[0]
        
    # We define the selection metric as the mean squared innovation (prediction error)
    # on the validation portion of the training fold.
    # Note: innovation = y_t - x_{t|t-1}
    
    best_config = candidate_grid[0]
    best_mse = float('inf')
    
    for config in candidate_grid:
        obs_n = config["observation_noise"]
        lvl_n = config["level_noise"]
        slp_n = config["slope_noise"]
        
        _, innovations, _ = apply_kalman_local_linear(prices_train, obs_n, lvl_n, slp_n)
        
        # Calculate MSE on the validation portion
        # Exclude NaNs from the metric
        val_innovations = innovations[train_size:]
        valid_mask = ~np.isnan(val_innovations)
        
        if np.any(valid_mask):
            mse = np.mean(val_innovations[valid_mask]**2)
        else:
            mse = float('inf')
            
        if mse < best_mse:
            best_mse = mse
            best_config = config
            
    return best_config
