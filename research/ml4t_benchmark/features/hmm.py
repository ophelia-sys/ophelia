import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

class FoldLocalHMM:
    """
    Causal HMM filter for Ophelia ML4T benchmark.
    
    Parameters are learned ONLY during fit() (train data).
    Probabilities are extracted causally using forward filtering.
    """
    def __init__(self, n_states: int = 2, random_state: int = 42):
        self.n_states = n_states
        self.random_state = random_state
        self.model = None

    def fit(self, X_train: np.ndarray) -> "FoldLocalHMM":
        """
        Fits the HMM on training data and deterministically orders states by variance.
        """
        # Ensure we drop NaNs for fitting
        mask = ~np.isnan(X_train).any(axis=1)
        X_clean = X_train[mask]

        if len(X_clean) == 0:
            raise ValueError("No valid data to fit HMM.")

        # Fit model
        self.model = GaussianHMM(
            n_components=self.n_states,
            covariance_type="full",
            random_state=self.random_state,
            n_iter=100
        )
        self.model.fit(X_clean)

        # Sort states by variance (trace of covariance matrix)
        # Covariance shape is (n_components, n_features, n_features)
        variances = np.array([np.trace(cov) for cov in self.model.covars_])
        order = np.argsort(variances)
        
        # If the states are already sorted, we do nothing.
        # Otherwise, we reorder means, covars, transmat, and startprob.
        if not np.array_equal(order, np.arange(self.n_states)):
            self.model.means_ = self.model.means_[order]
            self.model.covars_ = self.model.covars_[order]
            self.model.transmat_ = self.model.transmat_[order, :][:, order]
            if hasattr(self.model, "startprob_"):
                self.model.startprob_ = self.model.startprob_[order]

        return self

    def filter_probabilities(self, X: np.ndarray) -> np.ndarray:
        """
        Extract causal regime probabilities P(State_t | X_{1:t}) using the forward algorithm.
        Outputs NaN for any row containing NaN inputs, but propagates the state belief
        via the transition matrix without a measurement update.
        """
        if self.model is None:
            raise ValueError("Model is not fitted.")

        n_samples = X.shape[0]
        n_components = self.n_states
        probs = np.full((n_samples, n_components), np.nan)

        log_startprob = np.log(self.model.startprob_ + 1e-300)
        log_transmat = np.log(self.model.transmat_ + 1e-300)

        prev_fwd = None

        for t in range(n_samples):
            obs = X[t:t+1]
            if np.isnan(obs).any():
                # Missing observation: propagate state via transition matrix only
                if prev_fwd is not None:
                    fwdlattice_t = np.zeros(n_components)
                    for j in range(n_components):
                        fwdlattice_t[j] = np.logaddexp.reduce(prev_fwd + log_transmat[:, j])
                    prev_fwd = fwdlattice_t
                continue
            
            # Compute log likelihood of this observation
            framelogprob = self.model._compute_log_likelihood(obs)[0]
            
            fwdlattice_t = np.zeros(n_components)
            if prev_fwd is None:
                # Initialize using start probabilities
                fwdlattice_t = log_startprob + framelogprob
            else:
                # Forward recursive update
                for j in range(n_components):
                    fwdlattice_t[j] = framelogprob[j] + np.logaddexp.reduce(prev_fwd + log_transmat[:, j])
            
            # Normalize to probabilities
            log_normalizer = np.logaddexp.reduce(fwdlattice_t)
            probs[t] = np.exp(fwdlattice_t - log_normalizer)
            
            # Update previous forward state
            prev_fwd = fwdlattice_t

        return probs
