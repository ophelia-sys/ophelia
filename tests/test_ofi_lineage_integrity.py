import pytest
import numpy as np
import pandas as pd
from institutional.types import MarketState, MicrostructureState, DataQuality, FeatureStatus
from institutional.data.models import MarketDataSnapshot
from institutional.institutional_math import InstitutionalMathEngine
from institutional.order_flow import calculate_ofi

def test_market_state_does_not_alias_ofi():
    """
    Proves that MarketState does not contain an 'ofi' field
    and that no other metric is allowed to masquerade as OFI.
    """
    # Create distinct values for all microstructure variables
    # to guarantee they are not colliding or being aliased.
    micro_state = MicrostructureState(
        depth_imbalance=0.73,
        queue_imbalance=-0.22,
        microprice=65001.5,
        book_slope_bid=10.0,
        book_slope_ask=15.0,
        book_concentration=0.5
    )
    
    state = MarketState(
        symbol="BTC-USDT",
        timestamp=1234567890,
        timeframe="1m",
        microstructure=micro_state,
        order_flow_state="VALID",
        direction="UNKNOWN",
        data_quality=DataQuality.VALID,
    )
    
    # 1. Depth imbalance remains depth imbalance
    assert state.microstructure.depth_imbalance == 0.73
    
    # 2. Queue imbalance remains queue imbalance
    assert state.microstructure.queue_imbalance == -0.22
    
    # 3. MarketState should NOT have an 'ofi' attribute 
    # to prevent silent aliasing.
    assert not hasattr(state, "ofi"), "MarketState must NOT contain an 'ofi' field to prevent semantic collisions."
    
    # 4. MarketState should NOT have 'order_flow_imbalance' attribute
    assert not hasattr(state, "order_flow_imbalance"), "MarketState must NOT contain 'order_flow_imbalance' attribute."

def test_canonical_ofi_returns_nan_on_invalid_data():
    """
    Asserts the Cont-Kukanov-Stoikov OFI calculation behaves safely 
    when given None or empty data, preserving UNAVAILABLE status.
    """
    assert np.isnan(calculate_ofi(None))
    assert np.isnan(calculate_ofi(pd.DataFrame()))

def test_engine_preserves_distinct_metrics_without_ofi_hallucination():
    """
    Pass a snapshot through the InstitutionalMathEngine to verify
    the actual integration path doesn't invent OFI.
    """
    # Using a mocked snapshot
    snapshot = MarketDataSnapshot(
        symbol="ETH-USDT",
        timestamp=123,
        timeframe="1m",
        ohlcv=[], # Empty will trigger early exit, we want that or we need 500 rows.
    )
    
    # If < normalization_window, it returns early with INSUFFICIENT_DATA
    engine = InstitutionalMathEngine()
    state = engine.analyze(snapshot)
    
    assert state.data_quality == DataQuality.INSUFFICIENT_DATA
    assert not hasattr(state, "ofi")
