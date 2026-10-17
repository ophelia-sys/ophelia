import numpy as np
import pandas as pd

class DataSplitter:
    """
    Enforces the strict OOS lock required by Phase 5.1.
    Separates the dataset chronologically into:
    - Discovery (for stages A-E)
    - Locked OOS (for stage G only)
    """
    @staticmethod
    def split_discovery_oos(df: pd.DataFrame, split_date_str: str = "2023-09-01"):
        """
        Assumes df has a 'timestamp' column in milliseconds.
        """
        df = df.copy()
        if 'dt' not in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            
        split_date = pd.to_datetime(split_date_str)
        
        discovery = df[df['dt'] < split_date].copy().reset_index(drop=True)
        locked_oos = df[df['dt'] >= split_date].copy().reset_index(drop=True)
        
        # We can drop 'dt' if we want, but it's fine to keep it.
        return discovery, locked_oos

class PurgedWalkForwardValidation:
    """
    Implements chronologically safe Walk-Forward cross validation.
    Enforces 'embargo' between train and test sets to prevent overlapping label leakage.
    """
    def __init__(self, n_folds: int = 3, embargo: int = 60):
        self.n_folds = n_folds
        self.embargo = embargo
        
    def split(self, X):
        """
        Returns list of (train_idx, test_idx)
        """
        n_samples = len(X)
        fold_size = n_samples // (self.n_folds + 1)
        splits = []
        
        for i in range(self.n_folds):
            test_start = (i + 1) * fold_size
            
            # The last fold should consume the remaining samples
            if i == self.n_folds - 1:
                test_end = n_samples
            else:
                test_end = (i + 2) * fold_size
            
            if test_start >= n_samples:
                break
                
            train_end = test_start - self.embargo
            
            if train_end <= 0:
                continue
                
            train_idx = np.arange(0, train_end)
            test_idx = np.arange(test_start, test_end)
            
            if len(test_idx) == 0:
                continue
                
            splits.append((train_idx, test_idx))
            
        return splits
