# Phase 6.2 Validation Framework

This document outlines the strict validation and statistical methodologies governing feature research in Ophelia, following the Phase 6.1 Audit.

## 1. What Was Structurally Wrong
The Phase 6.1 audit discovered severe structural flaws in how time-series statistics (Newey-West HAC and Stationary Block Bootstrap) were applied to multi-symbol event sets. Specifically, events were concatenated as a flat 1D array across symbols (e.g., all ADA events, then all BNB events) rather than being chronologically interleaved. Even if interleaved, applying a standard uniform-lag estimator to a sparsely, irregularly spaced event series renders the standard errors theoretically invalid, drastically increasing the likelihood of false positives. Furthermore, multiple-testing correction (FDR) suffered from "hyperparameter selection leakage" by correcting only the winning threshold's horizons on OOS data rather than penalizing the entire search space.

## 2. What Was Corrected
The evaluation architecture has been entirely replaced:
- **Calendar-Time Portfolio (CTP):** All sparse, multi-symbol events are now aggregated onto a uniform calendar grid (e.g., 1-hour bins) utilizing an equal-symbol weighting scheme. This perfectly preserves chronological and cross-sectional dependence.
- **ExperimentRunner State Machine:** A strict orchestrator now strictly separates DEV data from OOS data. OOS data cannot be fetched during the DEV phase, and accessing OOS data requires locking a predefined Hypothesis Family.
- **Global FDR Correction:** The `MultipleTestingCorrector` now applies Benjamini-Hochberg FDR across the entire pre-registered Hypothesis Family (including all thresholds and parameters evaluated on DEV), not just the selected winners.
- **Feature Registry:** A centralized machine-readable JSON registry tracks feature versions, parameters, lineage, and their immutable promotion state.

## 3. Permitted Statistical Methods
- **Calendar-Time Portfolio Inference (PRIMARY):** The `CalendarTimePortfolio` class is the mandatory primary inference framework. It groups overlapping events across symbols into uniform time bins (e.g., hourly), computing the Unconditional Expected Return of the strategy.
- **Calendar-Time Newey-West:** Standard Newey-West is permitted *only* on the output of the Calendar-Time Portfolio, using lag parameters $L \ge \lceil h / \text{bin} \rceil$ to account for overlapping horizons.
- **Calendar Block Bootstrap:** Resampling must occur on continuous calendar-time blocks (e.g., 24-hour blocks) of the CTP to perfectly preserve cross-sectional correlation and regime persistence.
- **Panel-HAC (SECONDARY):** Estimators like Driscoll-Kraay are permitted only as a secondary robustness check, provided the underlying panel structure actually satisfies the estimator's assumptions (e.g., dense $T$, large $N$).

## 4. Prohibited Methods
- **1D Array Time-Series Statistics:** Running standard Newey-West or Stationary Block Bootstrap on a concatenated 1D list of sparse events is strictly prohibited.
- **Silent Weighting:** Aggregating portfolios without explicitly documenting whether events are equal-weighted, event-weighted, or equal-symbol weighted is prohibited.
- **Local FDR Correction:** Applying FDR only to the horizons of the "best" parameter configuration found in the DEV set is prohibited.

## 5. Promotion State Machine
A feature earns promotion by passing sequential, mandatory gates implemented via the `FeatureRegistry` and `ExperimentRunner`:

1. `CANDIDATE`: Theoretical definition.
2. `LEAKAGE_PASS`: Audit confirms no look-ahead.
3. `DEV_PASS`: Demonstrates edge on Dev data.
4. `OOS_PASS`: Survives holdout evaluation on OOS data.
5. `COST_PASS`: Net expectancy is significantly positive after realistic transaction costs (maker/taker fees + slippage + funding).
6. `STABILITY_PASS`: Win Rate, Profit Factor, MAE, and MFE remain stable across market regimes.
7. `MULTIPLE_TESTING_PASS`: Survives global FDR correction across the entire Hypothesis Family.
8. `PRODUCTION_CANDIDATE`: Verified ready for deployment.

## 6. Permanent Rejection
Failure at any mandatory gate (e.g., failing to demonstrate positive Net Expectancy or failing FDR correction) results in an immediate transition to `REJECTED / REMOVE`. 

**A rejected feature formulation is immutable.** It cannot be "rescued" by manual override, changing the threshold post-hoc, or manipulating the data. If a genuinely different formulation is conceptualized later, a new `feature_id` and a new experiment must be initialized from scratch.

*Example:* `FLOW_PRICE_DIVERGENCE` is permanently locked as `REJECTED`.
