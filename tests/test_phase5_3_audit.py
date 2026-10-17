import numpy as np
import pandas as pd
import pytest

from research.pipeline.labels import _compute_barrier_numba, LabelGenerator, OUTCOME_TIMEOUT, OUTCOME_TARGET, OUTCOME_STOP, OUTCOME_AMBIGUOUS
from research.pipeline.features import FeatureGenerator

# ---------------------------------------------------------
# 1. BARRIER LABEL OFF-BY-ONE & AMBIGUITY AUDIT
# ---------------------------------------------------------
def test_barrier_logic_and_ambiguity():
    # Setup hand-calculated array
    # Entry at index 0 (price = 100)
    # TP = +20 bps = 100.20
    # SL = -15 bps = 99.85
    # Max horizon = 3
    
    closes = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
    highs  = np.array([100.0, 100.1, 100.3, 100.0, 100.0])
    lows   = np.array([100.0,  99.9,  99.9,  99.0, 100.0])
    
    target_pct = 20 / 10000.0
    stop_pct = 15 / 10000.0
    
    # 0: target on first future candle (no, high=100.1 < 100.20)
    # 1: target on second future candle (yes, high=100.3 >= 100.20)
    
    outcomes, exit_idxs = _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, max_horizon=3, is_long=True)
    
    # For index 0:
    # j=1 (idx=1): H=100.1, L=99.9. Neither hit.
    # j=2 (idx=2): H=100.3, L=99.9. Target hit!
    assert outcomes[0] == OUTCOME_TARGET
    assert exit_idxs[0] == 2
    
    # Test Ambiguous (hit both in same bar)
    highs[1] = 100.3
    lows[1] = 99.8
    outcomes, exit_idxs = _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, max_horizon=3, is_long=True)
    assert outcomes[0] == OUTCOME_AMBIGUOUS
    assert exit_idxs[0] == 1
    
    # Test Stop
    highs[1] = 100.1
    lows[1] = 99.8
    outcomes, exit_idxs = _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, max_horizon=3, is_long=True)
    assert outcomes[0] == OUTCOME_STOP
    assert exit_idxs[0] == 1
    
    # Test Timeout
    highs[1] = 100.0; lows[1] = 100.0
    highs[2] = 100.0; lows[2] = 100.0
    highs[3] = 100.0; lows[3] = 100.0
    outcomes, exit_idxs = _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, max_horizon=3, is_long=True)
    assert outcomes[0] == OUTCOME_TIMEOUT
    assert exit_idxs[0] == 3
    
    # Test final available candle truncation (horizon=10 but array is size 5)
    outcomes, exit_idxs = _compute_barrier_numba(highs, lows, closes, target_pct, stop_pct, max_horizon=10, is_long=True)
    assert outcomes[0] == OUTCOME_TIMEOUT
    assert exit_idxs[0] == 4 # Max available idx


# ---------------------------------------------------------
# 2. COST SEMANTICS & INDEPENDENT EV CALCULATOR
# ---------------------------------------------------------
def independent_ev_calculator(trades_df, tp_bps, sl_bps, cost_bps, policy='CONSERVATIVE_EXCLUSION'):
    """
    Independent reference EV calculator that does NOT use the exp_014 function.
    """
    tp_frac = tp_bps / 10000.0
    sl_frac = sl_bps / 10000.0
    cost_frac = cost_bps / 10000.0
    
    net_rets = []
    
    for _, row in trades_df.iterrows():
        outcome = row['b_outcome']
        
        if outcome == OUTCOME_AMBIGUOUS:
            if policy == 'CONSERVATIVE_EXCLUSION':
                continue
            elif policy == 'WORST_CASE':
                outcome = OUTCOME_STOP
                
        # Gross return is theoretically exact for target/stop
        if outcome == OUTCOME_TARGET:
            gross = tp_frac
        elif outcome == OUTCOME_STOP:
            gross = -sl_frac
        elif outcome == OUTCOME_TIMEOUT:
            # Reconstruct exact return
            entry_price = row['close']
            exit_price = row['exit_price']
            gross = (exit_price / entry_price) - 1.0
            
        net = gross - cost_frac
        net_rets.append(net)
        
    if len(net_rets) == 0:
        return 0.0, 0.0, 0.0
    
    net_rets = np.array(net_rets)
    return net_rets.mean() * 10000.0, (net_rets.mean() + cost_frac) * 10000.0, (net_rets > 0).mean()

def test_ev_calculator():
    # Construct a synthetic dataframe
    df = pd.DataFrame({
        'b_outcome': [OUTCOME_TARGET, OUTCOME_STOP, OUTCOME_TIMEOUT, OUTCOME_AMBIGUOUS],
        'close': [100.0, 100.0, 100.0, 100.0],
        'exit_price': [0.0, 0.0, 100.1, 0.0] # 100.1 means +10 bps
    })
    
    # 1. CONSERVATIVE (Target, Stop, Timeout)
    # Gross rets: +20 bps, -15 bps, +10 bps
    # Avg Gross: (20 - 15 + 10) / 3 = 15 / 3 = 5.0 bps
    # Cost = 12 bps => Net = 5.0 - 12 = -7.0 bps
    net_ev, gross_ev, p_win = independent_ev_calculator(df, tp_bps=20, sl_bps=15, cost_bps=12, policy='CONSERVATIVE_EXCLUSION')
    assert np.isclose(gross_ev, 5.0)
    assert np.isclose(net_ev, -7.0)
    # wins: 20-12=8 (win), -15-12=-27 (loss), 10-12=-2 (loss) -> 1 win out of 3 = 0.3333
    assert np.isclose(p_win, 1/3)

    # What if cost = 20 bps?
    # wins: 20-20=0 (not > 0), -15-20=-35 (loss), 10-20=-10 (loss) -> 0 wins out of 3 = 0.0
    net_ev, gross_ev, p_win = independent_ev_calculator(df, tp_bps=20, sl_bps=15, cost_bps=20, policy='CONSERVATIVE_EXCLUSION')
    assert p_win == 0.0 # This explains the plummeted P(Net>0) at 20 bps cost!

# ---------------------------------------------------------
# 3. MICROSTRUCTURE CAUSALITY AUDIT
# ---------------------------------------------------------
def test_microstructure_causality():
    # If we alter T+1 data, does it affect the rolling statistics at T?
    df = pd.DataFrame({
        'close': [100.0]*100,
        'high': [100.0]*100,
        'low': [100.0]*100,
        'volume': [10.0]*100,
        'delta_v': [1.0]*100,
        'taker_buy_volume': [5.5]*100
    })
    
    # Generate features
    df1 = FeatureGenerator.generate_features(df.copy(), families=['microstructure'])
    
    # Modify future
    df_altered = df.copy()
    df_altered.loc[66:, 'delta_v'] = 1000.0
    
    df2 = FeatureGenerator.generate_features(df_altered, families=['microstructure'])
    
    # Value at index 65 must be completely identical in both
    # Also verify it's not nan
    assert not np.isnan(df1.loc[65, 'ofi_proxy_z'])
    assert df1.loc[65, 'ofi_proxy_z'] == df2.loc[65, 'ofi_proxy_z']
    
    # Is rolling mean lookahead free? pandas rolling(60).mean() uses current row and 59 previous rows.
    # Therefore it only uses data up to T. Causality holds.
