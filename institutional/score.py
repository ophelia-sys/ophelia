import numpy as np
import pandas as pd
from typing import List, Optional

def calculate_evidence_entropy(probabilities: List[float]) -> float:
    """
    Entropy: - sum(p_i * log2(p_i))
    Quantifies conflict or uncertainty among evidence probabilities.
    High entropy = high conflict / low agreement.
    """
    if not probabilities:
        return 0.0
    
    p = np.array(probabilities)
    # Filter out 0 to avoid log2(0)
    p = p[p > 0]
    
    if len(p) == 0:
        return 0.0
        
    return -np.sum(p * np.log2(p))

def calculate_advisory_volatility_score(volatility_ecdf_percentile: float) -> int:
    """
    Score = ceil(10 * ECDF(RV))
    Returns a score from 1 to 10 indicating historical relative volatility.
    1 = Lowest historical volatility
    10 = Highest historical volatility
    """
    if np.isnan(volatility_ecdf_percentile):
        return 5 # Default neutral
        
    # ECDF percentile is between 0.0 and 100.0
    ecdf_frac = volatility_ecdf_percentile / 100.0
    score = int(np.ceil(10 * ecdf_frac))
    
    # Bound to [1, 10]
    return max(1, min(10, score))

def calculate_composite_directional_probability(features: dict) -> Optional[float]:
    """
    Logistic Regression composite directional probability.
    P(Y=1|X) = 1 / [1 + exp(-(beta_0 + beta^T X))]
    Pending explicit out-of-sample calibration.
    """
    # For now, we return None until coefficients are calibrated.
    return None
