import numpy as np
from numba import njit

@njit
def get_ffd_weights(d: float, threshold: float = 1e-4, max_len: int = 100000) -> np.ndarray:
    """
    Computes Fractional Differencing weights (binomial series).
    Returns array of weights that are strictly >= threshold in absolute magnitude.
    """
    if d == 0:
        return np.array([1.0])
        
    weights = np.zeros(max_len)
    weights[0] = 1.0
    
    for k in range(1, max_len):
        w = -weights[k - 1] * (d - k + 1) / k
        if abs(w) < threshold:
            return weights[:k]
        weights[k] = w
        
    return weights

@njit
def apply_ffd(series: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """
    Applies the full-window convention FFD.
    Output will have exactly len(weights) - 1 leading NaNs.
    """
    n = len(series)
    w_len = len(weights)
    out = np.full(n, np.nan)
    
    # Strictly causal convolution.
    # Start at w_len - 1 to drop the boundary-partial warmup rows.
    for i in range(w_len - 1, n):
        dot_product = 0.0
        for j in range(w_len):
            dot_product += series[i - j] * weights[j]
        out[i] = dot_product
        
    return out
