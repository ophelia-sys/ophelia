import pytest
import time
from institutional.data.models import (
    TradeEvent, OrderBookSnapshot, MarketDataSnapshot, OHLCVBar, MarketTicker
)
from institutional.data.engine import InstitutionalDataEngine
from institutional.types import DataQuality

def test_engine_handles_missing_websocket():
    engine = InstitutionalDataEngine(use_ws=False)
    # The math engine requires a snapshot. We mock REST adapter responses internally or just see if it handles no WS gracefully.
    assert engine.ws_manager is None
    
    # Fake REST adapter responses
    engine.rest_adapter.get_klines = lambda s, i, **kwargs: [OHLCVBar(s, int(time.time()), 100, 100, 100, 100, 10, "REST")]
    engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(s, int(time.time()), [[100, 1]], [[101, 1]], "REST")
    engine.rest_adapter.get_funding_history = lambda s: []
    engine.rest_adapter.get_open_interest = lambda s: None
    engine.rest_adapter.get_ticker = lambda s: MarketTicker(s, int(time.time()), 100, 100, "REST")
    
    snapshot = engine.get_snapshot("BTC-USDT", "1m")
    
    assert snapshot.data_quality == DataQuality.INSUFFICIENT_DATA
    assert snapshot.freshness == "STALE"
    assert snapshot.order_book is not None
    assert snapshot.ohlcv is not None

def test_engine_aggregates_trades():
    engine = InstitutionalDataEngine(use_ws=False)
    now = int(time.time() * 1000)
    engine._trades["BTC-USDT"] = [
        TradeEvent("BTC-USDT", "t1", now - 200, 100.0, 1.0, is_buyer_maker=False, source="WS"), # Buyer is aggressor
        TradeEvent("BTC-USDT", "t2", now - 100, 100.0, 2.0, is_buyer_maker=True, source="WS"),  # Seller is aggressor
        TradeEvent("BTC-USDT", "t3", now, 100.0, 0.5, is_buyer_maker=False, source="WS")  # Buyer is aggressor
    ]
    
    engine.rest_adapter.get_klines = lambda s, i, **kwargs: [OHLCVBar(s, int(time.time()), 100, 100, 100, 100, 10, "REST")]
    engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(s, int(time.time()), [[100, 1]], [[101, 1]], "REST")
    engine.rest_adapter.get_funding_history = lambda s: []
    engine.rest_adapter.get_open_interest = lambda s: None
    engine.rest_adapter.get_ticker = lambda s: MarketTicker(s, int(time.time()), 100, 100, "REST")
    
    snapshot = engine.get_snapshot("BTC-USDT", "1m")
    
    assert snapshot.buy_volume == 1.5
    assert snapshot.sell_volume == 2.0
    assert snapshot.cvd == -0.5
    
def test_engine_handles_degraded_state():
    engine = InstitutionalDataEngine(use_ws=False)
    
    # REST fails
    engine.rest_adapter.get_klines = lambda s, i, **kwargs: []
    engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(s, int(time.time()), [], [], "REST", DataQuality.UNAVAILABLE)
    engine.rest_adapter.get_funding_history = lambda s: []
    engine.rest_adapter.get_open_interest = lambda s: None
    engine.rest_adapter.get_ticker = lambda s: MarketTicker(s, int(time.time()), 100, 100, "REST")
    
    snapshot = engine.get_snapshot("BTC-USDT", "1m")
    
    # Should seamlessly downgrade to INSUFFICIENT_DATA or DEGRADED state
    assert snapshot.data_quality == DataQuality.INSUFFICIENT_DATA
    assert snapshot.freshness == "STALE"

def test_no_future_data_leakage():
    engine = InstitutionalDataEngine(use_ws=False)
    engine.rest_adapter.get_klines = lambda s, i, **kwargs: [OHLCVBar(s, int(time.time()), 100, 100, 100, 100, 10, "REST")]
    engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(s, int(time.time()), [[100, 1]], [[101, 1]], "REST")
    engine.rest_adapter.get_funding_history = lambda s: []
    engine.rest_adapter.get_open_interest = lambda s: None
    engine.rest_adapter.get_ticker = lambda s: MarketTicker(s, int(time.time()), 100, 100, "REST")
    snapshot = engine.get_snapshot("BTC-USDT", "1m")
    
    # We should ensure the snapshot timestamp is strictly <= current time
    assert snapshot.timestamp <= int(time.time() * 1000)
