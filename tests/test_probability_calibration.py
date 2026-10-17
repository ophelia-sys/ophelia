import pytest
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

def test_platt_scaling_bounds():
    # Simulate some raw decision scores
    raw_scores = np.random.randn(100, 1) * 2
    y_calib = np.random.randint(0, 2, 100)
    
    calibrator = LogisticRegression()
    calibrator.fit(raw_scores, y_calib)
    
    test_scores = np.random.randn(50, 1) * 3
    calib_preds = calibrator.predict_proba(test_scores)[:, 1]
    
    # Predictions must be strictly in [0, 1]
    assert np.all(calib_preds >= 0.0)
    assert np.all(calib_preds <= 1.0)

def test_brier_score_logic():
    # Perfect predictions
    y_true = np.array([1, 0, 1, 0])
    y_pred_perf = np.array([1.0, 0.0, 1.0, 0.0])
    b_perf = brier_score_loss(y_true, y_pred_perf)
    assert b_perf == 0.0
    
    # Worst predictions
    y_pred_worst = np.array([0.0, 1.0, 0.0, 1.0])
    b_worst = brier_score_loss(y_true, y_pred_worst)
    assert b_worst == 1.0

if __name__ == "__main__":
    pytest.main([__file__])
