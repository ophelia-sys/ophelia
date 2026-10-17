import pytest
import numpy as np
from research.ml4t_benchmark.features.hmm import FoldLocalHMM

@pytest.fixture
def synthetic_hmm_data():
    np.random.seed(42)
    # 2D input: (log return, realized vol)
    # Regime 0: low variance
    regime_0 = np.random.normal(0, 0.01, size=(200, 2))
    # Regime 1: high variance
    regime_1 = np.random.normal(0, 0.05, size=(200, 2))
    
    X_train = np.vstack([regime_0, regime_1])
    # Mix for OOS
    X_test = np.vstack([regime_1[:50], regime_0[:50]])
    return X_train, X_test

def test_hmm_determinism(synthetic_hmm_data):
    X_train, X_test = synthetic_hmm_data
    
    hmm1 = FoldLocalHMM(n_states=2, random_state=42)
    hmm1.fit(X_train)
    p1 = hmm1.filter_probabilities(X_test)
    
    hmm2 = FoldLocalHMM(n_states=2, random_state=42)
    hmm2.fit(X_train)
    p2 = hmm2.filter_probabilities(X_test)
    
    np.testing.assert_allclose(p1, p2, err_msg="HMM is not deterministic.")

def test_hmm_state_order_consistency(synthetic_hmm_data):
    X_train, _ = synthetic_hmm_data
    hmm = FoldLocalHMM(n_states=2, random_state=42)
    hmm.fit(X_train)
    
    # State 0 should be low variance, State 1 should be high variance
    var_0 = np.trace(hmm.model.covars_[0])
    var_1 = np.trace(hmm.model.covars_[1])
    
    assert var_0 < var_1, "HMM states were not deterministically sorted by variance."

def test_hmm_causality_future_perturbation(synthetic_hmm_data):
    X_train, X_test = synthetic_hmm_data
    
    hmm = FoldLocalHMM(n_states=2, random_state=42)
    hmm.fit(X_train)
    
    p_orig = hmm.filter_probabilities(X_test)
    
    # Perturb the future (last 10 rows)
    X_test_perturbed = X_test.copy()
    X_test_perturbed[-10:] += 10.0
    
    p_perturbed = hmm.filter_probabilities(X_test_perturbed)
    
    # The past (up to -10) should remain EXACTLY identical
    np.testing.assert_allclose(
        p_orig[:-10], 
        p_perturbed[:-10], 
        err_msg="HMM filter leaked future information backwards."
    )

def test_hmm_fold_local_parameter_isolation(synthetic_hmm_data):
    X_train, X_test = synthetic_hmm_data
    
    hmm = FoldLocalHMM(n_states=2, random_state=42)
    hmm.fit(X_train)
    
    # Record parameters
    means_before = hmm.model.means_.copy()
    covars_before = hmm.model.covars_.copy()
    
    # Filter OOS
    hmm.filter_probabilities(X_test)
    
    # Assert parameters are untouched
    np.testing.assert_allclose(means_before, hmm.model.means_)
    np.testing.assert_allclose(covars_before, hmm.model.covars_)

def test_hmm_gap_handling(synthetic_hmm_data):
    X_train, X_test = synthetic_hmm_data
    
    hmm = FoldLocalHMM(n_states=2, random_state=42)
    hmm.fit(X_train)
    
    # Inject NaN in the middle
    X_test_gapped = X_test.copy()
    X_test_gapped[5] = np.nan
    
    p_gapped = hmm.filter_probabilities(X_test_gapped)
    
    # Output should have NaN at index 5
    assert np.isnan(p_gapped[5]).all(), "HMM did not output NaN for missing input."
    # The next step should still be calculable (though it only did a time update at step 5)
    assert not np.isnan(p_gapped[6]).any(), "HMM failed to propagate state after a gap."
