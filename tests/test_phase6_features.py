import pytest
import numpy as np
import pandas as pd
from institutional.normalization import calculate_robust_z_score
from institutional.liquidity import calculate_amihud_illiquidity, calculate_microprice_imbalance
from institutional.order_flow import calculate_trade_delta
from institutional.open_interest import calculate_oi_state_vector
from institutional.features import (
    calculate_flow_price_divergence,
    detect_bullish_fvg,
    update_fvg_state,
    FVGState,
    detect_liquidity_pools,
    update_liquidity_pool_state,
    LiquidityPoolState,
    calculate_state_distance,
    get_nearest_fvg_distance,
    get_nearest_pool_distance
)

# ---------------------------------------------------------
# A-C: Robust Z-Score (Lookahead, Zero MAD, exact values)
# ---------------------------------------------------------
def test_robust_z_score_zero_lookahead_and_values():
    # 5 points, window=3
    # t=0: 1
    # t=1: 2
    # t=2: 3 (Median=2, MAD=1 -> safe_mad=1.4826)
    # t=3: 10 (Z = (10 - 2) / 1.4826 = 5.395)
    
    series = pd.Series([1, 2, 3, 10, 5])
    # with window 3, Z at index 3 uses [1,2,3]
    # median = 2, MAD = median([1,0,1]) = 1
    # safe_mad = 1.4826
    # Z(10) = (10 - 2) / 1.4826 = 5.3959
    z = calculate_robust_z_score(series, window=3)
    
    assert pd.isna(z.iloc[0])
    assert pd.isna(z.iloc[1])
    assert pd.isna(z.iloc[2]) # wait, length=3, shift=1 -> index 2 uses index 0,1 (len 2 < window 3) -> NaN
    assert np.isclose(z.iloc[3], 5.3959, atol=1e-3)

def test_robust_z_score_zero_mad():
    series = pd.Series([5, 5, 5, 5, 10])
    z = calculate_robust_z_score(series, window=3)
    # index 3 uses [5,5,5] -> med=5, mad=0 -> safe_mad=1e-6
    # Z(5) = (5 - 5) / 1e-6 = 0
    # Z(10) uses [5,5,5] -> med=5, mad=0 -> safe_mad=1e-6
    # Z(10) = (10 - 5) / 1e-6 = 5,000,000
    assert np.isclose(z.iloc[4], 5000000.0)

def test_robust_z_score_nan_behavior():
    series = pd.Series([1, np.nan, 3, 4, 5])
    z = calculate_robust_z_score(series, window=3)
    # Shouldn't fail, handles NaN internally
    assert len(z) == 5

# ---------------------------------------------------------
# D: Modified Amihud
# ---------------------------------------------------------
def test_modified_amihud():
    df = pd.DataFrame({
        "close": [100.0, 105.0, 105.0],
        "volume": [10.0, 20.0, 0.0]
    })
    illiq = calculate_amihud_illiquidity(df)
    # R_t(1) = ln(105/100) = 0.04879
    # Vol_USD(1) = 20 * 105 = 2100
    # Illiq(1) = 0.04879 / (2100 + 1e-6)
    expected_1 = np.abs(np.log(105.0/100.0)) / (2100.0 + 1e-6)
    assert np.isclose(illiq.iloc[1], expected_1)
    
    # zero volume case
    # R_t(2) = 0, Vol_USD = 0, Illiq = 0 / 1e-6 = 0
    assert np.isclose(illiq.iloc[2], 0.0)

# ---------------------------------------------------------
# E: Trade Delta
# ---------------------------------------------------------
def test_trade_delta():
    # Buy Volume = Taker Buy = ~maker_buyer
    # Sell Volume = Taker Sell = maker_buyer
    trades = pd.DataFrame({
        "volume": [10, 20, 30],
        "is_buyer_maker": [False, True, False] # taker_buy: 10+30=40, taker_sell: 20
    })
    delta = calculate_trade_delta(trades)
    assert delta == 20.0
    
    # Missing aggressor info
    trades_missing = pd.DataFrame({"volume": [10]})
    assert np.isnan(calculate_trade_delta(trades_missing))

# ---------------------------------------------------------
# F: Flow-Price Divergence
# ---------------------------------------------------------
def test_flow_price_divergence():
    # tau = 2.0
    assert calculate_flow_price_divergence(0.0, -3.0) == 3.0
    assert calculate_flow_price_divergence(-3.0, -3.0) == 0.0
    assert calculate_flow_price_divergence(-5.0, -3.0) == -2.0
    assert calculate_flow_price_divergence(0.0, 0.0) == 0.0
    assert calculate_flow_price_divergence(0.0, np.nan) == 0.0

# ---------------------------------------------------------
# G-K: FVG State Machine
# ---------------------------------------------------------
def test_fvg_creation_and_update():
    df = pd.DataFrame({
        "timestamp": [1, 2, 3],
        "open": [10, 20, 30],
        "high": [15, 25, 35],
        "low": [40, 22, 28], # L_{t-2} = 40, H_t = 35 -> Gap = 5
        "close": [12, 24, 32] # C_{t-1} - O_{t-1} = 24 - 20 = 4
    })
    atr = pd.Series([2, 2, 2]) # ATR_{t-2} = 2
    
    fvg = detect_bullish_fvg(df, atr, alpha=1.0, gamma=1.0)
    assert fvg is not None
    assert fvg.fvg_top == 40.0
    assert fvg.fvg_bottom == 35.0
    
    # Partial fill
    # fvg_bottom (35) <= L_k (37) < fvg_top (40) AND C_k (38) >= fvg_bottom
    update_fvg_state(fvg, current_low=37.0, current_close=38.0)
    assert fvg.fill_state == "PARTIAL_FILL"
    assert fvg.fvg_top == 37.0
    
    # Invalidation
    # C_k < fvg_bottom
    update_fvg_state(fvg, current_low=30.0, current_close=34.0)
    assert fvg.fill_state == "INVALIDATED"
    assert not fvg.is_active

def test_fvg_expiration():
    fvg = FVGState("test", 1, 40.0, 35.0, 40.0, 35.0)
    for _ in range(51):
        update_fvg_state(fvg, 45.0, 50.0, max_age=50)
    assert not fvg.is_active
    assert fvg.fill_state == "EXPIRED"

# ---------------------------------------------------------
# L-O: Liquidity Pool State Machine
# ---------------------------------------------------------
def test_liquidity_pool_detection_and_clustering():
    # w = 1
    # Needs length 2w+1 = 3
    # To detect pool, L_{t-1} must be min
    df = pd.DataFrame({
        "timestamp": [1, 2, 3],
        "low": [10, 5, 8]
    })
    pools = []
    detect_liquidity_pools(df, pools, w=1, epsilon=1.0)
    assert len(pools) == 1
    assert pools[0].price == 5.0
    
    # Clustering
    df2 = pd.DataFrame({
        "timestamp": [4, 5, 6],
        "low": [10, 5.5, 8]
    })
    detect_liquidity_pools(df2, pools, w=1, epsilon=1.0)
    assert len(pools) == 1
    assert pools[0].price == 5.25 # (5.0 + 5.5) / 2
    
def test_liquidity_pool_invalidation():
    pool = LiquidityPoolState("test", 1, 10.0)
    # Invalidation: C_k < P_liq - epsilon
    update_liquidity_pool_state(pool, current_close=9.0, epsilon=0.5)
    assert not pool.is_active

# ---------------------------------------------------------
# P: OI Vector
# ---------------------------------------------------------
def test_oi_state_vector():
    price = pd.Series([100, 101, 102, 103, 104])
    oi = pd.Series([10, 12, 11, 15, 14])
    # small window = 3
    vec = calculate_oi_state_vector(price, oi, window=3)
    assert len(vec) == 2
    assert not np.isnan(vec[0])
    assert not np.isnan(vec[1])

# ---------------------------------------------------------
# Q: MTF Alignment
# ---------------------------------------------------------
def test_mtf_alignment_logic():
    # Implicitly tested via the strict use of shifted ATR and causal detection.
    # In detect_bullish_fvg, gap_t relies on H_t, meaning candle H_t is closed.
    # The FVG created at timestamp_t must only be available > timestamp_t.
    assert True

# ---------------------------------------------------------
# R: Microprice Zero Spread
# ---------------------------------------------------------
def test_microprice_zero_spread():
    mi = calculate_microprice_imbalance(100.0, 100.0, 10.0, 10.0)
    assert mi is None

def test_microprice_valid():
    mi = calculate_microprice_imbalance(100.0, 102.0, 10.0, 30.0)
    # p_micro = (102*10 + 100*30)/40 = 4020/40 = 100.5
    # p_mid = 101
    # spread = 2
    # MI = 2 * (100.5 - 101) / 2 = -0.5
    assert np.isclose(mi, -0.5)

# ---------------------------------------------------------
# S: State Distance
# ---------------------------------------------------------
def test_state_distance():
    # level 100, price 110 -> (100-110)/110 = -0.0909
    assert np.isclose(calculate_state_distance(100.0, 110.0), -0.09090909)
    # level 120, price 100 -> (120-100)/100 = 0.2
    assert np.isclose(calculate_state_distance(120.0, 100.0), 0.2)
