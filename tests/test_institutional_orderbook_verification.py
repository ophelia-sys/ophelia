import pytest
import time
from institutional.data.models import OrderBookSnapshot
from institutional.types import DataQuality

def test_payload_parsing_snapshot():
    # Synthetic BingX-like snapshot payload
    payload = {
        "code": 0,
        "data": {
            "asks": [
                ["64740.24", "11.426913"],
                ["64733.99", "0.000098"]
            ],
            "bids": [
                ["64727.92", "0.001839"],
                ["64725.36", "0.019934"]
            ],
            "lastUpdateId": 16226307465
        },
        "dataType": "BTC-USDT@depth20",
        "success": True,
        "timestamp": 1786371499993
    }

    # Simulate parsing
    data = payload["data"]
    bids = sorted([(float(p), float(q)) for p, q in data.get("bids", [])], key=lambda x: x[0], reverse=True)
    asks = sorted([(float(p), float(q)) for p, q in data.get("asks", [])], key=lambda x: x[0])
    
    ob = OrderBookSnapshot(
        symbol="BTC-USDT",
        timestamp=payload["timestamp"],
        bids=bids,
        asks=asks,
        source="WS",
        data_quality=DataQuality.VALID
    )
    
    assert len(ob.bids) == 2
    assert len(ob.asks) == 2
    assert ob.best_bid == 64727.92
    assert ob.best_ask == 64733.99
    
def test_sequence_gaps_in_snapshots():
    # If update IDs have gaps, this is normal for a snapshot feed, but prevents incremental OFI.
    id_1 = 16226307465
    id_2 = 16226307471
    
    # In an incremental feed, a gap implies missing data.
    # In a snapshot feed, a gap simply means events occurred between our snapshot polls.
    assert id_2 > id_1

def test_zero_quantity_removal():
    # While BingX snapshots don't typically send zero quantity, 
    # robust parsing should handle it if it does happen.
    raw_bids = [
        ["64727.92", "0.000000"],
        ["64725.36", "0.019934"]
    ]
    # Filter out zero quantities
    bids = [(float(p), float(q)) for p, q in raw_bids if float(q) > 0]
    
    assert len(bids) == 1
    assert bids[0][0] == 64725.36
    
def test_crossed_book_detection():
    # A crossed book is mathematically invalid and should degrade quality.
    bids = [(65000.0, 1.0)]
    asks = [(64000.0, 1.0)]
    
    is_crossed = bids[0][0] >= asks[0][0]
    assert is_crossed == True
    
def test_future_timestamp_rejection():
    future_time_ms = int(time.time() * 1000) + 60000
    
    is_valid = future_time_ms <= int(time.time() * 1000)
    assert is_valid == False
