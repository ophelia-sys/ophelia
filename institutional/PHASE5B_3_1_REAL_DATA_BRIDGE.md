# Phase 5B.3.1: Real Institutional Data Bridge

## Overview
This phase connects the `InstitutionalDataEngine` to the `DecisionEngine` so that V3 Shadow Mode can evaluate real institutional data (such as CVD, TVI, and order book metrics) rather than relying on synthetic/legacy snapshots derived purely from 1-minute klines.

## Architecture Guidelines
- **No Direct Execution**: The V3 system remains purely observational. The output of V3 does not drive actual trading.
- **Lineage Integrity**: Data flows strictly from `BingX` -> `InstitutionalDataEngine` -> `MarketDataSnapshot` -> `DecisionEngine.evaluate()`.
- **Data Coordination**: `InstitutionalDataEngine` is instantiated and managed by `TradingEngine`, which injects it into `Scanner`. `Scanner` queries the snapshot alongside regular market data and injects it into the `DecisionEngine`. No new connections to BingX are made inside `DecisionEngine`.
- **Legacy Fallback**: If institutional data is missing or fails to be retrieved, the pipeline falls back to using synthetic `df_1m` based data, ensuring that the legacy pipeline remains functional.
- **OFI Prohibition**: Canonical OFI (`order_flow_state`) remains `UNAVAILABLE`. Proxy microstructure metrics (like `depth_imbalance` or `queue_imbalance`) retain their own distinct identities and are not aliases for OFI.

## Implementation Details
1. **`core.trading_engine`**:
   - Initializes `InstitutionalDataEngine` and manages its lifecycle (`start`/`stop`).
   - Injects it into the `Scanner` initialization.
2. **`core.scanner`**:
   - `Scanner` receives the `institutional_data` object upon initialization.
   - During `scan_symbol`, `Scanner` attempts to fetch a real `MarketDataSnapshot`. If an exception occurs, it logs a warning and proceeds with `snapshot=None`.
   - Passes the `snapshot` to `DecisionEngine.evaluate()`.
3. **`core.decision_engine`**:
   - Updates `evaluate` signature to accept an optional `MarketDataSnapshot`.
   - In Shadow Mode, logs whether it's using `REAL_INSTITUTIONAL_DATA`, `PARTIAL_INSTITUTIONAL_DATA`, or `SYNTHETIC/LEGACY_INPUT`.
   - Validates that V3 failures or missing fields do not disrupt legacy decision-making logic or state.

## Verification
- Ensures 100% test coverage including legacy components and institutional math paths without breaking.
- Validates the shadow mode deep copy state-mutation checks still pass.
- Evaluates that V3 `order_flow_state` mapping behaves strictly as intended.
