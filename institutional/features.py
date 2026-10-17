import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from dataclasses import dataclass

# =============================================================================
# 1. STANDARDIZED FLOW-PRICE DIVERGENCE
# =============================================================================

def calculate_flow_price_divergence(
    z_r: float, 
    z_delta_v: float, 
    tau: float = 2.0
) -> float:
    """
    Standardized Flow-Price Divergence
    Evaluates the bullish divergence condition when Z_DeltaV < -tau
    Returns Z_R - Z_DeltaV if condition met, else 0.0
    """
    if np.isnan(z_r) or np.isnan(z_delta_v):
        return 0.0
        
    if z_delta_v < -tau:
        return float(z_r - z_delta_v)
    return 0.0

# =============================================================================
# 2. FVG STATE MACHINE
# =============================================================================

@dataclass
class FVGState:
    fvg_id: str
    created_timestamp: int
    fvg_top: float
    fvg_bottom: float
    original_top: float
    original_bottom: float
    age: int = 0
    is_active: bool = True
    fill_state: str = "ACTIVE"  # ACTIVE, PARTIAL_FILL, INVALIDATED, EXPIRED

def detect_bullish_fvg(
    df: pd.DataFrame, 
    atr_series: pd.Series, 
    alpha: float = 1.0, 
    gamma: float = 1.0
) -> Optional[FVGState]:
    """
    Detects a bullish Fair Value Gap (FVG).
    Requires a DataFrame with 'high', 'low', 'open', 'close' columns.
    ATR must be passed properly shifted (atr_series represents ATR_{t-2}).
    Gap_t = L_{t-2} - H_t
    Condition 1: Gap_t > alpha * ATR_{t-2}
    Condition 2: (C_{t-1} - O_{t-1}) / ATR_{t-2} > gamma
    """
    if len(df) < 3 or len(atr_series) < 3:
        return None
        
    high_t = float(df.iloc[-1]['high'])
    low_t_2 = float(df.iloc[-3]['low'])
    
    close_t_1 = float(df.iloc[-2]['close'])
    open_t_1 = float(df.iloc[-2]['open'])
    
    # Strictly aligned ATR from two periods ago
    atr_t_2 = float(atr_series.iloc[-3])
    
    if pd.isna(atr_t_2) or atr_t_2 <= 0:
        return None
        
    gap_t = low_t_2 - high_t
    
    cond_1 = gap_t > (alpha * atr_t_2)
    cond_2 = (close_t_1 - open_t_1) / atr_t_2 > gamma
    
    if cond_1 and cond_2:
        return FVGState(
            fvg_id=f"fvg_bull_{df.iloc[-1]['timestamp']}",
            created_timestamp=int(df.iloc[-1]['timestamp']),
            fvg_top=low_t_2,
            fvg_bottom=high_t,
            original_top=low_t_2,
            original_bottom=high_t
        )
    return None

def update_fvg_state(fvg: FVGState, current_low: float, current_close: float, max_age: int = 50) -> None:
    """
    Updates FVG state for the current candle.
    """
    if not fvg.is_active:
        return
        
    fvg.age += 1
    
    # Invalidation: C_k < fvg_bottom
    if current_close < fvg.fvg_bottom:
        fvg.is_active = False
        fvg.fill_state = "INVALIDATED"
        return
        
    # Expiration
    if fvg.age > max_age:
        fvg.is_active = False
        fvg.fill_state = "EXPIRED"
        return
        
    # Partial Fill: fvg_bottom <= L_k < fvg_top AND C_k >= fvg_bottom
    if fvg.fvg_bottom <= current_low < fvg.fvg_top and current_close >= fvg.fvg_bottom:
        fvg.fvg_top = current_low
        fvg.fill_state = "PARTIAL_FILL"
        
        # Guard against inversion
        if fvg.fvg_top < fvg.fvg_bottom:
            fvg.fvg_top = fvg.fvg_bottom
            fvg.is_active = False
            fvg.fill_state = "INVALIDATED"

# =============================================================================
# 3. LIQUIDITY POOL STATE MACHINE
# =============================================================================

@dataclass
class LiquidityPoolState:
    pool_id: str
    created_timestamp: int
    price: float
    age: int = 0
    is_active: bool = True

def detect_liquidity_pools(
    df: pd.DataFrame, 
    active_pools: List[LiquidityPoolState], 
    w: int = 5, 
    epsilon: float = 0.5
) -> None:
    """
    Detects swing low candidates for liquidity pools.
    P_liq = L_{t-w} when L_{t-w} = min(L_{t-2w}, ..., L_t)
    Right-side confirmation means it's causal.
    """
    if len(df) < 2 * w + 1:
        return
        
    # Segment from t-2w to t
    segment = df.iloc[-(2 * w + 1):]
    
    # Center element is at index w in the segment
    low_t_w = float(segment.iloc[w]['low'])
    min_low = float(segment['low'].min())
    
    if low_t_w == min_low:
        new_pool_price = low_t_w
        timestamp_t_w = int(segment.iloc[w]['timestamp'])
        
        # Clustering
        merged = False
        for pool in active_pools:
            if pool.is_active and abs(pool.price - new_pool_price) <= epsilon:
                pool.price = (pool.price + new_pool_price) / 2.0
                pool.age = 0
                merged = True
                break
                
        if not merged:
            active_pools.append(
                LiquidityPoolState(
                    pool_id=f"liq_pool_{timestamp_t_w}",
                    created_timestamp=timestamp_t_w,
                    price=new_pool_price
                )
            )

def update_liquidity_pool_state(pool: LiquidityPoolState, current_close: float, epsilon: float, max_age: int = 100) -> None:
    """
    Updates liquidity pool state.
    """
    if not pool.is_active:
        return
        
    pool.age += 1
    
    # Invalidation: C_k < P_liq - epsilon
    if current_close < (pool.price - epsilon):
        pool.is_active = False
        return
        
    # Expiration
    if pool.age > max_age:
        pool.is_active = False
        return

# =============================================================================
# 4. STATE-DISTANCE FEATURES
# =============================================================================

def calculate_state_distance(level: float, current_price: float) -> float:
    """
    Calculates signed normalized distance.
    Negative = level below current price
    Positive = level above current price
    Magnitude = relative distance
    """
    if current_price <= 0:
        return np.nan
    return (level - current_price) / current_price

def get_nearest_fvg_distance(active_fvgs: List[FVGState], current_price: float) -> float:
    if not active_fvgs:
        return np.nan
    
    # Find FVG whose top is closest to current price
    closest_dist = float('inf')
    best_dist = np.nan
    
    for fvg in active_fvgs:
        if not fvg.is_active: continue
        # Distance to the closest boundary (typically top for bullish)
        dist = calculate_state_distance(fvg.fvg_top, current_price)
        if abs(dist) < closest_dist:
            closest_dist = abs(dist)
            best_dist = dist
            
    return best_dist

def get_nearest_pool_distance(active_pools: List[LiquidityPoolState], current_price: float) -> float:
    if not active_pools:
        return np.nan
        
    closest_dist = float('inf')
    best_dist = np.nan
    
    for pool in active_pools:
        if not pool.is_active: continue
        dist = calculate_state_distance(pool.price, current_price)
        if abs(dist) < closest_dist:
            closest_dist = abs(dist)
            best_dist = dist
            
    return best_dist
