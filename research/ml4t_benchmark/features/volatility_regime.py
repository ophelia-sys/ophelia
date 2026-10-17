import numpy as np
import pandas as pd
from arch import arch_model

class FoldLocalGARCH:
    """
    Causal GARCH(1,1) filter for Ophelia ML4T benchmark.
    
    Parameters (omega, alpha, beta, mu) are learned ONLY during fit() (train data).
    Conditional volatility is extracted recursively for OOS data.
    """
    def __init__(self, p: int = 1, q: int = 1):
        if p != 1 or q != 1:
            raise ValueError("Only GARCH(1,1) is supported in this causal adaptation.")
        self.p = p
        self.q = q
        self.omega = None
        self.alpha = None
        self.beta = None
        self.mu = None
        self.last_train_var = None
        self.last_train_resid_sq = None

    def fit(self, returns_train: np.ndarray) -> "FoldLocalGARCH":
        """
        Fits the GARCH model on training data.
        """
        # Ensure we drop NaNs for fitting
        mask = ~np.isnan(returns_train)
        returns_clean = returns_train[mask]

        if len(returns_clean) < 10:
            raise ValueError("Insufficient data to fit GARCH.")

        # Fit model
        model = arch_model(returns_clean, mean="Constant", vol="GARCH", p=self.p, q=self.q, dist="normal")
        result = model.fit(disp="off", show_warning=False)

        self.omega = result.params["omega"]
        self.alpha = result.params["alpha[1]"]
        self.beta = result.params["beta[1]"]
        self.mu = result.params["mu"]

        self.last_train_var = result.conditional_volatility[-1] ** 2
        self.last_train_resid_sq = (returns_clean[-1] - self.mu) ** 2

        return self

    def filter_volatility(self, returns: np.ndarray) -> np.ndarray:
        """
        Extract causal conditional volatility using frozen parameters.
        sigma_t^2 = omega + alpha * resid_{t-1}^2 + beta * sigma_{t-1}^2
        """
        if self.omega is None:
            raise ValueError("Model is not fitted.")

        n_samples = len(returns)
        vol = np.full(n_samples, np.nan)

        prev_var = self.last_train_var
        prev_resid_sq = self.last_train_resid_sq

        for t in range(n_samples):
            r_t = returns[t]

            # Compute current conditional variance prior to seeing r_t
            if prev_var is not None and prev_resid_sq is not None and not np.isnan(prev_var) and not np.isnan(prev_resid_sq):
                current_var = self.omega + self.alpha * prev_resid_sq + self.beta * prev_var
                vol[t] = np.sqrt(current_var)
            else:
                current_var = np.nan
                vol[t] = np.nan

            # State update for t+1
            if np.isnan(r_t):
                prev_var = np.nan
                prev_resid_sq = np.nan
            else:
                prev_var = current_var
                prev_resid_sq = (r_t - self.mu) ** 2

        return vol

def compute_ewma_volatility(returns: pd.Series, span: int = 120) -> pd.Series:
    """
    Causal EWMA volatility using pandas.
    """
    return returns.ewm(span=span, ignore_na=False).std()
