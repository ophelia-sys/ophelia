import os
import sys
import time
import logging
from pprint import pprint

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exchange.bingx_client import BingXClient
from institutional.data.rest_adapter import InstitutionalRESTAdapter
from institutional.data.engine import InstitutionalDataEngine
from institutional.institutional_math import InstitutionalMathEngine
from institutional.types import DataQuality

logging.basicConfig(level=logging.INFO)

def main():
    print("==================================================")
    print("REAL BINGX DATA LINEAGE VERIFICATION")
    print("==================================================")
    
    # Initialize the real client and engines
    # Requires API keys to be set in env or config, but public endpoints usually don't
    client = BingXClient()
    # InstitutionalDataEngine doesn't take rest_adapter in init, it instantiates its own or takes use_ws.
    # Actually wait, let's just pass use_ws=True
    data_engine = InstitutionalDataEngine(use_ws=True)
    math_engine = InstitutionalMathEngine()
    
    symbol = "BTC-USDT"
    
    print(f"Starting WS for {symbol} and waiting for trades...")
    data_engine.start([symbol])
    
    # Wait for up to 10 seconds for trades to arrive
    for _ in range(10):
        trades = list(data_engine._trades.get(symbol, []))
        if len(trades) > 0:
            print(f"Received {len(trades)} trades via WS.")
            break
        time.sleep(1)
        
    print(f"Fetching real snapshot for {symbol}...")
    try:
        snapshot = data_engine.get_snapshot(symbol, "1m")
    except Exception as e:
        print(f"Failed to fetch snapshot: {e}")
        data_engine.stop()
        return

    print(f"Snapshot timestamp: {snapshot.timestamp}")
    print(f"Data Quality: {snapshot.data_quality.name}")
    
    def classify(val):
        import numpy as np
        if val is None: return "UNAVAILABLE"
        if isinstance(val, float) and np.isnan(val): return "UNAVAILABLE"
        return "REAL" # basic heuristic

    print("--- SNAPSHOT LINEAGE CLASSIFICATION ---")
    print(f"OHLCV: {'REAL' if snapshot.ohlcv else 'UNAVAILABLE'} (length: {len(snapshot.ohlcv) if snapshot.ohlcv else 0})")
    print(f"Order Book: {'REAL' if snapshot.order_book else 'UNAVAILABLE'}")
    print(f"Funding: {'REAL' if snapshot.funding else 'UNAVAILABLE'}")
    print(f"Funding History: {'REAL' if snapshot.funding_history else 'UNAVAILABLE'} (length: {len(snapshot.funding_history) if snapshot.funding_history else 0})")
    print(f"Open Interest: {'REAL' if snapshot.open_interest else 'UNAVAILABLE'}")
    print(f"OI History: {'REAL' if snapshot.open_interest_history else 'UNAVAILABLE'} (length: {len(snapshot.open_interest_history) if snapshot.open_interest_history else 0})")
    print(f"VWAP: {'REAL' if snapshot.vwap_raw is not None else 'UNAVAILABLE'} ({snapshot.vwap_raw})")
    
    # Trades are real, CVD/TVI derived from trades
    print(f"Trades/Volume: {'REAL' if snapshot.buy_volume is not None else 'UNAVAILABLE'}")
    print(f"CVD: {'DERIVED_FROM_REAL' if snapshot.cvd is not None else 'UNAVAILABLE'}")
    print(f"TVI: {'DERIVED_FROM_REAL' if snapshot.tvi is not None else 'UNAVAILABLE'}")
    
    state = math_engine.analyze(snapshot)
    
    print("\n--- MARKET STATE LINEAGE ---")
    print(f"Symbol: {state.symbol}")
    print(f"Timestamp: {state.timestamp}")
    print(f"Data Quality: {state.data_quality.name}")
    print(f"OI State: {state.oi_state}")
    print(f"Funding State: {state.funding_state}")
    print(f"Liquidity State: {state.liquidity_state}")
    print(f"Order Flow State: {state.order_flow_state}")
    print(f"Liquidation State: {state.liquidation_state}")
    print(f"VWAP State: {state.vwap_deviation} (deviation)")
    
    if state.microstructure:
        print("\n--- MICROSTRUCTURE (DERIVED_FROM_REAL) ---")
        for k, v in state.microstructure.__dict__.items():
            print(f"  {k}: {v}")
    
    print("\n--- FEATURE STATUSES ---")
    for k, v in state.feature_statuses.items():
        print(f"  {k}: {v.name if hasattr(v, 'name') else v}")
        
    data_engine.stop()

if __name__ == "__main__":
    main()
