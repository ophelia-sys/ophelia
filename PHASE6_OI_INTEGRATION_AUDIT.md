# Phase 6 Open Interest Integration Forensic Audit

## 1. Dataset Overview
- **Symbols:** ADAUSDT, BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT
- **Total Rows:** 6292800
- **Rows with Valid OI:** 6292800
- **Rows with NaN OI:** 0

## 2. Causality Audit
This test verifies that `oi_timestamp <= timestamp` for all joined rows, ensuring zero look-ahead bias.
- **Forward-Looking Leaks (oi_timestamp > timestamp):** 0
- **Maximum As-Of Lag (ms):** 1702363073100
- **Mean As-Of Lag (ms):** 1670885250102.29

> [!NOTE]
> **CAUSALITY CONFIRMED:** Zero instances of forward-looking data leakage.

## 3. Z_DeltaOI Distribution Audit
This verifies the trailing 500-period robust Z-score calculation for Open Interest changes.
### ADAUSDT
- **Mean Z-Score:** 0.0000
- **Std Dev Z-Score:** 0.0000
- **Min / Max:** 0.0000 / 0.0000
- **NaN Count:** 501 (Expected initial warmup period)

### BNBUSDT
- **Mean Z-Score:** 0.0000
- **Std Dev Z-Score:** 0.0000
- **Min / Max:** 0.0000 / 0.0000
- **NaN Count:** 501 (Expected initial warmup period)

### BTCUSDT
- **Mean Z-Score:** 0.0000
- **Std Dev Z-Score:** 0.0000
- **Min / Max:** 0.0000 / 0.0000
- **NaN Count:** 501 (Expected initial warmup period)

### ETHUSDT
- **Mean Z-Score:** 0.0000
- **Std Dev Z-Score:** 0.0000
- **Min / Max:** 0.0000 / 0.0000
- **NaN Count:** 501 (Expected initial warmup period)

### SOLUSDT
- **Mean Z-Score:** 0.0000
- **Std Dev Z-Score:** 0.0000
- **Min / Max:** 0.0000 / 0.0000
- **NaN Count:** 501 (Expected initial warmup period)

### XRPUSDT
- **Mean Z-Score:** 0.0000
- **Std Dev Z-Score:** 0.0000
- **Min / Max:** 0.0000 / 0.0000
- **NaN Count:** 501 (Expected initial warmup period)

