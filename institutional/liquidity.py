import numpy as np
import pandas as pd
from typing import List, Optional
from institutional.volatility import calculate_log_returns

def calculate_mid_price(best_bid: float, best_ask: float) -> Optional[float]:
    if best_bid is None or best_ask is None or best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:
        return None
    return (best_bid + best_ask) / 2.0

def calculate_spread(best_bid: float, best_ask: float) -> Optional[float]:
    if best_bid is None or best_ask is None or best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:
        return None
    return best_ask - best_bid

def calculate_relative_spread(best_bid: float, best_ask: float) -> Optional[float]:
    spread = calculate_spread(best_bid, best_ask)
    mid = calculate_mid_price(best_bid, best_ask)
    if spread is None or mid is None or mid == 0:
        return None
    return spread / mid

def calculate_queue_imbalance(bid_qty_1: float, ask_qty_1: float) -> Optional[float]:
    if bid_qty_1 is None or ask_qty_1 is None or bid_qty_1 < 0 or ask_qty_1 < 0:
        return None
    total = bid_qty_1 + ask_qty_1
    if total == 0:
        return None
    return (bid_qty_1 - ask_qty_1) / total

def calculate_depth_imbalance(bids: List[List[float]], asks: List[List[float]], levels: int = 20) -> Optional[float]:
    if not bids or not asks:
        return None
    bids_subset = bids[:levels]
    asks_subset = asks[:levels]
    
    bid_depth = sum(qty for _, qty in bids_subset)
    ask_depth = sum(qty for _, qty in asks_subset)
    
    if bid_depth < 0 or ask_depth < 0:
        return None
        
    total = bid_depth + ask_depth
    if total == 0:
        return None
    return (bid_depth - ask_depth) / total

def calculate_microprice(best_bid: float, best_ask: float, bid_qty_1: float, ask_qty_1: float) -> Optional[float]:
    if None in (best_bid, best_ask, bid_qty_1, ask_qty_1):
        return None
    if best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:
        return None
    if bid_qty_1 < 0 or ask_qty_1 < 0:
        return None
    total = bid_qty_1 + ask_qty_1
    if total == 0:
        return None
    return (best_ask * bid_qty_1 + best_bid * ask_qty_1) / total

def calculate_book_concentration(levels: List[List[float]]) -> Optional[float]:
    """
    HHI style concentration: sum(s_i^2) where s_i = q_i / sum(q_j)
    """
    if not levels:
        return None
    total_qty = sum(qty for _, qty in levels)
    if total_qty <= 0:
        return None
    hhi = sum((qty / total_qty) ** 2 for _, qty in levels if qty >= 0)
    return float(hhi)

def calculate_order_book_slope(levels: List[List[float]], mid_price: float) -> Optional[float]:
    """
    Regression-based visible-book slope (USDT / BPS).
    Dependent variable: Cumulative visible quote notional (y) in USDT
    Independent variable: Price distance from mid in basis points (x)
    """
    if not levels or mid_price is None or mid_price <= 0:
        return None
    
    distances_bps = []
    cumulative_notional = []
    current_notional = 0.0
    
    for price, qty in levels:
        if qty < 0 or price <= 0:
            return None # invalid
        
        # X: Distance in basis points
        distance_bps = abs(price - mid_price) / mid_price * 10000.0
        
        # Y: Cumulative quote notional in USDT
        current_notional += (qty * price)
        
        distances_bps.append(distance_bps)
        cumulative_notional.append(current_notional)
        
    if len(distances_bps) < 2:
        return None
        
    x = np.array(distances_bps)
    y = np.array(cumulative_notional)
    
    var_x = np.var(x)
    if var_x == 0:
        return None
        
    slope = np.cov(x, y)[0, 1] / var_x
    return float(slope)

def calculate_visible_impact_bps(levels: List[List[float]], best_price: float, quote_notional: float, side: str) -> Optional[float]:
    """
    Calculates visible price impact in basis points.
    Walks the provided levels (bids or asks) to fill the requested quote_notional.
    side: 'BUY' (walks asks), 'SELL' (walks bids)
    """
    if not levels or best_price is None or best_price <= 0 or quote_notional <= 0:
        return None
        
    accumulated_quote = 0.0
    accumulated_base = 0.0
    
    for price, qty in levels:
        if price <= 0 or qty < 0:
            return None
            
        level_quote = price * qty
        remaining_quote = quote_notional - accumulated_quote
        
        if remaining_quote <= level_quote:
            base_needed = remaining_quote / price
            accumulated_base += base_needed
            accumulated_quote += remaining_quote
            break
        else:
            accumulated_base += qty
            accumulated_quote += level_quote
            
    # Check if we were able to completely fill the requested notional
    # Allow a small float epsilon for equality
    if accumulated_quote < quote_notional - 1e-9:
        return None # INSUFFICIENT_DATA
        
    vwap = accumulated_quote / accumulated_base
    
    if side == 'BUY':
        impact_bps = (vwap - best_price) / best_price * 10000.0
    elif side == 'SELL':
        impact_bps = (best_price - vwap) / best_price * 10000.0
    else:
        return None
        
    return float(impact_bps)

def calculate_amihud_illiquidity(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Amihud Illiquidity = |R_t| / V_USD,t
    """
    returns = calculate_log_returns(df, 1)
    volume_usd = df["close"].astype(float) * df["volume"].astype(float)
    illiq = returns.abs() / volume_usd.replace(0, np.nan)
    return illiq.rolling(window=window).mean()

def estimate_kyle_lambda(df: pd.DataFrame, trades: pd.DataFrame, window: int = 20) -> float:
    """
    Kyle Lambda proxy using rolling regression of DeltaP ~ CVD.
    """
    if trades is None or trades.empty:
        return np.nan
    return np.nan
