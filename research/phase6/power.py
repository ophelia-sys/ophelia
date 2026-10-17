import numpy as np
from typing import Dict, Any
from scipy.stats import norm

class PowerAnalysis:
    """
    Evaluates the statistical power of the empirical validation.
    Calculates Minimum Detectable Effect (MDE) and performs power 
    sensitivity analysis based on bootstrapped standard errors.
    """
    def __init__(self, desired_power: float = 0.8, alpha: float = 0.05):
        self.desired_power = desired_power
        self.alpha = alpha

    def analyze_power(self, baseline_std: float, n_eff: int, assumed_effects: list = [0.05, 0.10, 0.15, 0.20, 0.25]) -> Dict[str, Any]:
        """
        Calculates power metrics based on baseline variance and effective sample size.
        """
        if n_eff <= 1 or baseline_std <= 0:
            return {
                "estimated_n_eff": n_eff,
                "status": "UNDERPOWERED",
                "mde": None,
                "power_by_effect": {}
            }
            
        se = baseline_std / np.sqrt(n_eff)
        z_alpha = norm.ppf(1 - self.alpha / 2)
        z_beta = norm.ppf(self.desired_power)
        
        # MDE = (Z_{1-a/2} + Z_power) * SE
        mde = (z_alpha + z_beta) * se
        
        power_by_effect = {}
        is_powered = False
        
        for d_eff in assumed_effects:
            # d_eff is a standardized effect size (Cohen's d)
            # raw effect = d_eff * baseline_std
            # z_eff = raw effect / se = (d_eff * baseline_std) / (baseline_std / sqrt(n_eff)) = d_eff * sqrt(n_eff)
            z_eff = d_eff * np.sqrt(n_eff)
            pwr = norm.cdf(z_eff - z_alpha)
            power_by_effect[d_eff] = float(pwr)
            if pwr >= self.desired_power:
                is_powered = True
                
        return {
            "estimated_n_eff": n_eff,
            "mde": float(mde),
            "power_by_effect": power_by_effect,
            "status": "ADEQUATELY POWERED" if is_powered else "POWER SENSITIVITY ONLY — EFFECT SIZE UNKNOWN"
        }
