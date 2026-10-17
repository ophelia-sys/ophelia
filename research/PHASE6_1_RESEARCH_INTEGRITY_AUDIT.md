# Phase 6.1 Research Integrity Audit

This document formally audits the methodology of the Phase 6.1 Gate 1 empirical validation (`exp_037_039_divergence_search.py`), identifying methodological defects and validating whether the final `REMOVE` verdict holds.

## Audit Checklist

| Item | Description | Status | Findings |
| :--- | :--- | :--- | :--- |
| 1 | No look-ahead leakage in `Z_R` | PASS | `Z_R` at time `t` is accessed strictly at index `i` corresponding to the event confirmation timestamp `t`. |
| 2 | No look-ahead leakage in `Z_DeltaOI` | PASS | Same as above. `Z_DeltaOI` is causally aligned. |
| 3 | Correct chronological Dev/OOS separation | PASS | `WalkForwardValidator` generated 5 chronological folds. Folds 1-3 were mapped to Dev; Folds 4-5 to OOS. |
| 4 | Tau selection occurred exclusively on Dev data | PASS | Hyperparameter search (`tau` grid) was evaluated exclusively via `dev_folds = folds_meta[:3]`. |
| 5 | OOS data untouched during hyperparameter selection | PASS | OOS data was not evaluated until `best_tau` was explicitly locked. |
| 6 | Correct transaction-cost application | PASS | 12.0 bps round-trip transaction costs were applied in the economic expectancy calculation. |
| 7 | Correct event timestamp alignment | PASS | Events were correctly filtered by `test_start <= e["timestamp"] <= test_end`. |
| 8 | Correct handling of overlapping events & sample size | FAIL | Events were concatenated sequentially by symbol (all ADA, then BNB...). Overlapping events across symbols were not temporally interleaved, destroying cross-sectional temporal alignment. |
| 9 | Correct Newey-West/HAC assumptions | FAIL | The script applied `newey_west_se()` to sparse, irregularly spaced event returns concatenated across symbols. Newey-West assumes uniform temporal spacing. Applying lag-based autocorrelation on an array where "lag 1" could mean a 1-minute gap or a 1-month gap (or a jump between ADA and BNB) renders the HAC standard error theoretically invalid. |
| 10 | Correct block-bootstrap methodology | FAIL | `stationary_block_bootstrap` resampled consecutive indices in the array. Because the array is irregularly spaced and spans multiple symbols, a block of 10 events mixes time periods and symbols entirely arbitrarily, failing to preserve true market regime autocorrelation. |
| 11 | Correct FDR/multiple-testing correction | FAIL | `fdr_bh` was applied per-feature (6 horizons) rather than globally across the hypothesis family (all evaluated event types and horizons). This under-penalized the p-values. |
| 12 | No silent exclusion of failed thresholds | PASS | All `tau` thresholds and setups were explicitly printed in the Dev output; all horizons printed in OOS output. |
| 13 | No accidental contamination | PASS | Canonical dataset was read-only. No transformations were leaked back into the global dataframe. |
| 14 | Canonical dataset hash unchanged | PASS | SHA-256 confirmed as `D2E839EDECFAE88B798993CFF9545FA626071EFCB722F266FBE15E0BEA3E20B5`. |

## Methodological Defect Analysis

The script contains severe structural flaws in how it applies time-series statistics (Newey-West HAC and Stationary Block Bootstrap) to sparse, cross-sectional event arrays. 

In `exp_037_039_divergence_search.py`:
```python
f_returns = [e.get(f"R_{h}") for e in subset_events]
f_arr = np.array(f_returns)
# ...
hac_se = newey_west_se(x, y)
boot_samples = stationary_block_bootstrap(y, block_size=10, num_bootstraps=1000)
```
`subset_events` is populated by iterating over folds, but the underlying events were appended symbol-by-symbol during generation. Thus, `f_arr` is an irregular, non-chronological array jumping between assets and massive gaps in time. Applying standard uniform-lag time-series estimators to this array is statistically invalid. A proper implementation requires either a Panel-HAC estimator or aggregating returns to a uniform chronological grid (e.g., evaluating the portfolio return at every minute).

## Final Conclusion

**Does the Phase 6.1 `REMOVE` verdict remain valid?**
**YES.**

The identified statistical defects (Items 8-11) generally result in standard errors that are *too small*, because they fail to properly penalize the clustered correlation of overlapping events. If the standard errors are artificially small, it becomes *easier* to achieve a false positive (p < 0.05). 

Despite this flawed leniency, the Flow-Price Divergence feature *still* failed to produce any statistically significant p-values, and the raw economic expectancy was severely negative out-of-sample (-9.19 bps). Furthermore, the sample size constraints (`N=1` for FVG, `N=0` for Sweep) are absolute and unaffected by HAC methodology.

A statistically corrected test would only widen the standard errors and make the feature fail even harder.

**Decision:** The Flow-Price Divergence feature is officially locked as `REMOVE`. No further experiments or alternative thresholds will be evaluated to rescue it.
