# PHASE 6.4 - P7 FEATURE REGISTRY (OHLCV-DERIVED VOLUME / PRICE ACCEPTANCE PROXIES)

## Conceptual Source
Computed strictly from local `BASE` 5m OHLCV data. These metrics proxy "Volume Profile" and "Price Acceptance" by quantifying where price is trading relative to recent heavy volume. 

**Disclaimer:** These are strictly OHLCV-derived approximations. They do NOT represent a true intra-bar tick-by-tick order-book Volume Profile.

## Timestamp & Causality Semantics
- **Inputs:** `close` and `volume` from the 5m OHLCV grid.
- **Availability Semantics:** All inputs for a candle ending at `T_decision` are assumed available at `T_decision`.
- **Missing-Data Behavior:** Handled natively by the baseline OHLCV processing (forward-filled closes, 0 volume).
- **Warmup Behavior:** 288 periods (24 hours) are required to warm up the 1-day VWAP and VWSD metrics.

## Features

### 1. `price_to_vwap_8h`
- **Definition:** The percentage deviation of the current close from the rolling 8-hour Volume Weighted Average Price (VWAP).
- **Formula:** `(close / VWAP_8h) - 1.0`
- **VWAP_8h Calculation:** `rolling_sum(close * volume, 96) / rolling_sum(volume, 96)`
- **Zero-Denominator Behavior:** If rolling volume over 8 hours is exactly 0, output 0.0.

### 2. `price_to_vwap_1d`
- **Definition:** The percentage deviation of the current close from the rolling 24-hour VWAP.
- **Formula:** `(close / VWAP_1d) - 1.0`
- **VWAP_1d Calculation:** `rolling_sum(close * volume, 288) / rolling_sum(volume, 288)`
- **Zero-Denominator Behavior:** If rolling volume over 24 hours is exactly 0, output 0.0.

### 3. `volume_concentration_1d`
- **Definition:** A measure of whether the current 5m volume is historically heavy relative to the past 24 hours.
- **Formula:** `volume / rolling_mean(volume, 288)`
- **Zero-Denominator Behavior:** If the 24-hour rolling mean volume is 0, output 1.0.

### 4. `value_area_proxy`
- **Definition:** A rigorous OHLCV-derived proxy for whether the current price is inside or outside the accepted "value area". It calculates the Z-Score of the current price relative to a Volume-Weighted Standard Deviation (VWSD) computed over 24 hours.
- **VWSD_1d Calculation:** `sqrt( rolling_sum(volume * (close - VWAP_1d)^2, 288) / rolling_sum(volume, 288) )`
- **Formula:** `(close - VWAP_1d) / VWSD_1d`
- **Zero-Denominator Behavior:** If VWSD_1d is 0 (or rolling volume is 0), output 0.0.

---
*Registry Frozen for Phase 6.4 Out-of-Sample evaluation.*
