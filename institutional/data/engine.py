import time
import threading
from typing import Dict, List, Optional
from collections import deque

from institutional.types import DataQuality, MicrostructureState
from institutional.data.models import (
    TradeEvent, OrderBookSnapshot, FundingSnapshot,
    OpenInterestSnapshot, MarketTicker, OHLCVBar, MarketDataSnapshot
)
from institutional.data.rest_adapter import InstitutionalRESTAdapter
from institutional.data.websocket_manager import InstitutionalWebSocketManager
from utils.logger import logger

class InstitutionalDataEngine:
    """
    Consolidates data from REST and WebSocket layers into normalized MarketDataSnapshots.
    Isolates data acquisition completely from TradingEngine logic.
    """
    
    def __init__(self, use_ws: bool = True):
        self.rest_adapter = InstitutionalRESTAdapter()
        self.ws_manager = InstitutionalWebSocketManager() if use_ws else None
        
        # State caches
        self._lock = threading.RLock()
        self._order_books: Dict[str, OrderBookSnapshot] = {}
        self._trades: Dict[str, deque] = {} # keep last 10000 trades
        self._processed_trade_ids: Dict[str, set] = {}
        self._recent_trade_ids: Dict[str, deque] = {}
        self._tickers: Dict[str, MarketTicker] = {}
        self._funding_history: Dict[str, List[FundingSnapshot]] = {}
        self._open_interest_history: Dict[str, deque] = {}
        self._funding_last_update: Dict[str, float] = {}
        self._open_interest_last_update: Dict[str, float] = {}
        
        self.watchlist = []
        
        if self.ws_manager:
            self.ws_manager.on_trade_callback = self._on_trade
            self.ws_manager.on_depth_callback = self._on_depth
            self.ws_manager.on_ticker_callback = self._on_ticker

    def start(self, watchlist: List[str]):
        self.watchlist = watchlist
        for sym in watchlist:
            self._trades[sym] = deque(maxlen=10000)
            self._processed_trade_ids[sym] = set()
            self._recent_trade_ids[sym] = deque(maxlen=10000)
            self._open_interest_history[sym] = deque(maxlen=1000)
            self._funding_history[sym] = []
            self._funding_last_update[sym] = 0.0
            self._open_interest_last_update[sym] = 0.0
            
        if self.ws_manager:
            self.ws_manager.start(watchlist)

    def stop(self):
        if self.ws_manager:
            self.ws_manager.stop()

    def _on_trade(self, event: TradeEvent):
        with self._lock:
            if event.symbol in self._trades:
                if event.trade_id and event.trade_id in self._processed_trade_ids[event.symbol]:
                    return  # reject exact duplicate
                    
                if event.trade_id:
                    self._processed_trade_ids[event.symbol].add(event.trade_id)
                    self._recent_trade_ids[event.symbol].append(event.trade_id)
                
                self._trades[event.symbol].append(event)
                
                if len(self._recent_trade_ids[event.symbol]) >= 10000:
                    old_id = self._recent_trade_ids[event.symbol].popleft()
                    self._processed_trade_ids[event.symbol].discard(old_id)
                
    def _on_depth(self, snapshot: OrderBookSnapshot):
        with self._lock:
            self._order_books[snapshot.symbol] = snapshot
            
    def _on_ticker(self, ticker: MarketTicker):
        with self._lock:
            self._tickers[ticker.symbol] = ticker
            
    def get_snapshot(self, symbol: str, timeframe: str) -> MarketDataSnapshot:
        """
        Builds the consolidated MarketDataSnapshot for the Math Engine.
        """
        ohlcv = self.rest_adapter.get_klines(symbol, timeframe, limit=500)
        
        with self._lock:
            ob = self._order_books.get(symbol)
            if not ob or (time.time() * 1000 - ob.timestamp) > 30000:
                ob = self.rest_adapter.get_order_book(symbol)
                if ob and ob.data_quality == DataQuality.VALID:
                    self._order_books[symbol] = ob
            
            ticker = self._tickers.get(symbol)
            if not ticker or (time.time() * 1000 - ticker.timestamp) > 30000:
                ticker = self.rest_adapter.get_ticker(symbol)
                if ticker and ticker.data_quality == DataQuality.VALID:
                    self._tickers[symbol] = ticker

            # Note: For non-watchlist symbols, we create buffers on the fly if needed
            if symbol not in self._open_interest_history:
                self._open_interest_history[symbol] = deque(maxlen=1000)
            if symbol not in self._funding_last_update:
                self._funding_last_update[symbol] = 0.0
            if symbol not in self._open_interest_last_update:
                self._open_interest_last_update[symbol] = 0.0
                
            last_funding_ts = self._funding_last_update.get(symbol, 0.0)
            if (time.time() * 1000 - last_funding_ts) > 60000 or symbol not in self._funding_history:
                funding_list = self.rest_adapter.get_funding_history(symbol)
                if funding_list:
                    self._funding_history[symbol] = funding_list
                    self._funding_last_update[symbol] = time.time() * 1000

            last_oi_ts = self._open_interest_last_update.get(symbol, 0.0)
            if (time.time() * 1000 - last_oi_ts) > 60000:
                oi = self.rest_adapter.get_open_interest(symbol)
                if oi and oi.data_quality == DataQuality.VALID:
                    # Deduplicate by timestamp
                    if not self._open_interest_history[symbol] or self._open_interest_history[symbol][-1].timestamp < oi.timestamp:
                        self._open_interest_history[symbol].append(oi)
                    self._open_interest_last_update[symbol] = time.time() * 1000

            oi_history_list = list(self._open_interest_history[symbol])
            funding_history_list = self._funding_history.get(symbol, [])
            
            # For backward compatibility / snapshot structure, we might expose the latest single element
            latest_oi = oi_history_list[-1] if oi_history_list else None
            latest_funding = funding_history_list[-1] if funding_history_list else None

            trades = list(self._trades.get(symbol, []))
            
        window_ms = 60000 # default 1m
        if timeframe == "5m":
            window_ms = 300000
        elif timeframe == "15m":
            window_ms = 900000
            
        now = int(time.time() * 1000)
        window_start = now - window_ms
        
        buy_vol = 0.0
        sell_vol = 0.0
        cvd = 0.0
        trades_in_window = 0
        missing_aggressor = False
        
        for t in trades:
            if window_start <= t.timestamp <= now:
                if t.aggressor == "BUY":
                    buy_vol += t.quantity
                    cvd += t.quantity
                    trades_in_window += 1
                elif t.aggressor == "SELL":
                    sell_vol += t.quantity
                    cvd -= t.quantity
                    trades_in_window += 1
                else:
                    missing_aggressor = True
                    trades_in_window += 1

        tvi = None
        if (buy_vol + sell_vol) > 0:
            tvi = (buy_vol - sell_vol) / (buy_vol + sell_vol)

        micro_state = None
        if ob:
            micro_state = MicrostructureState(
                mid_price=ob.mid_price,
                spread=ob.spread,
                relative_spread=ob.relative_spread,
                queue_imbalance=ob.queue_imbalance,
                depth_imbalance=ob.depth_imbalance,
                microprice=ob.microprice,
                book_slope_bid=ob.book_slope_bid,
                book_slope_ask=ob.book_slope_ask,
                book_concentration=ob.book_concentration,
                visible_impact_buy=ob.calculate_visible_impact(100000, 'BUY'), # default 100k
                visible_impact_sell=ob.calculate_visible_impact(100000, 'SELL'),
                data_quality=ob.data_quality
            )
            
        cross_assets = {}
        for ca in self.watchlist:
            if ca != symbol:
                cross_assets[ca] = self.rest_adapter.get_klines(ca, timeframe, limit=50)

        quality = DataQuality.VALID
        if not ohlcv or not ob or ob.data_quality in [DataQuality.UNAVAILABLE, DataQuality.INVALID]:
            quality = DataQuality.DEGRADED
            
        if trades_in_window == 0:
            quality = DataQuality.INSUFFICIENT_DATA
            cvd = None # Explicitly mark unavailable, don't use fake 0
            tvi = None
        elif missing_aggressor:
            quality = DataQuality.DEGRADED
            
        return MarketDataSnapshot(
            symbol=symbol,
            timestamp=int(time.time() * 1000),
            timeframe=timeframe,
            ohlcv=ohlcv,
            order_book=ob,
            funding=latest_funding,
            open_interest=latest_oi,
            open_interest_history=oi_history_list,
            funding_history=funding_history_list,
            ticker=ticker,
            buy_volume=buy_vol if trades else None,
            sell_volume=sell_vol if trades else None,
            cvd=cvd if trades else None,
            tvi=tvi,
            microstructure=micro_state,
            cross_asset_klines=cross_assets,
            data_quality=quality,
            freshness="FRESH" if quality == DataQuality.VALID else "STALE"
        )
