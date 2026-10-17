import pytest
import numpy as np
from research.phase6.statistics import newey_west_se, stationary_block_bootstrap, diebold_mariano_test

def test_newey_west_se():
    x = np.random.randn(100)
    y = 2.0 * x + np.random.randn(100)
    se = newey_west_se(x, y, max_lags=2)
    assert not np.isnan(se)
    assert se > 0

def test_stationary_block_bootstrap():
    data = np.arange(100)
    boot = stationary_block_bootstrap(data, block_size=10, num_bootstraps=5)
    assert boot.shape == (5, 100)
    
    # Check that blocks of contiguous elements exist
    # A difference of 1 implies contiguous block element
    diffs = np.diff(boot[0])
    contiguous_count = np.sum(diffs == 1)
    # With a block size of 10, we expect roughly 90% contiguous
    assert contiguous_count > 50

def test_diebold_mariano():
    # Model 1 has large error, Model 2 has small error
    e1 = np.random.randn(100) * 2.0
    e2 = np.random.randn(100) * 0.5
    
    stat, pval = diebold_mariano_test(e1, e2, h=1)
    assert not np.isnan(stat)
    assert not np.isnan(pval)
    assert stat > 0 # Since e1^2 - e2^2 will be positive on average

def test_fdr_bh():
    from research.phase6.statistics import fdr_bh
    # Typical example
    p_vals = np.array([0.01, 0.04, 0.03, 0.005, 0.20])
    adj_p = fdr_bh(p_vals)
    # The smallest p-value (0.005) is rank 1 (i=0): 0.005 * 5/1 = 0.025
    assert np.isclose(adj_p[3], 0.025)
    
def test_compute_excess_return():
    from research.phase6.statistics import compute_excess_return
    base = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    feat = np.array([0.05, 0.06, 0.07])
    # base mean = 0.03
    # feat mean = 0.06
    # excess = 0.03
    excess, eff, se = compute_excess_return(base, feat)
    assert np.isclose(excess, 0.03)
    assert eff > 0
    assert not np.isnan(se)
