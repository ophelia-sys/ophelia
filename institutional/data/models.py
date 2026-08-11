from dataclasses import dataclass, field
from typing import Optional, List, Dict
from institutional.types import DataQuality, MicrostructureState

@dataclass
class TradeEvent:
    symbol: str
    trade_id: str
    timestamp: int
    price: float
    quantity: float
    is_buyer_maker: Optional[bool]
    source: str
    sequence: Optional[int] = None
    data_quality: DataQuality = DataQuality.VALID
    
    @property
    def aggressor(self) -> Optional[str]:
        # is_buyer_maker = True means buyer was maker (aggressor was seller)
        # is_buyer_maker = False means buyer was taker (aggressor was buyer)
        if self.is_buyer_maker is None:
            return None
        return "SELL" if self.is_buyer_maker else "BUY"

@dataclass
class OrderBookSnapshot:
    symbol: str
    timestamp: int
    bids: List[List[float]] # [price, quantity]
    asks: List[List[float]]
    source: str
    data_quality: DataQuality = DataQuality.VALID
    
    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0][0] if self.bids and self.data_quality != DataQuality.INVALID else None
        
    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0][0] if self.asks and self.data_quality != DataQuality.INVALID else None
        
    @property
    def mid_price(self) -> Optional[float]:
        from institutional.liquidity import calculate_mid_price
        return calculate_mid_price(self.best_bid, self.best_ask)
        
    @property
    def spread(self) -> Optional[float]:
        from institutional.liquidity import calculate_spread
        return calculate_spread(self.best_bid, self.best_ask)
        
    @property
    def relative_spread(self) -> Optional[float]:
        from institutional.liquidity import calculate_relative_spread
        return calculate_relative_spread(self.best_bid, self.best_ask)
        
    @property
    def queue_imbalance(self) -> Optional[float]:
        if not self.bids or not self.asks or self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_queue_imbalance
        return calculate_queue_imbalance(self.bids[0][1], self.asks[0][1])
        
    @property
    def depth_imbalance(self) -> Optional[float]:
        if self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_depth_imbalance
        return calculate_depth_imbalance(self.bids, self.asks)
        
    @property
    def microprice(self) -> Optional[float]:
        if not self.bids or not self.asks or self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_microprice
        return calculate_microprice(self.best_bid, self.best_ask, self.bids[0][1], self.asks[0][1])
        
    @property
    def book_slope_bid(self) -> Optional[float]:
        if self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_order_book_slope
        return calculate_order_book_slope(self.bids, self.mid_price)

    @property
    def book_slope_ask(self) -> Optional[float]:
        if self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_order_book_slope
        return calculate_order_book_slope(self.asks, self.mid_price)
        
    @property
    def book_concentration(self) -> Optional[float]:
        if self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_book_concentration
        # We can calculate concentration for the whole book by concatenating
        return calculate_book_concentration(self.bids + self.asks)
        
    def calculate_visible_impact(self, quote_notional: float, side: str) -> Optional[float]:
        if self.data_quality == DataQuality.INVALID: return None
        from institutional.liquidity import calculate_visible_impact_bps
        if side == 'BUY':
            return calculate_visible_impact_bps(self.asks, self.best_ask, quote_notional, side)
        elif side == 'SELL':
            return calculate_visible_impact_bps(self.bids, self.best_bid, quote_notional, side)
        return None

@dataclass
class FundingSnapshot:
    symbol: str
    timestamp: int
    funding_rate: float
    mark_price: Optional[float]
    source: str
    data_quality: DataQuality = DataQuality.VALID

@dataclass
class OpenInterestSnapshot:
    symbol: str
    timestamp: int
    open_interest: float
    source: str
    data_quality: DataQuality = DataQuality.VALID

@dataclass
class MarketTicker:
    symbol: str
    timestamp: int
    last_price: float
    volume_24h: float
    source: str
    data_quality: DataQuality = DataQuality.VALID

@dataclass
class OHLCVBar:
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    data_quality: DataQuality = DataQuality.VALID

@dataclass
class MarketDataSnapshot:
    symbol: str
    timestamp: int
    timeframe: str
    
    # Pre-aggregated OHLCV
    ohlcv: Optional[List[OHLCVBar]] = None
    
    # Snapshot data
    order_book: Optional[OrderBookSnapshot] = None
    funding: Optional[FundingSnapshot] = None
    open_interest: Optional[OpenInterestSnapshot] = None
    ticker: Optional[MarketTicker] = None
    
    # Historical Snapshot data
    open_interest_history: List[OpenInterestSnapshot] = field(default_factory=list)
    funding_history: List[FundingSnapshot] = field(default_factory=list)
    
    # Aggregated event metrics for the timeframe
    # Trade aggregations
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    cvd: Optional[float] = None
    tvi: Optional[float] = None
    
    # VWAP metrics
    vwap_raw: Optional[float] = None
    vwap_deviation: Optional[float] = None
    
    # Liquidity aggregations
    microstructure: Optional[MicrostructureState] = None
    
    # Cross asset data
    cross_asset_klines: Dict[str, List[OHLCVBar]] = field(default_factory=dict)
    
    # Data tracking
    data_quality: DataQuality = DataQuality.UNAVAILABLE
    freshness: str = "UNAVAILABLE"
