# PHASE 5.3 AUDIT AND RERUN REPORT

## 1. Audit Objectives and Scope
This report documents the rigorous adversarial audit and reconciliation of the Phase 5.3 microstructure/barrier pipeline. The core mandate was to:
1. Verify timeframe semantics (1m vs 5m) across datasets.
2. Establish a causality framework to prove no forward-looking data leaks.
3. Quantify precise expected values (EV) across two distinct ambiguity policies (Conservative Exclusion vs. Worst Case).
4. Perform an off-by-one verification of the Numba barrier generation logic.
5. Create a standalone EV calculator independent of the pipeline to cross-verify the gross/net economic calculations.

## 2. Key Findings

### 2.1 Timeframe Correction
The dataset `v2_fixed_timestamp/BTCUSDT.parquet` has been definitively audited and proven to consist of **1-minute (1m)** candles, not 5-minute candles as was described in the initial iterations of Phase 5.
- Therefore, the barrier timeout `max_horizon = 60` corresponds strictly to a **60-minute holding period**, not 5 hours.
- A separate `PHASE5_TIMEFRAME_CORRECTIVE_REPORT.md` has been issued to historically document this mapping error while preserving the original artifacts.

### 2.2 Barrier Logic Off-By-One Audit
Unit tests (in `test_phase5_3_audit.py`) using hand-calculated arrays confirm that `_compute_barrier_numba`:
- **Correctly excludes T**: Looks only at T+1 to T+60.
- **Properly attributes targets and stops**: Resolves intra-bar ambiguity using the selected `OUTCOME_AMBIGUOUS` flag correctly without assuming the favorable path.
- **Truncates safely**: Properly handles array-boundary timeouts without indexing errors.

### 2.3 Ambiguity Policy Verification
Two policies were evaluated using an independent EV calculator script against the generated labels:
- `CONSERVATIVE_EXCLUSION`: Excludes trades where TP and SL are hit in the same bar.
- `WORST_CASE`: Assumes `OUTCOME_AMBIGUOUS` results in `OUTCOME_STOP` (-SL).

**Finding:** The two policies yield nearly identical Net Expected Value (~0.03 bps difference) at 60m horizons because ambiguity occurrences are extremely rare on 1m bars (only 0.3% of events).

### 2.4 Microstructure Causality Check
The proxies (`ofi_proxy_z`, `taker_buy_ratio`, `delta_oi_z`) are calculated securely.
- **Test:** Intentionally corrupting data at T+15 had zero effect on the generated feature values at T.
- The use of `pandas.Series.rolling(window=60).mean()` strictly accesses `[T-59, T]` correctly without lookahead.

### 2.5 Cost Semantics & P(Net > 0) Anomaly
The audit resolved the strange behavior where `P(Net > 0)` crashed when transaction costs reached 20 bps:
- The target threshold was set to `20 bps`.
- Therefore, a winning trade (hitting TP) yielded exactly `+20 bps` gross return.
- `Net = Gross - Cost = 20 - 20 = 0 bps`.
- Since the metric checked for *strictly positive* returns (`Net > 0`), break-even trades were counted as non-positive. This mathematical phenomenon was fully verified by the independent synthetic calculator.

## 3. Re-run Results (Experiment 014)
The baseline event model (Logistic Regression, Base Features) was trained to predict the 20/15 (TP/SL) barrier at a 60-minute timeout.

### 3.1 Model Diagnostics (WORST_CASE)
- **Validation AUC:** ~0.5699
- **Average Holding Time:** 11.4 minutes (previously thought to be 57 minutes due to the 5m mislabel).
- **Cost Sensitivity:**
  - Cost: 6 bps | Net EV: -4.81 bps | Gross EV: 1.19 bps | P(Net>0): 0.4550
  - Cost: 12 bps | Net EV: -10.81 bps | Gross EV: 1.19 bps | P(Net>0): 0.4543
  - Cost: 20 bps | Net EV: -18.81 bps | Gross EV: 1.19 bps | P(Net>0): 0.0070

*Note: The model captures an edge in predicting directional events (AUC > 0.50), yielding a positive gross return (1.19 bps). However, it is entirely incapable of overcoming the 12 bps operational cost.*

## 4. Re-run Results (Experiment 015 - Microstructure)
The microstructure ablation study was re-run cleanly on the 1m dataset.

- **BASELINE EVENT MODEL:** AUC 0.5699 | Net EV: -10.81 bps
- **BASELINE + taker_buy_ratio:** AUC 0.5700 | Net EV: -10.70 bps
- **BASELINE + ofi_proxy_z:** AUC 0.5699 | Net EV: -10.81 bps
- **BASELINE + delta_oi_z:** AUC 0.5700 | Net EV: -10.85 bps
- **BASELINE + ALL MICROSTRUCTURE:** AUC 0.5699 | Net EV: -10.76 bps

### Microstructure Conclusion
The microstructure proxies (`ofi_proxy_z`, `taker_buy_ratio`, `delta_oi_z`) failed to improve the Out-of-Sample AUC or Economic Value of the model.

- **Statistical Edge:** Remained stagnant (~0.5700).
- **Economic Edge:** Remained severely negative (~ -10.8 bps).

## 5. Final Reconciliation
The Phase 5.3 pipeline is mathematically sound. The prior results were factually accurate in their economic outputs, though they incorrectly labelled the unit-time horizon. 

With the 1-minute dataset fully verified and the microstructure edge thoroughly invalidated under real-world transaction costs, Phase 5.3 research is successfully completed.

**Status:**
- Statistical Edge: **YES**
- Economic Edge: **NO**
- Ready for Production: **NO**
