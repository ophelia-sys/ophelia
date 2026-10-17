import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
import xgboost as xgb

class BaselineModel:
    def fit(self, X, y):
        self.mean = y.mean()
    def predict_proba(self, X):
        return np.full((len(X), 2), [1 - self.mean, self.mean])

class PersistenceModel:
    def fit(self, X, y):
        pass
    def predict_proba(self, X):
        # Assumes 'ret_1' is the first column or similarly accessible. 
        # A true persistence model might just predict based on recent trend.
        # For simplicity, we predict 0.51 if ret_1 > 0 else 0.49
        ret_1 = X.iloc[:, 0] if hasattr(X, 'iloc') else X[:, 0]
        prob = np.where(ret_1 > 0, 0.51, 0.49)
        return np.column_stack([1 - prob, prob])

class LogisticRegressionWrapper:
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = LogisticRegression(max_iter=1000)
    def fit(self, X, y):
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
    def predict_proba(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)

class LightGBMWrapper:
    def __init__(self):
        self.model = lgb.LGBMClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, verbose=-1, random_state=42)
    def fit(self, X, y):
        self.model.fit(X, y)
    def predict_proba(self, X):
        return self.model.predict_proba(X)

class XGBoostWrapper:
    def __init__(self):
        self.model = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, verbosity=0, random_state=42)
    def fit(self, X, y):
        self.model.fit(X, y)
    def predict_proba(self, X):
        return self.model.predict_proba(X)

def get_model(name: str):
    models = {
        'baseline': BaselineModel(),
        'persistence': PersistenceModel(),
        'logistic': LogisticRegressionWrapper(),
        'lightgbm': LightGBMWrapper(),
        'xgboost': XGBoostWrapper()
    }
    return models[name]
