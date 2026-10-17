import time
import json
import logging
from institutional.data.engine import InstitutionalDataEngine
from institutional.data.rest_adapter import InstitutionalRESTAdapter

logging.basicConfig(level=logging.INFO)

def smoke_test():
    print("=== STARTING SMOKE TEST ===")
    
    # 1. Test REST directly to see exact payloads
    adapter = InstitutionalRESTAdapter()
    
    print("\n--- REST KLINES ---")
    klines_raw = adapter._get("/openApi/swap/v2/quote/klines", {"symbol": "BTC-USDT", "interval": "1m", "limit": 2})
    print(json.dumps(klines_raw, indent=2))
    
    print("\n--- REST DEPTH ---")
    depth_raw = adapter._get("/openApi/swap/v2/quote/depth", {"symbol": "BTC-USDT", "limit": 5})
    print(json.dumps(depth_raw, indent=2))
    
    print("\n--- REST TRADES ---")
    trades_raw = adapter._get("/openApi/swap/v2/quote/trades", {"symbol": "BTC-USDT", "limit": 5})
    print(json.dumps(trades_raw, indent=2))
    
    print("\n--- REST OPEN INTEREST ---")
    oi_raw = adapter._get("/openApi/swap/v2/quote/openInterest", {"symbol": "BTC-USDT"})
    print(json.dumps(oi_raw, indent=2))

    print("\n--- REST FUNDING RATE ---")
    funding_raw = adapter._get("/openApi/swap/v2/quote/fundingRate", {"symbol": "BTC-USDT"})
    print(json.dumps(funding_raw[:2] if isinstance(funding_raw, list) else funding_raw, indent=2))

    print("\n--- REST LIQUIDATIONS ---")
    liq_raw = adapter._get("/openApi/swap/v2/quote/forceOrders", {"symbol": "BTC-USDT"})
    print(json.dumps(liq_raw, indent=2))

    print("\n--- TESTING ENGINE WITH WS ---")
    engine = InstitutionalDataEngine(use_ws=True)
    engine.start(["BTC-USDT"])
    
    print("Waiting 5 seconds to accumulate trades...")
    time.sleep(5)
    
    snapshot = engine.get_snapshot("BTC-USDT", "1m")
    
    print(f"\nSnapshot received:")
    print(f"Data Quality: {snapshot.data_quality}")
    print(f"Buy Vol: {snapshot.buy_volume}, Sell Vol: {snapshot.sell_volume}, CVD: {snapshot.cvd}")
    print(f"Trades count: {len(engine._trades.get('BTC-USDT', []))}")
    
    engine.stop()
    print("\n=== SMOKE TEST COMPLETE ===")

if __name__ == "__main__":
    smoke_test()
