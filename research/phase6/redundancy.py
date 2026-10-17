import numpy as np
import pandas as pd
from typing import Dict, Any

class FeatureRedundancyAnalyzer:
    """
    Evaluates whether Phase 6 features provide incremental predictive power
    beyond Ophelia's Baseline 5 features.
    """
    def __init__(self):
        pass
        
    def analyze_redundancy(self, df: pd.DataFrame, base_preds: pd.Series, model6_preds: pd.Series, labels: pd.Series) -> Dict[str, Any]:
        """
        Primary criterion: Does Phase 6 improve OOS predictive performance over Baseline 5?
        (Since this is the pipeline implementation, we simulate the correlation logic here)
        """
        if len(base_preds) == 0 or len(model6_preds) == 0:
            return {"status": "INSUFFICIENT_DATA"}
            
        # Spearman correlation between base predictions and model6 predictions
        try:
            from scipy.stats import spearmanr
            corr, pval = spearmanr(base_preds, model6_preds, nan_policy='omit')
        except ImportError:
            corr = np.corrcoef(base_preds.fillna(0), model6_preds.fillna(0))[0, 1]
            pval = 1.0
            
        # OOS MSE improvement
        base_mse = np.nanmean((labels - base_preds)**2)
        model6_mse = np.nanmean((labels - model6_preds)**2)
        
        improvement = (base_mse - model6_mse) / base_mse if base_mse > 0 else 0
        
        return {
            "spearman_correlation": float(corr),
            "base_mse": float(base_mse),
            "model6_mse": float(model6_mse),
            "mse_improvement": float(improvement),
            "is_redundant": improvement <= 0
        }
