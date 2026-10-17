# PHASE 6.5 P7 CHECKPOINT

**STATUS:** P7 = READY FOR BLIND CONFIRMATION

## FROZEN DEFINITIONS (DO NOT ALTER)

**Terminology:** OHLCV-Derived Volume / Price Acceptance Proxies
(NOT "True Volume Profile")

### 1. price_to_vwap_8h
`VWAP_8h = sum(close * volume, 96) / sum(volume, 96)`
`feature = close / VWAP_8h - 1`

### 2. price_to_vwap_1d
`VWAP_1d = sum(close * volume, 288) / sum(volume, 288)`
`feature = close / VWAP_1d - 1`

### 3. volume_concentration_1d
`feature = volume / rolling_mean(volume, 288)`

### 4. value_area_proxy
`VWSD_1d = sqrt(sum(volume * (close - VWAP_1d)^2) / sum(volume))`
`feature = (close - VWAP_1d) / VWSD_1d`

## Technical Constraints Confirmed
- **Exact Rolling Windows:** Right-aligned, zero shift, explicitly uses `df.rolling(window)`. Current bar is strictly included.
- **Missingness Policy:** `min_periods=window`. First 287 bars are output as `NaN` and implicitly purged. No forward-filling.
- **Zero-Denominator Behavior:** `sum(volume) == 0` correctly results in `NaN`, which is safely ignored or dropped.
- **Causality:** STRICTLY CAUSAL. No future observations or target-period data enter the feature calculations.

## Audit Results
- Passed Integrity Audit (`PHASE6_4_P7_INTEGRITY_AUDIT.md`)
- Passed Causality Verification (`tests/test_phase6_4_p7_causality.py`)
