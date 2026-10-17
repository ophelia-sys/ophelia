import numpy as np
import pandas as pd
from research.pipeline.economic import EconomicEngine

def test_mae_mfe_calculation():
    # Mock data
    df = pd.DataFrame({
        'close': [100, 102, 105, 95, 110],
        'high': [100, 103, 106, 98, 111],
        'low': [100, 101, 104, 94, 105]
    })
    
    # Long trade from idx 0 to 4
    # Entry at 100
    # High is 111 (MFE = 11%)
    # Low is 94 (MAE = -6%)
    mae, mfe = EconomicEngine.calculate_mae_mfe(df, 0, 4, is_long=True)
    assert np.isclose(mfe, 0.11)
    assert np.isclose(mae, -0.06)
    
    # Short trade from idx 0 to 4
    # MFE is when price goes down. Lowest is 94, return = 1 - 94/100 = 0.06
    # MAE is when price goes up. Highest is 111, return = 1 - 111/100 = -0.11
    mae, mfe = EconomicEngine.calculate_mae_mfe(df, 0, 4, is_long=False)
    assert np.isclose(mfe, 0.06)
    assert np.isclose(mae, -0.11)

def test_cost_curve_and_breakeven():
    gross_returns = [0.0010, 0.0020, -0.0005, 0.0015] # 10 bps, 20 bps, -5 bps, 15 bps
    costs = [6, 12]
    
    curve, be = EconomicEngine.calculate_cost_curve(gross_returns, costs)
    
    # Mean gross return is 40 bps / 4 = 10 bps
    assert np.isclose(be, 10.0)
    
    # At 6 bps cost, net returns: 4, 14, -11, 9
    np.testing.assert_allclose(curve[6], [0.0004, 0.0014, -0.0011, 0.0009])
    
    # At 12 bps cost, net returns: -2, 8, -17, 3
    np.testing.assert_allclose(curve[12], [-0.0002, 0.0008, -0.0017, 0.0003])

def test_pullback_entry():
    df = pd.DataFrame({
        'open': [100, 101, 99, 102],
        'high': [100, 102, 100, 103],
        'low': [100, 100.5, 98, 101],
        'close': [100, 101, 99, 102]
    })
    # Signal at idx 0, close=100. Want a 1% pullback (limit=99).
    # wait 3 candles.
    # idx 1: low is 100.5 (no fill)
    # idx 2: low is 98 (fills!). open is 99, so conservative fill is 99.
    idx, price, missed = EconomicEngine.simulate_pullback_entry(df, 0, 99.0, max_wait=3, is_long=True)
    assert idx == 2
    assert price == 99.0
    assert not missed

    # If limit is 98.5
    # idx 2 low is 98, open is 99. Opened above limit, but low went below. 
    # Conservative fill says limit_price (since open > limit, it must have traded through limit)
    idx, price, missed = EconomicEngine.simulate_pullback_entry(df, 0, 98.5, max_wait=3, is_long=True)
    assert price == 98.5
    
    # Missed opportunity
    idx, price, missed = EconomicEngine.simulate_pullback_entry(df, 0, 97.0, max_wait=3, is_long=True)
    assert missed

def test_barrier_logic():
    df = pd.DataFrame({
        'high': [100, 101, 105, 102],
        'low':  [100,  99,  98, 101],
        'close':[100, 100, 104, 102]
    })
    
    # Long, target 4%, stop 1.5%
    # idx 1: high 101 (+1%), low 99 (-1%). Neither.
    # idx 2: high 105 (+5%), low 98 (-2%). Both hit! Ambiguous.
    res, idx = EconomicEngine.evaluate_barriers(df, 0, 0.04, 0.015, is_long=True, max_horizon=3)
    assert res == 'AMBIGUOUS'
    
    # Target 4%, stop 2.5%
    # idx 2: high 105 (+5%), low 98 (-2%). Low didn't hit stop. Target hit!
    res, idx = EconomicEngine.evaluate_barriers(df, 0, 0.04, 0.025, is_long=True, max_horizon=3)
    assert res == 'TARGET'

    # Target 6%, stop 1.5%
    # idx 2: high 105 (+5%), low 98 (-2%). High didn't hit target, low hit stop.
    res, idx = EconomicEngine.evaluate_barriers(df, 0, 0.06, 0.015, is_long=True, max_horizon=3)
    assert res == 'STOP'
    
    # Expired
    res, idx = EconomicEngine.evaluate_barriers(df, 0, 0.06, 0.025, is_long=True, max_horizon=3)
    assert res == 'EXPIRED'
    assert idx == 3
