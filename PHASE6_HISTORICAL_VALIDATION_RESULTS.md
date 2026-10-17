# Phase 6 Historical Empirical Validation Results

## 1. Dataset Identity
- **Dataset ID:** `binance_um_btcusdt_1m_v1`
- **Source:** Binance Vision USDⓈ-M perpetual futures
- **Symbol:** BTCUSDT
- **Interval:** 1m
- **Date Range:** 2023-01-01 to 2023-03-31
- **Observation Count:** 129600

## 2. Data Quality
- **Audit Status:** PASS
- **Completeness:** 100.0%
- **Missing Intervals (Gaps):** 0

## 3. Event Accounting
- **Raw Event Count:** 7866
- **Cluster Count:** 7866
- **Primary Events:** 7866
- **Non-Primary Events:** 0

**Primary Events by Type:**
- POOL_CONFIRMATION: 7866

## 4. OOS Walk-Forward Fold Structure
Chronological Train -> Purge (60m) -> Embargo (24h) -> Test
### Fold 1
- Train Start: 1672531200000
- Train End: 1673619780000
- Purge End: 1673623431600
- Embargo End: 1673709831600
- Test Start: 1673709840000
- Test End: 1674086340000
- Train Event Count: 1060
- Test Event Count: 381
### Fold 2
- Train Start: 1674086400000
- Train End: 1675174980000
- Purge End: 1675178619600
- Embargo End: 1675265019600
- Test Start: 1675265040000
- Test End: 1675641540000
- Train Event Count: 1049
- Test Event Count: 381
### Fold 3
- Train Start: 1675641600000
- Train End: 1676730180000
- Purge End: 1676733807600
- Embargo End: 1676820207600
- Test Start: 1676820240000
- Test End: 1677196740000
- Train Event Count: 1095
- Test Event Count: 387
### Fold 4
- Train Start: 1677196800000
- Train End: 1678285380000
- Purge End: 1678288995600
- Embargo End: 1678375395600
- Test Start: 1678375440000
- Test End: 1678751940000
- Train Event Count: 1107
- Test Event Count: 389
### Fold 5
- Train Start: 1678752000000
- Train End: 1679840580000
- Purge End: 1679844183600
- Embargo End: 1679930583600
- Test Start: 1679930640000
- Test End: 1680307140000
- Train Event Count: 1157
- Test Event Count: 408

## 5. Baseline Statistics (TEST)
| Horizon | N | Mean Return | Std Dev |
|---|---|---|---|
| 1m | 31379 | 0.000004 | 0.000820 |
| 3m | 31377 | 0.000011 | 0.001412 |
| 5m | 31375 | 0.000019 | 0.001797 |
| 15m | 31365 | 0.000055 | 0.003128 |
| 30m | 31350 | 0.000114 | 0.004478 |
| 60m | 31320 | 0.000226 | 0.006282 |

## 6. OOS Statistical Inference
| Feature | Horizon | N | Mean | Excess | Effect Size | HAC SE | Raw p-val | FDR p-val | 95% CI Lower | 95% CI Upper | Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FVG_CONFIRMATION | 1m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| FVG_CONFIRMATION | 3m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| FVG_CONFIRMATION | 5m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| FVG_CONFIRMATION | 15m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| FVG_CONFIRMATION | 30m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| FVG_CONFIRMATION | 60m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| POOL_CONFIRMATION | 1m | 1946 | 0.000027 | 0.000023 | 0.028268 | 0.000018 | 0.2053 | 0.7327 | -0.000018 | 0.000059 | EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE |
| POOL_CONFIRMATION | 3m | 1946 | 0.000029 | 0.000018 | 0.012581 | 0.000035 | 0.6106 | 0.7327 | -0.000049 | 0.000090 | EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE |
| POOL_CONFIRMATION | 5m | 1946 | 0.000005 | -0.000014 | -0.007755 | 0.000041 | 0.7334 | 0.7334 | -0.000089 | 0.000066 | EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE |
| POOL_CONFIRMATION | 15m | 1945 | 0.000113 | 0.000058 | 0.018661 | 0.000085 | 0.4914 | 0.7327 | -0.000114 | 0.000226 | EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE |
| POOL_CONFIRMATION | 30m | 1944 | 0.000220 | 0.000106 | 0.023559 | 0.000151 | 0.4851 | 0.7327 | -0.000184 | 0.000408 | EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE |
| POOL_CONFIRMATION | 60m | 1942 | 0.000431 | 0.000206 | 0.032732 | 0.000264 | 0.4368 | 0.7327 | -0.000332 | 0.000717 | EMPIRICAL EVIDENCE FAILS TO SUPPORT FEATURE |
| LIQUIDITY_SWEEP | 1m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| LIQUIDITY_SWEEP | 3m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| LIQUIDITY_SWEEP | 5m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| LIQUIDITY_SWEEP | 15m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| LIQUIDITY_SWEEP | 30m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |
| LIQUIDITY_SWEEP | 60m | 0 | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | INCONCLUSIVE / INSUFFICIENT DATA |

## 7. Power Analysis (Simulation)
- **Status:** ADEQUATELY POWERED
- **Effective N:** 1946
- **Minimum Detectable Effect (MDE):** 0.000399
  - Power at 0.05 effect: 100.00%
  - Power at 0.10 effect: 100.00%
  - Power at 0.15 effect: 100.00%
  - Power at 0.20 effect: 100.00%
  - Power at 0.25 effect: 100.00%

## 8. Cost Analysis (Horizon=60m)
### OPTIMISTIC
- Events N: 1942
- Mean Net Return: 0.000031
- Total Net Return: 0.060997
- Total Fees: 0.776800
- Total Slippage: 0.000000
### REALISTIC
- Events N: 1942
- Mean Net Return: -0.000269
- Total Net Return: -0.521603
- Total Fees: 1.359400
- Total Slippage: 0.000000
### PESSIMISTIC
- Events N: 1942
- Mean Net Return: -0.000569
- Total Net Return: -1.104203
- Total Fees: 1.942000
- Total Slippage: 0.000000
### BINGX_SIMULATION
- Events N: 1942
- Mean Net Return: -0.000569
- Total Net Return: -1.104203
- Total Fees: 1.359400
- Total Slippage: 0.582600

## 9. Limitations & Next Steps
- Parameter Optimization: NOT PERFORMED — EXPLORATORY FIXED PARAMETERS
- OI/OFI/Microprice: NOT AVAILABLE (Requires orderbook history)

**Recommended Next Action:**
Extend dataset or integrate Open Interest features to achieve full empirical capability before engaging LIVE risk logic.