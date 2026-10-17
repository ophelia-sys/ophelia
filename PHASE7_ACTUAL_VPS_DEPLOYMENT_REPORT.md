# PHASE 7: ACTUAL VPS DEPLOYMENT REPORT

## 1. Executive Summary
The actual deployment to the isolated Ubuntu VPS (`ubuntu@15.235.193.47`) has been completed successfully. 
The system architecture was meticulously preserved. The Phase 7 mathematically frozen models (`institutional/cvd/live_engine.py`) have been deployed exactly as specified in the Phase 7 constraints.

## 2. Status Configuration
* **VPS PREFLIGHT**: EXECUTED AND PASSED
* **SHADOW**: WARMING_UP (Buffer 1/288)
* **SHADOW_START_UTC**: PENDING (Estimated: 2026-08-17 13:00:00 UTC)
* **HOST**: VPS (`ubuntu@15.235.193.47`)
* **PAPER**: NOT AUTHORIZED
* **LIVE**: NOT AUTHORIZED

## 3. Mathematical Parity and 24-Hour Buffer
During initial startup, it was observed that the core `TradingEngine` logged `Probability: NONE (Failed Closed)` for all configured coins. 

**Investigation and Conclusion:**
This behavior is not a bug; it is the mathematically purest manifestation of the Phase 7 constraint enforcement. 
The CVD models heavily rely on rolling Z-Scores of buy/sell volume imbalances over 288 periods (24 hours). 
Because the BingX REST API does not provide historical buy/sell delta volume, the internal `InstitutionalDataEngine` is forced to aggregate these metrics from real-time WebSocket tick data. 
If the engine were to calculate Z-Scores with less than 24 hours of data, the metrics would lack mathematical parity with the Phase 5 research dataset.
To prevent dataset pollution and ensure 100% decision logic parity, the engine correctly fails closed and returns `None`.

**Transparency Enhancement:**
To provide real-time status updates without violating mathematical constraints, the engine was updated to emit its current buffer status:
`[PHASE 7] BTC-USDT Buffer Warming: X/288 blocks (Failed Closed)`

## 4. Services 
* **`ophelia-shadow.service`**: Active, connecting to WebSockets, scheduling 5m evaluation ticks accurately.
* **`ophelia-telegram-monitor.service`**: Active, listening to systemd journal entries.

## 5. Next Steps
1. Allow the engine to organically consume 24 hours of live market data (`288` blocks).
2. At approximately **2026-08-17 13:00:00 UTC**, the buffer will be fully populated.
3. The engine will seamlessly transition from `Buffer Warming` to evaluating `Probability: 0.xxxx` and writing `[SHADOW_JSON]` logs.
4. Once the first `[SHADOW_JSON]` appears in the logs, `SHADOW_START_UTC` should be recorded and the official 24-hour Shadow Window will begin.
