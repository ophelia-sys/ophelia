# PHASE 5.3 CVD FEATURE AUDIT

**Date:** 2026-08-14

## Strict Missingness Semantics
The boolean flag `cvd_is_missing` has been strictly frozen. It mathematically represents **only** periods where the underlying Binance 5m CVD source data is natively absent.
Mathematical warm-ups, shift operations, or zero-variance periods **do not** set the missingness flag.

## Source Provenance Investigation
**BTCUSDT September 2022:**
- Binance monthly `aggTrades` source begins precisely at `2022-09-02 00:00:00 UTC` (`1662076800038`).
- Therefore `2022-09-01` is a genuine upstream source omission (288 rows).
- The exact-duplicate anomaly identified previously is a separate anomaly occurring strictly from September 2 onward, and does not mathematically cause the September 1 gap.

## BTCUSDT
- **Total 5m Rows:** 210,240

**`cvd_is_missing` Flag Status:**
- **Total Rows:** 210,240
- **NaN Count:** 0
- **Zero Flags (0):** 209,952
- **Source Missing Flags (1):** 288
- **Missing Percentage:** 0.14%


**Derived Feature NaN Decomposition:**
| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |
|---------|------------|------------------|--------------------------------|-----------------------------|
| cvd_delta_5m | 288 | 288 | 0 | 0 |
| cvd_delta_15m | 292 | 288 | 4 | 0 |
| cvd_delta_1h | 310 | 288 | 22 | 0 |
| cvd_imbalance_5m | 288 | 288 | 0 | 0 |
| cvd_imbalance_15m | 292 | 288 | 4 | 0 |
| cvd_imbalance_1h | 310 | 288 | 22 | 0 |
| cvd_zscore_5m | 864 | 288 | 574 | 2 |
| cvd_zscore_15m | 866 | 288 | 578 | 0 |
| cvd_zscore_1h | 1,450 | 288 | 596 | 566 |
| cvd_acceleration_15m | 298 | 288 | 10 | 0 |
| cvd_acceleration_1h | 334 | 288 | 46 | 0 |


## ETHUSDT
- **Total 5m Rows:** 210,240

**`cvd_is_missing` Flag Status:**
- **Total Rows:** 210,240
- **NaN Count:** 0
- **Zero Flags (0):** 209,952
- **Source Missing Flags (1):** 288
- **Missing Percentage:** 0.14%


**Derived Feature NaN Decomposition:**
| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |
|---------|------------|------------------|--------------------------------|-----------------------------|
| cvd_delta_5m | 288 | 288 | 0 | 0 |
| cvd_delta_15m | 292 | 288 | 4 | 0 |
| cvd_delta_1h | 310 | 288 | 22 | 0 |
| cvd_imbalance_5m | 288 | 288 | 0 | 0 |
| cvd_imbalance_15m | 292 | 288 | 4 | 0 |
| cvd_imbalance_1h | 310 | 288 | 22 | 0 |
| cvd_zscore_5m | 865 | 288 | 574 | 3 |
| cvd_zscore_15m | 1,441 | 288 | 578 | 575 |
| cvd_zscore_1h | 1,450 | 288 | 596 | 566 |
| cvd_acceleration_15m | 298 | 288 | 10 | 0 |
| cvd_acceleration_1h | 334 | 288 | 46 | 0 |


## SOLUSDT
- **Total 5m Rows:** 210,240

**`cvd_is_missing` Flag Status:**
- **Total Rows:** 210,240
- **NaN Count:** 0
- **Zero Flags (0):** 192,384
- **Source Missing Flags (1):** 17,856
- **Missing Percentage:** 8.49%


**Derived Feature NaN Decomposition:**
| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |
|---------|------------|------------------|--------------------------------|-----------------------------|
| cvd_delta_5m | 17,856 | 17,856 | 0 | 0 |
| cvd_delta_15m | 17,860 | 17,856 | 4 | 0 |
| cvd_delta_1h | 17,878 | 17,856 | 22 | 0 |
| cvd_imbalance_5m | 17,856 | 17,856 | 0 | 0 |
| cvd_imbalance_15m | 17,860 | 17,856 | 4 | 0 |
| cvd_imbalance_1h | 17,878 | 17,856 | 22 | 0 |
| cvd_zscore_5m | 19,007 | 17,856 | 574 | 577 |
| cvd_zscore_15m | 18,434 | 17,856 | 578 | 0 |
| cvd_zscore_1h | 18,452 | 17,856 | 596 | 0 |
| cvd_acceleration_15m | 17,866 | 17,856 | 10 | 0 |
| cvd_acceleration_1h | 17,902 | 17,856 | 46 | 0 |


## XRPUSDT
- **Total 5m Rows:** 210,240

**`cvd_is_missing` Flag Status:**
- **Total Rows:** 210,240
- **NaN Count:** 0
- **Zero Flags (0):** 209,376
- **Source Missing Flags (1):** 864
- **Missing Percentage:** 0.41%


**Derived Feature NaN Decomposition:**
| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |
|---------|------------|------------------|--------------------------------|-----------------------------|
| cvd_delta_5m | 864 | 864 | 0 | 0 |
| cvd_delta_15m | 870 | 864 | 6 | 0 |
| cvd_delta_1h | 897 | 864 | 33 | 0 |
| cvd_imbalance_5m | 864 | 864 | 0 | 0 |
| cvd_imbalance_15m | 870 | 864 | 6 | 0 |
| cvd_imbalance_1h | 897 | 864 | 33 | 0 |
| cvd_zscore_5m | 1,729 | 864 | 861 | 4 |
| cvd_zscore_15m | 1,731 | 864 | 867 | 0 |
| cvd_zscore_1h | 1,758 | 864 | 894 | 0 |
| cvd_acceleration_15m | 879 | 864 | 15 | 0 |
| cvd_acceleration_1h | 933 | 864 | 69 | 0 |


## BNBUSDT
- **Total 5m Rows:** 210,240

**`cvd_is_missing` Flag Status:**
- **Total Rows:** 210,240
- **NaN Count:** 0
- **Zero Flags (0):** 209,952
- **Source Missing Flags (1):** 288
- **Missing Percentage:** 0.14%


**Derived Feature NaN Decomposition:**
| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |
|---------|------------|------------------|--------------------------------|-----------------------------|
| cvd_delta_5m | 288 | 288 | 0 | 0 |
| cvd_delta_15m | 292 | 288 | 4 | 0 |
| cvd_delta_1h | 310 | 288 | 22 | 0 |
| cvd_imbalance_5m | 288 | 288 | 0 | 0 |
| cvd_imbalance_15m | 292 | 288 | 4 | 0 |
| cvd_imbalance_1h | 310 | 288 | 22 | 0 |
| cvd_zscore_5m | 864 | 288 | 574 | 2 |
| cvd_zscore_15m | 866 | 288 | 578 | 0 |
| cvd_zscore_1h | 884 | 288 | 596 | 0 |
| cvd_acceleration_15m | 298 | 288 | 10 | 0 |
| cvd_acceleration_1h | 334 | 288 | 46 | 0 |


## ADAUSDT
- **Total 5m Rows:** 210,240

**`cvd_is_missing` Flag Status:**
- **Total Rows:** 210,240
- **NaN Count:** 0
- **Zero Flags (0):** 209,952
- **Source Missing Flags (1):** 288
- **Missing Percentage:** 0.14%


**Derived Feature NaN Decomposition:**
| Feature | Total NaNs | cvd_is_missing=1 | Warmup/Prop (cvd_is_missing=0) | Zero-Var (cvd_is_missing=0) |
|---------|------------|------------------|--------------------------------|-----------------------------|
| cvd_delta_5m | 288 | 288 | 0 | 0 |
| cvd_delta_15m | 292 | 288 | 4 | 0 |
| cvd_delta_1h | 310 | 288 | 22 | 0 |
| cvd_imbalance_5m | 288 | 288 | 0 | 0 |
| cvd_imbalance_15m | 292 | 288 | 4 | 0 |
| cvd_imbalance_1h | 310 | 288 | 22 | 0 |
| cvd_zscore_5m | 1,443 | 288 | 574 | 581 |
| cvd_zscore_15m | 866 | 288 | 578 | 0 |
| cvd_zscore_1h | 1,450 | 288 | 596 | 566 |
| cvd_acceleration_15m | 298 | 288 | 10 | 0 |
| cvd_acceleration_1h | 334 | 288 | 46 | 0 |

