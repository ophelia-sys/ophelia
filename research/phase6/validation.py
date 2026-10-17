import pandas as pd
from typing import List, Tuple

class WalkForwardValidator:
    """
    Implements chronological purged walk-forward validation.
    """
    def __init__(self, embargo_seconds: int = 86400):
        self.embargo_seconds = embargo_seconds

    def generate_folds(self, df: pd.DataFrame, n_folds: int, train_ratio: float = 0.7, max_horizon_seconds: int = 3600) -> List[dict]:
        """
        Generates purged and embargoed Train/Test splits chronologically.
        Does NOT use random k-fold.
        Returns a list of dictionaries with dataframes and metadata.
        """
        if df.empty or 'timestamp' not in df.columns:
            return []
            
        total_time = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
        fold_time = total_time / n_folds
        
        folds = []
        for i in range(n_folds):
            start_t = df['timestamp'].iloc[0] + i * fold_time
            end_t = start_t + fold_time if i < n_folds - 1 else df['timestamp'].iloc[-1]
            
            fold_df = df[(df['timestamp'] >= start_t) & (df['timestamp'] <= end_t)]
            if fold_df.empty:
                continue
                
            train_time = start_t + (end_t - start_t) * train_ratio
            
            train_df = fold_df[fold_df['timestamp'] <= train_time]
            
            # The purge removes training data that overlaps with forward labels.
            purge_start = train_time
            purge_end = train_time + max_horizon_seconds * 1000
            
            embargo_start = purge_end
            embargo_end = purge_end + self.embargo_seconds * 1000
            
            test_start = embargo_end
            test_df = fold_df[fold_df['timestamp'] > test_start]
            
            if not train_df.empty and not test_df.empty:
                folds.append({
                    "train_df": train_df,
                    "test_df": test_df,
                    "train_start": int(train_df['timestamp'].iloc[0]),
                    "train_end": int(train_df['timestamp'].iloc[-1]),
                    "purge_start": int(purge_start),
                    "purge_end": int(purge_end),
                    "embargo_start": int(embargo_start),
                    "embargo_end": int(embargo_end),
                    "test_start": int(test_df['timestamp'].iloc[0]),
                    "test_end": int(test_df['timestamp'].iloc[-1]),
                    "train_event_count": 0, # To be filled
                    "test_event_count": 0   # To be filled
                })
                
        return folds
