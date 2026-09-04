import numpy as np
import pandas as pd

def calculate_cvd(trades: pd.DataFrame) -> float:
    """
    Cumulative Volume Delta (CVD) based on trade-by-trade data.
    CVD_t = sum(V_n * S_n)
    trades DataFrame requires columns: ['volume', 'is_buyer_maker']
    """
    if trades is None or trades.empty or 'is_buyer_maker' not in trades.columns:
        return np.nan
        
    # is_buyer_maker=True means the maker was the buyer, so the taker (aggressor) was the seller (S_n = -1)
    # is_buyer_maker=False means the taker was the buyer (S_n = 1)
    signs = np.where(trades['is_buyer_maker'], -1, 1)
    cvd = np.sum(trades['volume'].astype(float) * signs)
    return float(cvd)

def calculate_trade_delta(trades: pd.DataFrame) -> float:
    """
    Trade Delta (DeltaV_t = BuyVolume_t - SellVolume_t)
    Requires aggressor-labeled trades. If unavailable, returns NaN.
    """
    if trades is None or trades.empty or 'is_buyer_maker' not in trades.columns:
        return np.nan
        
    volume = trades['volume'].astype(float)
    buyer_maker = trades['is_buyer_maker'].astype(bool)
    
    taker_sell = volume[buyer_maker].sum()
    taker_buy = volume[~buyer_maker].sum()
    
    return float(taker_buy - taker_sell)

def calculate_taker_volume_imbalance(trades: pd.DataFrame) -> float:
    """
    Taker Volume Imbalance
    VI_t = (V_taker_buy - V_taker_sell) / V_total
    """
    if trades is None or trades.empty or 'is_buyer_maker' not in trades.columns:
        return np.nan
        
    volume = trades['volume'].astype(float)
    buyer_maker = trades['is_buyer_maker'].astype(bool)
    
    taker_sell = volume[buyer_maker].sum()
    taker_buy = volume[~buyer_maker].sum()
    
    total = taker_sell + taker_buy
    if total == 0:
        return 0.0
        
    return float((taker_buy - taker_sell) / total)

def calculate_ofi(l1_book_updates: pd.DataFrame) -> float:
    """
    Order Flow Imbalance (Cont-Kukanov-Stoikov).
    Requires a strictly sequential, non-gapped sequence of L1 book updates with columns:
    ['bid_price', 'bid_qty', 'ask_price', 'ask_qty']
    
    WARNING: Phase 4.3 proved that BingX public WebSockets emit gapped snapshots.
    This function MUST NOT be fed BingX snapshot data as it will result in mathematically 
    invalid OFI calculations. Canonical OFI is strictly UNAVAILABLE for BingX.
    """
    if l1_book_updates is None or l1_book_updates.empty or len(l1_book_updates) < 2:
        return np.nan
        
    df = l1_book_updates.copy()
    
    # Bid contributions
    df['prev_bid_price'] = df['bid_price'].shift(1)
    df['prev_bid_qty'] = df['bid_qty'].shift(1)
    
    # Default condition: price == prev_price -> qty_change
    bid_cont = df['bid_qty'] - df['prev_bid_qty']
    # Price > prev_price -> full current qty
    bid_cont = np.where(df['bid_price'] > df['prev_bid_price'], df['bid_qty'], bid_cont)
    # Price < prev_price -> full negative prev qty
    bid_cont = np.where(df['bid_price'] < df['prev_bid_price'], -df['prev_bid_qty'], bid_cont)
    
    # Ask contributions
    df['prev_ask_price'] = df['ask_price'].shift(1)
    df['prev_ask_qty'] = df['ask_qty'].shift(1)
    
    ask_cont = df['ask_qty'] - df['prev_ask_qty']
    ask_cont = np.where(df['ask_price'] < df['prev_ask_price'], df['ask_qty'], ask_cont)
    ask_cont = np.where(df['ask_price'] > df['prev_ask_price'], -df['prev_ask_qty'], ask_cont)
    
    e_n = bid_cont - ask_cont
    return float(np.nansum(e_n))
