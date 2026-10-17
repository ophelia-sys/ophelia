import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional

def compute_excess_return(baseline: np.ndarray, feature_returns: np.ndarray) -> Tuple[float, float, float]:
    """
    Computes excess return, effect size (Cohen's d equivalent), and standard error of the excess return.
    """
    b = np.asarray(baseline)
    f = np.asarray(feature_returns)
    b = b[~np.isnan(b)]
    f = f[~np.isnan(f)]
    
    if len(b) == 0 or len(f) == 0:
        return np.nan, np.nan, np.nan
        
    mu_b = np.mean(b)
    mu_f = np.mean(f)
    var_b = np.var(b, ddof=1) if len(b) > 1 else 0
    var_f = np.var(f, ddof=1) if len(f) > 1 else 0
    
    excess = mu_f - mu_b
    
    pooled_sd = np.sqrt(var_b) # Use market (baseline) SD as the true variance denominator
    effect_size = excess / pooled_sd if pooled_sd > 0 else 0
    se = np.sqrt(var_b/len(b) + var_f/len(f)) if len(b) > 0 and len(f) > 0 else np.nan
    
    return float(excess), float(effect_size), float(se)

class CalendarTimePortfolio:
    """
    Constructs a Calendar Time Portfolio (CTP) for sparse, multi-symbol event studies.
    Aggregates overlapping and cross-sectional events onto a uniform calendar grid.
    """
    def __init__(self, events: List[Dict[str, Any]], horizon: int, bin_freq: str = '1h', weighting: str = 'equal_symbol'):
        """
        weighting: 'equal_event' (every event has equal weight in the bin) 
                   'equal_symbol' (events are averaged per symbol first, then across symbols)
        """
        self.events = events
        self.horizon = horizon
        self.bin_freq = bin_freq
        self.weighting = weighting
        
        self._build_portfolio()

    def _build_portfolio(self):
        if not self.events:
            self.portfolio_series = pd.Series(dtype=float)
            self.event_counts = pd.Series(dtype=int)
            return
            
        df = pd.DataFrame(self.events)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['bin'] = df['datetime'].dt.floor(self.bin_freq)
        
        return_col = f"R_{self.horizon}"
        if return_col not in df.columns:
            df[return_col] = np.nan
            
        # Filter valid returns
        df = df.dropna(subset=[return_col])
        if df.empty:
            self.portfolio_series = pd.Series(dtype=float)
            self.event_counts = pd.Series(dtype=int)
            return

        if self.weighting == 'equal_symbol':
            # Average per symbol per bin, then across symbols
            symbol_bin = df.groupby(['bin', 'symbol'])[return_col].mean().reset_index()
            port_returns = symbol_bin.groupby('bin')[return_col].mean()
            counts = df.groupby('bin').size()
        elif self.weighting == 'equal_event':
            # Straight average of all events in the bin
            port_returns = df.groupby('bin')[return_col].mean()
            counts = df.groupby('bin').size()
        else:
            raise ValueError(f"Unknown weighting: {self.weighting}")

        # Create continuous calendar grid
        min_bin = df['bin'].min()
        max_bin = df['bin'].max()
        full_idx = pd.date_range(min_bin, max_bin, freq=self.bin_freq)
        
        self.portfolio_series = port_returns.reindex(full_idx).fillna(0.0)
        self.event_counts = counts.reindex(full_idx).fillna(0)
        self.raw_df = df

    def calendar_newey_west_se(self, max_lags: Optional[int] = None) -> float:
        """
        Newey-West standard error on the uniform calendar portfolio.
        Accounts for chronological overlap properly.
        """
        y = self.portfolio_series.values
        T = len(y)
        if T < 2:
            return np.nan
            
        # Unconditional mean formulation (testing if mean != 0)
        # Using intercept-only OLS: beta = mean(y)
        mu = np.mean(y)
        residuals = y - mu
        
        if max_lags is None:
            max_lags = int(4 * (T / 100) ** (2/9))
            
        Q = np.sum(residuals**2)
        for j in range(1, max_lags + 1):
            weight = 1 - j / (max_lags + 1)
            cov = np.sum(residuals[j:] * residuals[:-j])
            Q += 2 * weight * cov
            
        # Variance of the mean
        var_mu = Q / T
        return float(np.sqrt(max(0, var_mu) / T))

    def get_three_layer_diagnostics(self) -> Dict[str, Any]:
        """
        Generates the three required diagnostic layers: 
        Calendar-time, Symbol-level, and Event-level.
        """
        if self.portfolio_series.empty:
            return {}

        # 1. Calendar-Time Portfolio
        cal_mean = self.portfolio_series.mean()
        cal_se = self.calendar_newey_west_se()
        t_stat = cal_mean / cal_se if cal_se > 0 else 0.0
        
        layer_a = {
            "calendar_expectancy": float(cal_mean),
            "calendar_se": float(cal_se),
            "calendar_t_stat": float(t_stat),
            "total_bins": len(self.portfolio_series),
            "active_bins": int((self.event_counts > 0).sum())
        }

        # 2. Symbol-Level Diagnostics
        df = self.raw_df
        return_col = f"R_{self.horizon}"
        
        sym_stats = df.groupby('symbol')[return_col].agg(['mean', 'count', lambda x: (x > 0).mean()])
        sym_stats.columns = ['mean_return', 'event_count', 'hit_rate']
        
        layer_b = {
            "symbol_count": len(sym_stats),
            "symbols_positive_pct": float((sym_stats['mean_return'] > 0).mean()),
            "cross_sectional_dispersion": float(sym_stats['mean_return'].std()),
            "mean_hit_rate_across_symbols": float(sym_stats['hit_rate'].mean()),
            "symbol_stats": sym_stats.to_dict(orient='index')
        }

        # 3. Event-Level Diagnostics
        total_events = len(df)
        layer_c = {
            "total_event_count": total_events,
            "mean_event_return": float(df[return_col].mean()),
            "event_hit_rate": float((df[return_col] > 0).mean()),
            "return_std": float(df[return_col].std()),
            "return_skew": float(df[return_col].skew()) if total_events > 2 else 0.0,
            "max_favorable": float(df[return_col].max()),
            "max_adverse": float(df[return_col].min())
        }

        return {
            "Layer_A_Calendar": layer_a,
            "Layer_B_Symbol": layer_b,
            "Layer_C_Event": layer_c
        }


def fdr_bh(p_values: np.ndarray) -> np.ndarray:
    """
    Benjamini-Hochberg False Discovery Rate correction.
    """
    p_values = np.asarray(p_values)
    mask = ~np.isnan(p_values)
    valid_p = p_values[mask]
    
    if len(valid_p) == 0:
        return p_values
        
    n = len(valid_p)
    sort_idx = np.argsort(valid_p)
    sorted_p = valid_p[sort_idx]
    
    adj_p = np.zeros_like(sorted_p)
    adj_p[-1] = sorted_p[-1]
    
    for i in range(n - 2, -1, -1):
        adj_p[i] = min(adj_p[i+1], sorted_p[i] * n / (i + 1))
        
    res_p = np.zeros_like(valid_p)
    res_p[sort_idx] = np.minimum(1.0, adj_p)
    
    out = np.full_like(p_values, np.nan, dtype=float)
    out[mask] = res_p
    return out

def calendar_block_bootstrap(ctp: CalendarTimePortfolio, block_size_bins: int = 24, num_bootstraps: int = 1000) -> np.ndarray:
    """
    Stationary block bootstrap resampling on the calendar time grid.
    Preserves cross-sectional correlation and temporal dependence.
    """
    y = ctp.portfolio_series.values
    n = len(y)
    if n == 0:
        return np.array([])
        
    p = 1.0 / max(1.0, float(block_size_bins))
    bootstrapped_means = np.zeros(num_bootstraps)
    
    for i in range(num_bootstraps):
        current_len = 0
        sample_y = np.zeros(n)
        
        while current_len < n:
            start_idx = np.random.randint(0, n)
            length = np.random.geometric(p)
            length = min(length, n - current_len)
            
            indices = (np.arange(start_idx, start_idx + length) % n)
            sample_y[current_len:current_len + length] = y[indices]
            current_len += length
            
        bootstrapped_means[i] = np.mean(sample_y)
        
    return bootstrapped_means
