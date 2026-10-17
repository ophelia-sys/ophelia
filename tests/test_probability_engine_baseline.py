import pytest
import numpy as np
from sklearn.linear_model import LogisticRegression

def test_logistic_baseline():
    X = np.random.randn(100, 2)
    y = np.random.randint(0, 2, 100)
    
    clf = LogisticRegression()
    clf.fit(X, y)
    
    preds = clf.predict_proba(X)[:, 1]
    assert len(preds) == 100
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)

def test_net_expectancy():
    # Example computation check
    # E[Net] = prob_win * mag_win - prob_loss * mag_loss - fees + funding
    # Simplified here to check the baseline's core filter logic: E[Net] > 0
    p_win = 0.55
    r_win = 0.01  # 1%
    r_loss = 0.005 # 0.5%
    fees = 0.0012  # 12 bps
    
    e_gross = (p_win * r_win) - ((1 - p_win) * r_loss)
    e_net = e_gross - fees
    
    # 0.55 * 0.01 = 0.0055
    # 0.45 * 0.005 = 0.00225
    # gross = 0.00325 (32.5 bps)
    # net = 32.5 - 12 = 20.5 bps
    
    assert np.isclose(e_net, 0.00205)

if __name__ == "__main__":
    pytest.main([__file__])
