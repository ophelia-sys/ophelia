# OPHELIA PHASE 5.4.1 OOS CONFIRMATION REPORT

**Date**: 2026-08-12
**Status**: RESEARCH ONLY — NO PRODUCTION CONTAMINATION
**Final Classification**: REJECTED

---

## 1. Executive Summary
Phase 5.4 established an isolated `+0.46 bps` Gross EV for the microstructure-enhanced model (a `+0.81 bps` incremental improvement over baseline). Phase 5.4.1 subjected this configuration to a strictly frozen, out-of-sample (OOS) chronological test to confirm whether the observed incrementality was a robust structural edge or merely an artifact of sample-specific variance. 
The out-of-sample results reversed the relationship: the baseline model achieved `+1.54 bps` Gross EV while the microstructure model achieved `+1.40 bps`, demonstrating a **-0.14 bps** incremental deterioration. Consequently, the microstructure model has been rejected as an economic candidate.

## 2. Phase 5.4 Baseline Result
- **Baseline Gross EV**: `-0.35 bps`
- **Baseline + All Microstructure Gross EV**: `+0.46 bps`
- **Incremental Gross EV**: `+0.81 bps`

## 3. Locked Configuration
The configuration (`phase5_4_1_locked_config.json`) was completely frozen prior to the OOS evaluation:
- **Features**: `ret_1`, `ret_5`, `ret_15`, `vol_15`, `mom_5` + `cvd_norm`, `snapshot_ofi_proxy_norm`, `mean_queue_imbalance`, `mean_relative_spread`.
- **Target**: `fwd_ret_5 > 0` (1-minute close, evaluated 5 minutes forward).
- **Cost Assumption**: 12 bps.
- **Model**: Logistic Regression (`max_iter=1000`, `random_state=42`).

## 4. OOS Period Definition
The previously unseen chronological period immediately following the development set was used:
- **Start**: `2023-11-06 00:00:00`
- **End**: `2023-11-10 23:59:59`
- **Data Source**: Binance Vision (`BTCUSDT` `bookTicker` + `aggTrades`)

## 5. OOS Purity Verification
A programmatic embargo (LABEL PURGE) was executed to guarantee that no development label leaked into the OOS period.
- 6 training rows from the end of `2023-11-05` were forcibly purged because their forward 5-minute outcome windows extended into `2023-11-06`.
- We asserted `max(training_label_end) < min(OOS_decision_timestamp)`. The assertion passed perfectly.

## 6. Timestamp / Causality Verification
The `CANDLE CLOSE` decision timestamp convention was verified. 
- Features are strictly limited to `source_timestamp <= decision_close(T)`.
- Outcomes strictly begin after `decision_close(T)`.

## 7. Common Sample Verification
To prevent selection bias, models were compared strictly on overlapping timestamps.
- **Total OOS Rows**: 7,200
- **Baseline Eligible**: 7,180
- **Microstructure Eligible**: 7,195
- **Common Eligible OOS Rows**: 7,180
- **Excluded Rows (from Baseline)**: 0

## 8. Baseline OOS Results
- **AUC**: 0.5198
- **Brier**: 0.2497
- **Gross EV**: +1.54 bps
- **Net EV (12 bps cost)**: -10.46 bps
- **Trades Generated**: 918

## 9. Microstructure OOS Results
- **AUC**: 0.5011
- **Brier**: 0.2527
- **Gross EV**: +1.40 bps
- **Net EV (12 bps cost)**: -10.60 bps
- **Trades Generated**: 476

## 10. Incremental Economic Value
The primary metric is incremental cost-adjusted economic value:
- **Incremental Gross EV**: -0.14 bps
- **Incremental Net EV**: -0.14 bps
Microstructure underperformed the baseline out-of-sample.

## 11. Statistical Significance
Given the negative incremental economic value and the reduction in AUC (`0.5198` vs `0.5011`), the microstructure features did not improve the predictive statistics nor the economic outcomes. The `+0.81 bps` Phase 5.4 improvement was conclusively an artifact of the validation set rather than a stationary statistical edge. 

## 12. Cost Sensitivity
The frozen Phase 5.4 cost profile was precisely 12 bps. At a Gross EV of +1.40 bps, the microstructure strategy fails the 12 bps hurdle rate significantly. There is no positive Net EV scenario.

## 13. Feature Provenance
- `cvd` and `snapshot_ofi_proxy` were successfully generated natively from raw `aggTrades` and `bookTicker` files spanning the unseen OOS 5-day horizon without data corruption.

## 14. OFI Semantic Audit
No aliases mapping `snapshot_ofi_proxy` to `ofi` were found. The codebase explicitly maintains the boundary: **Canonical OFI = UNAVAILABLE / UNVERIFIED**.

## 15. Errors Discovered
No implementation or methodological errors were discovered during Phase 5.4.1 audit.

## 16. Fixes
N/A. The experimental architecture successfully handled the boundary limits naturally.

## 17. Regression Tests
All 164 Ophelia unit and integration tests (`pytest tests/`) were run using the full `PYTHONPATH` context and passed cleanly. The causal alignment synthetic test (`tests/test_causal_alignment.py`) was also independently verified.

## 18. Independent Reconciliation
`exp_026_oos_reconciliation.py` successfully and independently recalculated the exact metrics from the generated OOS prediction artifacts (`oos_predictions.parquet`). The calculations confirmed:
- Baseline Gross EV: 1.54 bps
- Base + All Micro Gross EV: 1.40 bps
- Target/Stop hit rates and MAE/MFE exactly aligned with the primary script.

## 19. Final Classification
**REJECTED**.
The out-of-sample incremental improvement was negative. The Phase 5.4 baseline improvement was not robust across unseen datasets.

## 20. Production Decision
**DO NOT DEPLOY**.
The addition of the microstructure family fails to establish positive cost-adjusted economics or statistical stability.

## 21. Recommended Next Step
As microstructure (Phase 5.4) did not resolve the profitability barrier, and considering that previous Phase 5 tests (features, non-linearities, barriers, entry timing) have also failed the 12 bps transaction cost hurdle on event-based forecasting, we recommend advancing to the next structural phase (Phase 5.5). The pure 1-minute event prediction model requires fundamental architectural evolution (e.g. regime awareness, higher timeframe integration, or transition to a different market-making paradigm) rather than further isolated tuning.

*Note: 5 days is a limited confirmation window, but failing to clear the hurdle rate on the immediate chronologically adjacent unseen data strongly supports rejection before committing to larger OOS allocations.*
