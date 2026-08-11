import pytest
import time
import numpy as np
from institutional.data.models import OrderBookSnapshot, DataQuality
from institutional.liquidity import (
    calculate_mid_price,
    calculate_spread,
    calculate_relative_spread,
    calculate_queue_imbalance,
    calculate_depth_imbalance,
    calculate_microprice,
    calculate_book_concentration,
    calculate_order_book_slope,
    calculate_visible_impact_bps
)
from institutional.data.websocket_manager import InstitutionalWebSocketManager

def test_valid_bbo_extraction():
    bids = [[100.0, 1.0], [99.0, 2.0]]
    asks = [[101.0, 1.0], [102.0, 2.0]]
    ob = OrderBookSnapshot("BTC-USDT", int(time.time()*1000), bids, asks, "WS")
    assert ob.best_bid == 100.0
    assert ob.best_ask == 101.0
    assert ob.mid_price == 100.5
    assert ob.spread == 1.0
    assert ob.relative_spread == 1.0 / 100.5

def test_invalid_crossed_book():
    # Bid >= Ask
    bids = [[101.0, 1.0]]
    asks = [[100.0, 1.0]]
    ob = OrderBookSnapshot("BTC-USDT", int(time.time()*1000), bids, asks, "WS", data_quality=DataQuality.INVALID)
    
    assert ob.best_bid is None
    assert ob.best_ask is None
    assert ob.mid_price is None
    assert ob.spread is None
    assert ob.queue_imbalance is None

def test_zero_quantity_handling():
    assert calculate_queue_imbalance(0.0, 0.0) is None
    assert calculate_depth_imbalance([[100.0, 0.0]], [[101.0, 0.0]]) is None
    assert calculate_microprice(100.0, 101.0, 0.0, 0.0) is None

def test_queue_imbalance():
    # bid_qty = 10, ask_qty = 5
    # (10 - 5) / 15 = 5 / 15 = 0.3333
    ob = OrderBookSnapshot("BTC", 0, [[100.0, 10.0]], [[101.0, 5.0]], "WS")
    assert pytest.approx(ob.queue_imbalance) == 0.3333333333

def test_depth_imbalance():
    bids = [[100, 10], [99, 10]] # 20
    asks = [[101, 5], [102, 5]] # 10
    # (20 - 10) / 30 = 10 / 30 = 0.3333
    ob = OrderBookSnapshot("BTC", 0, bids, asks, "WS")
    assert pytest.approx(ob.depth_imbalance) == 0.3333333333

def test_microprice():
    # bid=100(10), ask=101(5)
    # (101*10 + 100*5) / 15 = (1010 + 500) / 15 = 1510 / 15 = 100.6666
    ob = OrderBookSnapshot("BTC", 0, [[100.0, 10.0]], [[101.0, 5.0]], "WS")
    assert pytest.approx(ob.microprice) == 100.6666666667

def test_descending_bingx_ask_input():
    # BingX sends asks descending. websocket_manager should sort them ascending.
    ws = InstitutionalWebSocketManager()
    
    payload = {
        "dataType": "BTC-USDT@depth20",
        "data": {
            "T": int(time.time()*1000),
            "bids": [["100.0", "1.0"], ["99.0", "1.0"]],
            "asks": [["102.0", "1.0"], ["101.0", "1.0"]] # descending!
        }
    }
    
    captured = []
    ws.on_depth_callback = lambda ob: captured.append(ob)
    ws._parse_depth(payload)
    
    assert len(captured) == 1
    ob = captured[0]
    # Bids should be highest to lowest
    assert ob.bids[0][0] == 100.0
    assert ob.bids[1][0] == 99.0
    
    # Asks should be lowest to highest
    assert ob.asks[0][0] == 101.0
    assert ob.asks[1][0] == 102.0
    assert ob.best_ask == 101.0

def test_insufficient_levels_slope():
    # Need at least 2 levels for slope
    bids = [[100.0, 1.0]]
    asks = [[101.0, 1.0]]
    ob = OrderBookSnapshot("BTC", 0, bids, asks, "WS")
    assert ob.book_slope_bid is None
    assert ob.book_slope_ask is None

def test_bps_quote_notional_slope_calculation():
    # Mid = 100
    # Bids: [99.9, 1.0], [99.8, 2.0]
    # distance 99.9 -> 100 is 0.1 / 100 * 10000 = 10 bps
    # distance 99.8 -> 100 is 0.2 / 100 * 10000 = 20 bps
    #
    # Quote Notional Y1 = 99.9 * 1.0 = 99.9
    # Quote Notional Y2 = 99.9 + (99.8 * 2.0) = 99.9 + 199.6 = 299.5
    #
    # x = [10, 20]
    # y = [99.9, 299.5]
    # var(x) = 25
    # cov(x,y) = 998
    # slope = 998 / 25 = 39.92 (USDT / BPS)
    bids = [[99.9, 1.0], [99.8, 2.0]]
    asks = [[100.1, 1.0], [100.2, 2.0]]
    ob = OrderBookSnapshot("BTC", 0, bids, asks, "WS")
    
    # Assert values
    assert pytest.approx(ob.book_slope_bid, 0.01) == 39.92
    assert pytest.approx(ob.book_slope_ask, 0.01) == 39.92

def test_stale_snapshot_future_timestamp():
    ws = InstitutionalWebSocketManager()
    
    # 10 minutes in the future
    future_ms = int(time.time()*1000) + 600000
    payload = {
        "dataType": "BTC-USDT@depth20",
        "data": {
            "T": future_ms,
            "bids": [["100.0", "1.0"]],
            "asks": [["101.0", "1.0"]]
        }
    }
    
    captured = []
    ws.on_depth_callback = lambda ob: captured.append(ob)
    ws._parse_depth(payload)
    
    ob = captured[0]
    assert ob.data_quality == DataQuality.INVALID

def test_nan_infinity_rejection():
    ws = InstitutionalWebSocketManager()
    
    payload = {
        "dataType": "BTC-USDT@depth20",
        "data": {
            "T": int(time.time()*1000),
            "bids": [["100.0", "NaN"], ["99.0", "1.0"]],
            "asks": [["101.0", "1.0"]]
        }
    }
    
    captured = []
    ws.on_depth_callback = lambda ob: captured.append(ob)
    ws._parse_depth(payload)
    
    ob = captured[0]
    # The NaN level should be filtered out
    assert len(ob.bids) == 1
    assert ob.best_bid == 99.0

def test_visible_buy_side_impact():
    # Asks: 101 (10), 102 (10), 103 (10)
    asks = [[101.0, 10.0], [102.0, 10.0], [103.0, 10.0]]
    
    # We want to buy 1500 USDT notional.
    # Level 1: 101 * 10 = 1010 USDT. (accumulated quote: 1010, base: 10)
    # Remaining: 490 USDT.
    # Level 2: consumes 490 USDT at 102 price. Base = 490 / 102 = 4.8039
    # Total quote = 1500. Total base = 14.8039
    # VWAP = 1500 / 14.8039 = 101.3245
    # Impact BPS = (101.3245 - 101.0) / 101.0 * 10000 = 32.1287
    
    impact = calculate_visible_impact_bps(asks, 101.0, 1500.0, "BUY")
    assert pytest.approx(impact, 0.01) == 32.12

def test_visible_sell_side_impact():
    # Bids: 100 (10), 99 (10)
    bids = [[100.0, 10.0], [99.0, 10.0]]
    
    # Sell 1500 USDT notional
    # L1: 1000 USDT. base = 10.
    # Rem: 500 USDT.
    # L2: 500 USDT at 99. base = 500 / 99 = 5.0505
    # Total base = 15.0505
    # VWAP = 1500 / 15.0505 = 99.6644
    # Impact BPS = (100.0 - 99.6644) / 100.0 * 10000 = 33.56
    
    impact = calculate_visible_impact_bps(bids, 100.0, 1500.0, "SELL")
    assert pytest.approx(impact, 0.01) == 33.557

def test_insufficient_visible_liquidity():
    asks = [[101.0, 10.0]] # 1010 total notional
    impact = calculate_visible_impact_bps(asks, 101.0, 2000.0, "BUY")
    assert impact is None

def test_book_concentration():
    # 2 levels, 5 qty each. total = 10. s1 = 0.5, s2 = 0.5. HHI = 0.25 + 0.25 = 0.5
    levels = [[100.0, 5.0], [99.0, 5.0]]
    conc = calculate_book_concentration(levels)
    assert pytest.approx(conc) == 0.5
    
    # 1 level. s1 = 1.0. HHI = 1.0
    levels = [[100.0, 5.0]]
    conc = calculate_book_concentration(levels)
    assert pytest.approx(conc) == 1.0
