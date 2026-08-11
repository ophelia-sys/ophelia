# OPHELIA — PHASE 5F.2: DATASET READINESS AUDIT

This document establishes the statistical readiness of Ophelia's passive historical dataset for probability calibration. 

**Audit Timestamp:** 2026-08-11
**Dataset Location:** `data/historical/ophelia_history.db`
**Raw Events Location:** `data/historical/raw/`

---

## 1. DATASET READINESS CLASSIFICATION

**STATUS:** `NOT_READY`

**Reason:** The historical data collection engine was just deployed in Phase 5F.1. The database currently contains exactly 4 synthetic/test observations and 0 complete usable rows. There is no sustained history available to calculate robust trailing metrics (such as VWAP, RV, Funding-Z) or perform out-of-sample probability calibration.

---

## 2. HISTORICAL DATA COLLECTION METRICS

| Metric | Value |
|--------|-------|
| Total $X_t$ Rows | 4 |
| Unique Symbols | 1 (`BTC-USDT`) |
| Time Span | 1000 to 1786356240 |
| Duplicate Count | 0 |
| Total Raw Trade Events | 0 |
| Total Raw Orderbook Events | 6 |

---

## 3. FEATURE COVERAGE

| Feature | Rows Available | Percentage |
|---------|----------------|------------|
| `close` | 2 | 50.0% |
| `mid_price` | 1 | 25.0% |
| `log_return` | 2 | 50.0% |
| `realized_volatility` | 0 | 0.0% |
| `vwap_deviation` | 0 | 0.0% |
| `spread` | 1 | 25.0% |
| `queue_imbalance` | 1 | 25.0% |
| `depth_imbalance` | 1 | 25.0% |
| `microprice_vs_mid` | 1 | 25.0% |
| `cvd` | 2 | 50.0% |
| `tvi` | 2 | 50.0% |
| `volume_zscore` | 0 | 0.0% |
| `open_interest_delta` | 0 | 0.0% |
| `funding_rate` | 0 | 0.0% |

**Data Quality Coverage:**
- `INSUFFICIENT_DATA`: 3
- `UNAVAILABLE`: 1

**Usable Calibration Sample Size:** 0 (0.0% intersection of primary features)

---

## 4. OFI & LIQUIDATION AUDIT

- **OFI (Order Flow Imbalance):** Remains `UNAVAILABLE`. No metrics in the current `$X_t` schema alias to OFI (verified manually and via tests).
- **Liquidations:** Remains `UNAVAILABLE`.

---

## 5. LEAKAGE AUDIT & EXECUTION ISOLATION

- **Execution Isolation:** The `PassiveDataCollector` hooks into `DecisionEngine.evaluate_signal` exclusively to extract state variables. It does not dictate logic, modify states, or submit orders.
- **Leakage Test:** Automated tests (`test_x_t_immutability` in `test_institutional_label_builder.py`) mathematically prove that producing labels for $T_{t+k}$ does not alter the persisted features of $X_t$. The database connection relies on strict immutability.
- **Future Timestamps:** `OfflineLabelBuilder` explicitly checks offsets (e.g. `1m = 60000ms`) to map forward returns. Rows missing future context properly receive `NaN` instead of nearest neighbors.

---

## 6. TEMPORAL CONTINUITY

The median observation interval cannot be confidently established due to lack of samples (calculated arbitrarily from the 4 test rows). Continuous runtime observation is strictly required to accumulate real sequential data.

---

## 7. REMAINING BLOCKERS

1. **Temporal History Required:** The system must run continuously over WebSocket to accumulate at least 7-14 days of uninterrupted feature state vectors before any meaningful data exploration can begin.
2. **Robustness of V3:** While V3 correctly classifies the missing data as `INSUFFICIENT_DATA` and returns `NaN`, the live environment must actually capture these events. 

---

**Conclusion:** Do NOT proceed to Phase 5F.3 (Model Training). The collector is operationally sound and fully isolated, but the dataset mathematically lacks the necessary samples. The system must simply run and observe the market.
