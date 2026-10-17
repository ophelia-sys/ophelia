import pandas as pd
import numpy as np
from typing import List, Dict
from .features import FeatureGenerator
from .labels import LabelGenerator
from .validation import PurgedWalkForwardValidation
from .models import get_model
from .metrics import MetricsEvaluator

class AblationFramework:
    """
    Evaluates incremental feature families chronologically.
    """
    def __init__(self, target_col='target_60', fwd_return_col='R_60', embargo=60):
        self.target_col = target_col
        self.fwd_return_col = fwd_return_col
        self.validator = PurgedWalkForwardValidation(n_folds=3, embargo=embargo)
        
    def run_ablation(self, df: pd.DataFrame, families_sequence: List[List[str]], model_name='logistic', costs_bps=12):
        """
        families_sequence: e.g. [['baseline'], ['baseline', 'volatility'], ...]
        """
        results = []
        
        # We must use exactly the SAME validation splits for every ablation step.
        # So we split on the underlying dataframe first.
        # But we must drop NaNs for the FULL feature set first so that all models
        # are trained and tested on the exact same rows.
        
        all_families = set()
        for fams in families_sequence:
            if isinstance(fams, str):
                all_families.add(fams)
            else:
                all_families.update(fams)
            
        full_df = FeatureGenerator.generate_features(df, list(all_families))
        full_df = LabelGenerator.generate_labels(full_df, horizons=[60])
        feature_cols = FeatureGenerator.get_feature_columns(list(all_families))
        
        # Drop rows with NaNs in any feature or target
        valid_cols = feature_cols + [self.target_col, self.fwd_return_col]
        full_df = full_df.dropna(subset=valid_cols).reset_index(drop=True)
        
        splits = self.validator.split(full_df)
        
        for families in families_sequence:
            print(f"Running Ablation for: {families}")
            current_features = FeatureGenerator.get_feature_columns(families)
            
            y_true_oos = []
            y_pred_oos = []
            R_fwd_oos = []
            
            for fold, (train_idx, test_idx) in enumerate(splits):
                if len(train_idx) < 100 or len(test_idx) < 100: continue
                
                X_train = full_df.loc[train_idx, current_features]
                y_train = full_df.loc[train_idx, self.target_col]
                
                X_test = full_df.loc[test_idx, current_features]
                y_test = full_df.loc[test_idx, self.target_col]
                R_test = full_df.loc[test_idx, self.fwd_return_col]
                
                model = get_model(model_name)
                model.fit(X_train, y_train)
                preds = model.predict_proba(X_test)[:, 1]
                
                y_true_oos.extend(y_test.values)
                y_pred_oos.extend(preds)
                R_fwd_oos.extend(R_test.values)
                
            y_true_oos = np.array(y_true_oos)
            y_pred_oos = np.array(y_pred_oos)
            R_fwd_oos = np.array(R_fwd_oos)
            
            metrics = MetricsEvaluator.evaluate(y_true_oos, y_pred_oos, R_fwd_oos, costs_bps=costs_bps)
            
            results.append({
                'families': "+".join(families),
                'metrics': metrics
            })
            
        return results
