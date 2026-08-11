# PHASE 5D BINGX DATA ACQUISITION & FEATURE FOUNDATION AUDIT

## 1. BingX Data Availability & Repair

### Verified & Repaired Data Streams
- **Open Interest**: Verified available at `/openApi/swap/v2/quote/openInterest`. Integrated into `BingXClient` and mapped via `InstitutionalRESTAdapter` into the engine. 
- **Funding Rate**: Verified available at `/openApi/swap/v2/quote/fundingRate`. Integrated into `BingXClient` (Historical Array format).
- **Premium Index**: Verified available at `/openApi/swap/v2/quote/premiumIndex`.
- **Depth (Order Book)**: Repaired lineage. Now routed correctly through `BingXClient.get_depth`.
- **Trades**: Repaired lineage. Now routed correctly through `BingXClient.get_trades`.

### Unavailable Data Streams
- **Liquidations (Force Orders)**: `/openApi/swap/v2/quote/forceOrders` returns `100400` (API does not exist).
- **Mark Price Klines**: `/openApi/swap/v2/quote/markPriceKlines` returns `100400` (API does not exist).

### Data Lineage Audit (PASS)
The architectural constraint `BingX -> BingXClient -> Institutional Adapter -> InstitutionalDataEngine` has been fully enforced. The `requests.Session()` bypass in `InstitutionalRESTAdapter` was removed.

## 2. Institutional Mathematical Features

### Open Interest (OI)
- **Status**: Implemented.
- **Lineage**: Direct REST payload via `BingXClient.get_open_interest`.
- **Taxonomy**: Explicitly documented as inferential hypotheses (LONG_INITIATION, SHORT_COVERING, etc) based on Delta Price and Delta OI.

### Funding
- **Status**: Implemented.
- **Lineage**: Direct REST payload via `BingXClient.get_funding_rate`.
- **Logic**: Uses robust Median Absolute Deviation (MAD) for Z-Score normalization. Falls back to Standard Deviation if MAD is 0.

### VWAP
- **Status**: Implemented in `institutional/vwap.py`.
- **Formulas**: trailing `sum(P*V)/sum(V)`. `vwap_deviation = (close - vwap)/vwap`. No lookahead bias (uses strict `.rolling()`).

### Volume
- **Status**: Implemented in `institutional/volume.py`.
- **Formulas**: Differentiates strictly between raw volume, quote volume, volume robust Z-Score, and volume percentiles.

### Order Flow
- **CVD**: Aggressor Buy Volume - Aggressor Sell Volume. (Implemented).
- **TVI**: CVD / Total Volume. (Implemented).
- **OFI**: Canonical Order Flow Imbalance. (STILL UNAVAILABLE). 

### Liquidity
- **Status**: Re-validated. `book_slope` uses correct regression: X = distance from mid in BPS, Y = cumulative quote notional (USDT). Units = USDT/BPS.

## 3. FGV / CISD Research Specification

### Fair Value Gap (FGV)
- **Definition**: A 3-candle imbalance where there is no overlap between the wick of candle 1 and candle 3, leaving a gap where only candle 2's body traded.
- **Variant**: Bullish FGV (C1_High < C3_Low), Bearish FGV (C1_Low > C3_High).
- **Data Required**: Standard OHLCV (available).
- **Look-ahead Risk**: High if calculated before C3 closes. Must strictly evaluate at `T > C3.timestamp`.
- **Objective Validation**: Time spent returning to the gap (mean-reversion speed) vs continuation probability.
- **Classification**: **RESEARCH ONLY**. Easy to implement, but heavily relies on discretionary PA concepts that need strict probability calibration first.

### Change in State of Delivery (CISD)
- **Definition**: A structural shift in the algorithmic delivery of price (e.g., consecutive up-close candles breaking prior swing structural pivots).
- **Data Required**: Standard OHLCV.
- **Look-ahead Risk**: Medium. Often requires "confirmed" pivot points which use future context (fractals). To avoid look-ahead, we must use PELT/CUSUM sequential structural break detection.
- **Incremental Information**: Provides regime-shift context.
- **Classification**: **RESEARCH ONLY**. The math is significantly more complex (requires HMM or PELT) and should not be a raw heuristic.

## 4. Composite Evidence Research Candidates

We will research (but not grant trading authority to) the following interactions:

1. **CVD + Microprice**: Are aggressive market orders accurately pushing the microprice, or is the limit book absorbing them (divergence)?
2. **CVD + Visible Impact**: Does a high CVD cause expected visible impact, or is hidden liquidity replacing the book?
3. **Volume Anomaly + CVD**: Extreme volume + zero CVD = hidden accumulation/distribution.
4. **Spread + Depth Imbalance + Visible Impact**: The true cost of liquidity combination.
5. **VWAP Deviation + CVD**: Is the VWAP reversion led by aggressive takers?

## 5. Repository-Wide Audits

### Look-ahead Audit
- **PASS**: `vwap.py` and `volume.py` rely entirely on pandas `.rolling(window).metric().iloc[-1]` with `min_periods=window`. No `shift(-1)` or future data leakage exists.

### OFI Lineage Audit
- **PASS**: String matching confirms no aliases. `depth_imbalance` != OFI, `queue_imbalance` != OFI, `CVD` != OFI. Canonical `OFI` remains classified as UNAVAILABLE.

### Execution Isolation Audit
- **PASS**: No calls to `place_order`, `cancel_order`, or any execution-related actions exist inside `institutional/`. The boundary remains purely observational.

### Tests
- **Collected**: 5 tests specifically for 5D features.
- **Passed**: 5
- **Failed**: 0
- **Skipped**: 0

## 6. Stop Condition
Phase 5D Feature Foundation is complete. We await explicit approval before proceeding to Phase 6 or giving V3 any production decision authority.
