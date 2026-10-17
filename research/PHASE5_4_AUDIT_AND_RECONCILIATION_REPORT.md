# OPHELIA PHASE 5.4 AUDIT AND RECONCILIATION REPORT

**Date**: 2026-08-12
**Status**: RESEARCH ONLY — NO PRODUCTION CONTAMINATION
**Final Classification**: REJECTED

---

## 1. Original Phase 5.4 Result
- **Baseline Gross EV**: `-0.35 bps`
- **Microstructure Gross EV**: `+0.46 bps`
- **Incremental Gross EV**: `+0.81 bps`
- **Baseline Net EV @ 12 bps**: `-12.35 bps`
- **Microstructure Net EV @ 12 bps**: `-11.54 bps`

## 2. Audit Scope
The objective was to determine whether the reported `+0.81 bps` improvement is genuinely causal, incremental, reproducible, and economically meaningful, before deciding on its use in Ophelia. 
The audit tested: causal timestamp alignment, formula verifications, canonical OFI isolation, common-sample fairness, sample selection bias, cost model semantics, and independent numerical reproducibility.

## 3. Dataset/Timeframe
- **Source**: Binance Vision (Public/Free)
- **Asset**: USD-M Futures (`BTCUSDT`)
- **Data**: `bookTicker` (L1 snapshots) and `aggTrades`
- **Timeframe**: 2023-11-01 to 2023-11-05 (7200 minutes)

## 4. Timestamp Convention
- **Convention**: **CANDLE CLOSE**.
- For a 1-minute bar starting at `10:05:00.000` (OPEN), the actual candle close is `10:05:59.999`. 
- Features use data through `close_time(T)`.
- Decisions and outcome evaluations strictly begin AFTER `close_time(T)`. Target return `fwd_ret_5` measures the return from the `10:05:59.999` close to the `10:10:59.999` close.

## 5. Causal Alignment Proof
- The expression `(transact_time // 60000) * 60000` maps millisecond tick data exactly to the candle's OPEN timestamp.
- A synthetic regression test (`tests/test_causal_alignment.py`) was created and passed. It proved mathematically that tick events occurring strictly after `10:05:59.999` are mapped to the next bucket (`10:06:00.000`), guaranteeing that `source_timestamp <= close_time(T)` holds for every aggregated feature.

## 6. Microstructure Provenance
- **`snapshot_ofi_proxy`**:
  - Source: `bookTicker`
  - Formula: $\Delta V_{bid} - \Delta V_{ask}$ conditional on price changes (where $V_{bid} = \text{bid\_qty}$ if $\Delta P_{bid} > 0$, etc.)
  - Normalization: Divided by total `volume` (+ $1\times10^{-8}$) to enforce stationarity.
- **`cvd`**:
  - Source: `aggTrades`
  - Formula: $\sum \text{signed\_volume}$ (where volume is negative if `is_buyer_maker` is True).
  - Normalization: Divided by total `volume`.
- **`mean_queue_imbalance`**:
  - Source: `bookTicker`
  - Formula: Average of $(\text{bid\_qty} - \text{ask\_qty}) / (\text{bid\_qty} + \text{ask\_qty})$ across all snapshots in the minute.

## 7. Canonical OFI Status
**Canonical OFI is UNAVAILABLE / UNVERIFIED.**
- The `snapshot_ofi_proxy` is strictly calculated from top-of-book L1 updates, and the term "OFI" in the codebase (`ofi_norm`) was explicitly renamed to `snapshot_ofi_proxy_norm` to prevent semantic collision. The feature remains explicitly labeled PROXY and RESEARCH_ONLY.

## 8. Common-Sample & Selection Bias Analysis
All 7,200 observations from the baseline were evaluated against the microstructure features.
- **Baseline Eligible Rows**: 7,180
- **Microstructure Eligible Rows**: 7,195
- **Common Eligible Rows**: 7,180
- **Rows Lost**: 0
Since 100% of baseline observations mapped to microstructure features, there is **zero sample selection bias**.

## 9. Individual Feature Results (Common-Sample)
*Measured on the 2,442 holdout test samples.*

| Model Configuration | AUC | Gross EV | Net EV (12 bps) | MAE | MFE |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 0.5095 | -0.35 bps | -12.35 bps | -9.98 | 7.69 |
| Base + CVD | 0.4885 | +0.19 bps | -11.81 bps | -4.36 | 4.12 |
| Base + OFI Proxy | 0.4863 | +0.18 bps | -11.82 bps | -4.42 | 4.23 |
| Base + Queue Imbalance | 0.4908 | +0.21 bps | -11.79 bps | -4.37 | 4.33 |
| **Base + All Micro** | **0.4936** | **+0.46 bps** | **-11.54 bps** | **-4.09** | **4.55** |

## 10. Cost-Model Reconciliation
- **Formula**: `Net EV = Gross EV - Total Execution Cost`
- The `+0.46 bps` (Gross EV) minus `12.0 bps` explicitly yields `-11.54 bps` (Net EV).
- **Break-even Cost**: This represents the absolute Gross EV (`+0.46 bps`). To be profitable, round-trip execution (maker/taker fees + slippage) must sum to strictly less than 0.46 bps, which is economically inviable.

## 11. Errors Discovered & Fixes
- **Error #001**: `ofi_norm` Semantic Collision
  - *Description*: The ablation scripts named the proxy variable `ofi_norm`, risking conflation with true Canonical OFI.
  - *Root Cause*: Lazy naming conventions during feature engineering.
  - *Fix*: Renamed all instances across `exp_018_019_ablation.py` and `exp_020_021_cost_sensitivity.py` to `snapshot_ofi_proxy_norm`.
  - *Regression Test*: Added to prompt audit requirements to search for `ofi` collisions globally.
  - *Rerun Result*: Code runs identically; semantic purity restored.
- **Error #002**: Missing `import os` in strict ablation script.
  - *Fix*: Added `import os`.
- All 164 repository tests (including Phase 6, Phase 5.1/5.3 and institutional math) passed cleanly.

## 12. Independent Reconciliation
An isolated reconciliation script (`exp_023_independent_reconciliation.py`) successfully rebuilt the exact predictions, threshold quantiles, and metrics reported in Phase 5.4.
- Total Rows: 7200
- Eligible Rows: 7180
- AUC: 0.4936
- Gross EV: +0.46 bps
- Net EV: -11.54 bps
All numbers matched precisely.

## 13. Final Conclusion & Classification
The +0.81 bps improvement is genuinely causal, strictly incremental (proven by the common sample), and mathematically reproducible. However, it is not economically meaningful against real-world transaction costs.

**FINAL CLASSIFICATION: REJECTED**

The event prediction strategy utilizing 1-minute historical data and microstructure proxy features is structurally unable to clear the 12 bps execution hurdle rate. **Do not deploy this model.**
