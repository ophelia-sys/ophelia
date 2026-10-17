import numpy as np
import pandas as pd
from numba import njit

# Outcome encodings
OUTCOME_TIMEOUT = 0
OUTCOME_TARGET = 1
OUTCOME_STOP = 2
OUTCOME_AMBIGUOUS = 3

@njit
def _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, max_horizon, is_long=True):
    n = len(closes)
    outcomes = np.full(n, OUTCOME_TIMEOUT, dtype=np.int8)
    exit_idx = np.zeros(n, dtype=np.int32)
    # We also track realized log return at exit
    # and MAE/MFE up to exit
    # but for simplicity in numba, we'll return outcomes and exit_idx
    
    for i in range(n):
        entry_price = closes[i]
        
        reached_outcome = OUTCOME_TIMEOUT
        reached_idx = min(i + max_horizon, n - 1)
        
        # Iterate over future bars
        for j in range(1, max_horizon + 1):
            curr_idx = i + j
            if curr_idx >= n:
                reached_idx = n - 1
                break
                
            h = highs[curr_idx]
            l = lows[curr_idx]
            
            if is_long:
                hit_target = (h / entry_price - 1.0) >= target_pct
                hit_stop = (l / entry_price - 1.0) <= -stop_pct
                
                if hit_target and hit_stop:
                    reached_outcome = OUTCOME_AMBIGUOUS
                    reached_idx = curr_idx
                    break
                elif hit_target:
                    reached_outcome = OUTCOME_TARGET
                    reached_idx = curr_idx
                    break
                elif hit_stop:
                    reached_outcome = OUTCOME_STOP
                    reached_idx = curr_idx
                    break
            else:
                hit_target = (l / entry_price - 1.0) <= -target_pct
                hit_stop = (h / entry_price - 1.0) >= stop_pct
                
                if hit_target and hit_stop:
                    reached_outcome = OUTCOME_AMBIGUOUS
                    reached_idx = curr_idx
                    break
                elif hit_target:
                    reached_outcome = OUTCOME_TARGET
                    reached_idx = curr_idx
                    break
                elif hit_stop:
                    reached_outcome = OUTCOME_STOP
                    reached_idx = curr_idx
                    break
                    
        outcomes[i] = reached_outcome
        exit_idx[i] = reached_idx
        
    return outcomes, exit_idx

class LabelGenerator:
    """
    Generates structured targets for the ML models.
    """
    @staticmethod
    def generate_labels(df: pd.DataFrame, horizons: list = [60], thresholds_bps: list = [10, 15, 20]) -> pd.DataFrame:
        """
        Calculates forward targets.
        target_X: Directional target (1 if forward return > 0 else 0)
        target_X_up_Y: 1 if forward return > Y bps
        target_X_dn_Y: 1 if forward return < -Y bps
        R_X: Raw continuous log return over the same horizon
        """
        df = df.copy()
        
        for h in horizons:
            df[f'R_{h}'] = np.log(df['close'].shift(-h) / df['close'])
            df[f'target_{h}'] = (df[f'R_{h}'] > 0).astype(float)
            
            for thresh in thresholds_bps:
                thresh_frac = thresh / 10000.0
                df[f'target_{h}_up_{thresh}'] = (df[f'R_{h}'] > thresh_frac).astype(float)
                df[f'target_{h}_dn_{thresh}'] = (df[f'R_{h}'] < -thresh_frac).astype(float)
            
        return df

    @staticmethod
    def generate_barrier_labels(df: pd.DataFrame, target_bps: float, stop_bps: float, timeout_candles: int, is_long: bool = True, prefix="barrier") -> pd.DataFrame:
        """
        Calculates triple-barrier outcomes.
        Returns the dataframe with added columns:
        {prefix}_outcome: 0=TIMEOUT, 1=TARGET, 2=STOP, 3=AMBIGUOUS
        {prefix}_exit_idx: The integer row index where the outcome was hit
        {prefix}_exit_price: The exit price assuming exact fill at target/stop or close at timeout
        """
        df = df.copy()
        
        target_pct = target_bps / 10000.0
        stop_pct = stop_bps / 10000.0
        
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        outcomes, exit_idxs = _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, timeout_candles, is_long=is_long)
        
        df[f'{prefix}_outcome'] = outcomes
        
        # In a real environment, we would save entry_idx and exit_idx directly, but we map to absolute indices.
        df[f'{prefix}_exit_offset'] = exit_idxs - np.arange(len(df))
        
        return df
