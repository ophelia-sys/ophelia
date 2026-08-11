import pytest
import time
import numpy as np

from institutional.data.models import MarketDataSnapshot, OrderBookSnapshot
from institutional.types import DataQuality, MicrostructureState
from institutional.institutional_math import InstitutionalMathEngine

def test_ofi_is_not_aliased_to_depth_imbalance():
    """
    Proves that Canonical OFI remains UNAVAILABLE and is NOT
    hallucinated from depth imbalance.
    """
    engine = InstitutionalMathEngine(normalization_window=100)
    
    # Create a snapshot with an extreme depth imbalance
    micro_state = MicrostructureState(
        depth_imbalance=0.99, # Highly skewed
        data_quality=DataQuality.VALID
    )
    
    snapshot = MarketDataSnapshot(
        symbol="BTC-USDT",
        timestamp=int(time.time()*1000),
        timeframe="1m",
        microstructure=micro_state,
        data_quality=DataQuality.VALID
    )
    
    # Even without OHLCV (which will cause INSUFFICIENT_DATA), we can
    # test the math engine's output behavior on the fields.
    # To bypass the window check, we add dummy OHLCV
    from institutional.data.models import OHLCVBar
    bars = [
        OHLCVBar("BTC-USDT", i, 100, 101, 99, 100, 10, "TEST")
        for i in range(150)
    ]
    snapshot.ohlcv = bars
    
    state = engine.analyze(snapshot)
    
    # The depth imbalance should be passed through
    assert state.microstructure is not None
    assert state.microstructure.depth_imbalance == 0.99
    
    # But OFI should be explicitly UNAVAILABLE
    assert state.order_flow_state == "UNAVAILABLE"
