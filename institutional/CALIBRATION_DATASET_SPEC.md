# OPHELIA — CALIBRATION DATASET SPECIFICATION

*Note: For the physical storage schema and collection mechanics, refer to `institutional/historical/PASSIVE_DATA_COLLECTION_SPEC.md`.*

This document formally specifies the chronological dataset required to calibrate Ophelia's probability engine ($P(\text{UP} | X_t)$ and $E[\text{Return} | X_t]$).

## 1. Canonical Observation ($X_t$)
An observation is captured exactly at decision timestamp $t$ (e.g., exactly at the 1-minute candle close).

### Identifiers
- `timestamp_ms`: INT64 (exact unix millisecond of the decision)
- `symbol`: STRING

### Price & Returns
- `close`: FLOAT64
- `log_return_1m`: FLOAT64 (trailing 1m return)

### Volatility & Regime
- `realized_volatility`: FLOAT64 (trailing RV)
- `rv_percentile`: FLOAT64 (0.0 to 1.0)
- `ker`: FLOAT64 (0.0 to 1.0)

### Microstructure (Top of Book)
- `mid_price`: FLOAT64
- `spread_bps`: FLOAT64
- `queue_imbalance`: FLOAT64 (-1.0 to 1.0)
- `microprice_deviation`: FLOAT64 (microprice - mid_price)

### Microstructure (Deep Book)
- `depth_imbalance`: FLOAT64 (-1.0 to 1.0)
- `visible_impact_buy`: FLOAT64 (BPS)
- `visible_impact_sell`: FLOAT64 (BPS)
- `book_slope_bid`: FLOAT64
- `book_slope_ask`: FLOAT64

### Order Flow
- `cvd_raw`: FLOAT64
- `cvd_zscore`: FLOAT64 (Robust MAD normalized)
- `tvi`: FLOAT64 (Ratio)
- `volume_zscore`: FLOAT64

### VWAP
- `vwap_deviation`: FLOAT64

### Positioning
- `open_interest_delta`: FLOAT64
- `funding_rate`: FLOAT64

## 2. Target Labels ($Y_t$)
Target labels strictly use information $> t$.
- `fwd_ret_1m`: $(Close_{t+1m} - Close_t) / Close_t$
- `fwd_ret_3m`: $(Close_{t+3m} - Close_t) / Close_t$
- `fwd_dir_1m`: $Sign(fwd\_ret\_1m)$
- `vol_adj_fwd_ret_3m`: $fwd\_ret\_3m / (RV_t \times \sqrt{3})$
- `mfe_3m`: $Max(High_{t \to t+3m}) - Close_t$
- `mae_3m`: $Min(Low_{t \to t+3m}) - Close_t$

## 3. Missing Data Policy
- Missing features are stored as `NaN` (or `null` in JSON/Parquet).
- **Prohibited:** Forward-filling missing data across disjoint sessions.
- **Prohibited:** Filling with $0$ (which is semantically meaningful for many Z-scores).

## 4. Normalization Rules
- **Look-Ahead Safe:** Any Z-Score or Percentile calculated for $X_t$ must use a trailing window $[t-N, t]$.
- Global standard scaling (`(X - mean(X_all)) / std(X_all)`) is **strictly prohibited**.
