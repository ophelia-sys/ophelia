# Phase 6 Real Empirical Validation Implementation Plan

This plan repairs and executes the complete Phase 6 empirical validation pipeline, transitioning it from a mechanical validation to a rigorous statistical hypothesis test over out-of-sample (OOS) real data.

## Proposed Changes

### 1. `research/phase6/validation.py`
- Enhance `WalkForwardValidator` to emit precise metadata (train_start, train_end, purge_start, purge_end, embargo_start, embargo_end, test_start, test_end) for reporting.
- Ensure the purge window exactly matches the max forward horizon (60 minutes).

### 2. `research/phase6/events.py`
- Modify `_cluster_events` to keep an exact count of `FVG_CONFIRMATION`, `POOL_CONFIRMATION`, and `LIQUIDITY_SWEEP` events.
- Properly split events into `primary_events` (start of a cluster) and `non_primary_events`.
- Update the pipeline to perform primary statistical analysis ONLY on `primary_event == True`.

### 3. `research/phase6/power.py`
- Discard the invalid `cluster_count >= 350` logic.
- Implement simulation-based power analysis: given the available effective sample size, target power (80%), and alpha (0.05), simulate minimum detectable effect (MDE) using bootstrap variances of the baseline returns.

### 4. `research/phase6/statistics.py`
- Add Benjamini-Hochberg FDR (`fdr_bh`) function.
- Add OOS excess return calculation.
- Add block bootstrap confidence interval calculation for excess returns.
- Add effect size (Cohen's d equivalent for excess returns).

### 5. `research/phase6/costs.py`
- Add `BINGX_SIMULATION` scenario.
- Build an evaluator that takes a set of events and applies the cost model to calculate gross return, fees, slippage, and net return (assuming entry at the event timestamp and exit at the end of the horizon).

### 6. `research/phase6/pipeline.py`
- Orchestrate the genuine Walk-Forward Validation loop:
  1. Split folds (Train/Purge/Embargo/Test).
  2. Baseline Evaluation on Test Set.
  3. Evaluate events on the Test Set.
  4. Perform block-bootstrap inference on excess returns.
  5. Apply Benjamini-Hochberg FDR across all Feature x Horizon tests.
  6. Apply cost scenarios to test set events.

### 7. `scripts/run_real_validation.py`
- Update script to capture all this data.
- Generate the final `PHASE6_HISTORICAL_VALIDATION_RESULTS.md` strictly according to the required schema, containing exact numerical outcomes and classifying each feature.

### 8. `tests/`
- Add new unit tests to cover `fdr_bh`, chronological purge/embargo logic, primary event filtering, and block bootstrap logic.

## Verification Plan
1. **Automated Tests:** Execute `py -3.11 -m pytest tests/ -q` ensuring 130+ tests pass with no regressions.
2. **Isolation Check:** Run `grep` to ensure zero live-execution leakage.
3. **Execution on Real Data:** Execute `py -3.11 scripts/run_real_validation.py` to process the 129,600 rows and generate the final markdown report with purely statistical OOS outcomes.

## User Review Required
Does this statistical approach accurately reflect your expectations for Train/Purge/Embargo/Test evaluation and feature-versus-baseline comparisons?
