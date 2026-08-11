import pytest
import time
from institutional.data.engine import InstitutionalDataEngine
from institutional.data.models import TradeEvent, OHLCVBar, OrderBookSnapshot, MarketTicker
from institutional.types import DataQuality

def setup_engine():
    engine = InstitutionalDataEngine(use_ws=False)
    engine.rest_adapter.get_klines = lambda s, i, **kwargs: [OHLCVBar(s, int(time.time()), 100, 100, 100, 100, 10, "REST")]
    engine.rest_adapter.get_order_book = lambda s: OrderBookSnapshot(s, int(time.time()), [[100, 1]], [[101, 1]], "REST")
    engine.rest_adapter.get_funding_history = lambda s: []
    engine.rest_adapter.get_open_interest = lambda s: None
    engine.rest_adapter.get_ticker = lambda s: MarketTicker(s, int(time.time()), 100, 100, "REST")
    engine.start(["BTC-USDT"])
    return engine

def make_trade(trade_id: str, quantity: float, is_buyer_maker: bool, offset_ms: int = 0) -> TradeEvent:
    return TradeEvent(
        symbol="BTC-USDT",
        trade_id=trade_id,
        timestamp=int(time.time() * 1000) + offset_ms,
        price=60000.0,
        quantity=quantity,
        is_buyer_maker=is_buyer_maker,
        source="TEST"
    )

def test_1_single_buy():
    engine = setup_engine()
    # is_buyer_maker = False => seller is maker, buyer is aggressor => BUY
    engine._on_trade(make_trade("t1", 10.0, False))
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 10.0
    assert snap.sell_volume == 0.0
    assert snap.cvd == 10.0
    assert snap.tvi == 1.0

def test_2_single_sell():
    engine = setup_engine()
    # is_buyer_maker = True => buyer is maker, seller is aggressor => SELL
    engine._on_trade(make_trade("t1", 5.0, True))
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 0.0
    assert snap.sell_volume == 5.0
    assert snap.cvd == -5.0
    assert snap.tvi == -1.0

def test_3_equal_buy_and_sell():
    engine = setup_engine()
    engine._on_trade(make_trade("t1", 10.0, False)) # BUY 10
    engine._on_trade(make_trade("t2", 10.0, True))  # SELL 10
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.cvd == 0.0
    assert snap.tvi == 0.0

def test_4_duplicate_delivery():
    engine = setup_engine()
    trade = make_trade("dup1", 5.0, False)
    engine._on_trade(trade)
    engine._on_trade(trade) # Delivered twice
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 5.0 # Counted exactly once
    assert len(engine._trades["BTC-USDT"]) == 1

def test_5_repeated_snapshot():
    engine = setup_engine()
    engine._on_trade(make_trade("t1", 8.0, False))
    
    snap1 = engine.get_snapshot("BTC-USDT", "1m")
    snap2 = engine.get_snapshot("BTC-USDT", "1m")
    
    assert snap1.cvd == 8.0
    assert snap2.cvd == 8.0 # State not consumed

def test_6_ten_snapshots():
    engine = setup_engine()
    engine._on_trade(make_trade("t1", 7.0, True))
    
    for _ in range(10):
        snap = engine.get_snapshot("BTC-USDT", "1m")
        assert snap.cvd == -7.0

def test_7_trades_outside_1m():
    engine = setup_engine()
    # -61 seconds
    engine._on_trade(make_trade("old1", 10.0, False, -61000))
    engine._on_trade(make_trade("new1", 5.0, False, 0))
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 5.0 # Old excluded

def test_8_trades_outside_5m():
    engine = setup_engine()
    # -301 seconds
    engine._on_trade(make_trade("old1", 10.0, False, -301000))
    engine._on_trade(make_trade("new1", 5.0, False, -10000)) # -10 seconds
    
    snap = engine.get_snapshot("BTC-USDT", "5m")
    assert snap.buy_volume == 5.0

def test_9_zero_denominator():
    engine = setup_engine()
    # Zero volume trades
    engine._on_trade(make_trade("t1", 0.0, False))
    engine._on_trade(make_trade("t2", 0.0, True))
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.tvi is None

def test_10_missing_aggressor():
    engine = setup_engine()
    trade = make_trade("t1", 10.0, False)
    trade.is_buyer_maker = None # Unknown aggressor
    engine._on_trade(trade)
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    # Missing aggressor -> DEGRADED
    assert snap.data_quality == DataQuality.DEGRADED
    assert snap.cvd == 0.0 # Didn't add to CVD

def test_11_reconnect_replay():
    engine = setup_engine()
    engine._on_trade(make_trade("t1", 5.0, False))
    
    # Simulate reconnect giving t1 again plus t2
    engine._on_trade(make_trade("t1", 5.0, False))
    engine._on_trade(make_trade("t2", 3.0, False))
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 8.0 # 5 + 3, no double counting of t1

def test_12_out_of_order():
    engine = setup_engine()
    engine._on_trade(make_trade("t_new", 10.0, False, offset_ms=0))
    engine._on_trade(make_trade("t_old", 5.0, False, offset_ms=-5000))
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 15.0 # Both included correctly because both are in window

def test_13_no_trades():
    engine = setup_engine()
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.cvd is None # Explicitly UNAVAILABLE
    assert snap.tvi is None
    assert snap.data_quality == DataQuality.INSUFFICIENT_DATA

def test_14_future_dated():
    engine = setup_engine()
    engine._on_trade(make_trade("future1", 10.0, False, offset_ms=10000)) # 10s in future
    
    snap = engine.get_snapshot("BTC-USDT", "1m")
    assert snap.buy_volume == 0.0 # Future trade excluded from historical aggregate
    assert snap.cvd is None
