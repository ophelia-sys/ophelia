import pandas as pd
import numpy as np
from typing import List, Dict, Any
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
import lightgbm as lgb

class DriftBaseline:
    def __init__(self, task_type='regression'):
        self.task_type = task_type
        self.mean_val = 0.0
        
    def fit(self, X, y):
        if self.task_type == 'regression':
            self.mean_val = np.mean(y)
        else:
            self.mean_val = 1 if np.mean(y) > 0.5 else 0
            
    def predict(self, X):
        return np.full(X.shape[0], self.mean_val)

class HistoricalMLEngine:
    def __init__(self, target_col: str, feature_cols: List[str], model_type: str = 'ridge', task_type: str = 'regression'):
        self.target_col = target_col
        self.feature_cols = feature_cols
        self.model_type = model_type.lower()
        self.task_type = task_type.lower()
        
        if self.model_type == 'drift':
            self.model = DriftBaseline(self.task_type)
        elif self.model_type in ['logistic', 'logisticregression']:
            self.model = LogisticRegression(max_iter=1000)
            self.task_type = 'classification'
        elif self.model_type in ['linear', 'ridge']:
            self.model = Ridge()
            self.task_type = 'regression'
        elif self.model_type == 'tree':
            if self.task_type == 'regression':
                self.model = DecisionTreeRegressor(max_depth=3)
            else:
                self.model = DecisionTreeClassifier(max_depth=3)
        elif self.model_type == 'lightgbm':
            if self.task_type == 'regression':
                self.model = lgb.LGBMRegressor(n_estimators=100, max_depth=3, learning_rate=0.05)
            else:
                self.model = lgb.LGBMClassifier(n_estimators=100, max_depth=3, learning_rate=0.05)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

    def fit(self, df_dev: pd.DataFrame):
        # Drop rows with NaNs in features or target
        df = df_dev.dropna(subset=self.feature_cols + [self.target_col]).copy()
        
        if df.empty:
            raise ValueError("No data left after dropping NaNs in DEV set.")
            
        X = df[self.feature_cols].values
        y = df[self.target_col].values
        
        if self.task_type == 'classification':
            # Convert target to binary if not already
            if len(np.unique(y)) > 2:
                y = (y > 0).astype(int)
                
        self.model.fit(X, y)
        
    def predict_events(self, df_oos: pd.DataFrame, threshold: float = 0.0, return_horizon: int = 15) -> List[Dict[str, Any]]:
        df = df_oos.dropna(subset=self.feature_cols).copy()
        
        if df.empty:
            return []
            
        X = df[self.feature_cols].values
        
        if self.task_type == 'classification' and hasattr(self.model, 'predict_proba'):
            # Predict probability of class 1
            preds = self.model.predict_proba(X)[:, 1]
            # Map threshold roughly around 0.5
            threshold = 0.5 + threshold
        else:
            preds = self.model.predict(X)
            
        df['prediction'] = preds
        
        # Filter signals based on threshold
        signals = df[df['prediction'] > threshold].copy()
        
        events = []
        for idx, row in signals.iterrows():
            # Return column required by CalendarTimePortfolio
            ret_col = f"R_{return_horizon}"
            # True return for evaluation (raw)
            ret_val = row.get(f"R_{return_horizon}_raw", np.nan)
            
            event = {
                "timestamp": row['timestamp'],
                "symbol": row['symbol'],
                ret_col: ret_val,
                "prediction": row['prediction']
            }
            events.append(event)
            
        return events
