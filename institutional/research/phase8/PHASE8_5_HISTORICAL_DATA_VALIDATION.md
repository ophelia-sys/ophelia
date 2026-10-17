# PHASE 8.5 HISTORICAL DATA VALIDATION

Before any dataset is cleared for Probability Engine training, it must pass this validation checklist.

- [ ] **1. Granularity:** Dataset is exactly 1m OHLCV. No gaps larger than explicitly allowed by exchange downtime.
- [ ] **2. Null Preservation:** Missing derivatives/order-book data is represented as `NULL`/`np.nan`, not zero-filled.
- [ ] **3. Provenance Integrity:** No Binance L2 data is masquerading as BingX microstructure.
- [ ] **4. Leakage Checked:** `test_historical_feature_causality.py` passes on the final dataframe.
- [ ] **5. Label Validity:** `test_triple_barrier.py` confirms that intrabar ambiguity correctly yields a `NULL`/exclude label.
- [ ] **6. Feature Parity:** The features produced by the historical dataframe script exactly match the output of `InstitutionalMathEngine` given the same input window.
- [ ] **7. Sample Size:** The empirical effective sample size (non-overlapping labels) meets the minimum bound calculated in `SAMPLE_SIZE_ANALYSIS.md`.
- [ ] **8. Regime Diversity:** The dataset spans at least one major bull regime, bear regime, and low-volatility crab regime.
