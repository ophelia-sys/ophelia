---
phase: 6F
plan: 1
wave: 1
gap_closure: false
---

# Plan 6F.1: TimesFM Feature-Consumption Adapter & Incremental Value Research

## Objective
Design and execute strictly causal, shadow-only TimesFM feature-consumption experiments to determine whether conditioning on microstructure features provides incremental predictive value over the identical close-only baseline:
1. Leverage the verified native `past_only_covariates` interface of `timesfm.TimesFM3Forecaster` via a clean `TimesFMCovariateAdapter`.
2. Construct causal, train-normalized covariate channels across conditions:
   - Condition A: `TIMESFM_CLOSE_ONLY` (Exact Baseline Control)
   - Condition B: `TIMESFM + FLOW_DURATION`
   - Condition C: `TIMESFM + ORDERBOOK_LIQUIDITY`
   - Condition D: `TIMESFM + IMPACT_TOXICITY`
   - Condition E: `TIMESFM + HASBROUCK_VECM`
   - Condition F: `TIMESFM + ALL_MICROSTRUCTURE`
3. Execute walk-forward chronological evaluation across multiple horizons (5m, 15m, 30m, 1h) and assets (BTC-USDT, ETH-USDT, SOL-USDT).
4. Measure incremental predictive value: Delta MAE, Delta RMSE, directional accuracy gain, Diebold-Mariano test with Benjamini-Hochberg FDR-adjusted p-values, and pinball loss across quantiles ($q_{10}-q_{90}$).
5. Profile resource overhead (inference latency, CPU utilization, peak RAM, feature construction time) to preserve Phase 5.5 optimization.
6. Verify failure isolation: a failure in TimesFM leaves microstructure running; a failure in microstructure leaves TimesFM running; neither affects deterministic trading/risk.

## Context
Load these files for context:
- control_plane/forecast_service.py
- control_plane/microstructure_engine.py
- control_plane/microstructure_evaluation.py
- control_plane/db.py

## Tasks

<task type="auto">
  <name>Build TimesFMCovariateAdapter with Causal Alignment and Train-Only Normalization</name>
  <files>
    control_plane/timesfm_adapter.py
    control_plane/forecast_service.py
    control_plane/db.py
  </files>
  <action>
    1. Create control_plane/timesfm_adapter.py:
       - Implement TimesFMCovariateAdapter wrapping TimesFMProvider.
       - Support past_only_covariates: np.ndarray of shape (num_channels, context_length).
       - Enforce strict causality: for forecast cutoff T, every feature point must satisfy feature_event_timestamp <= T and feature_received_timestamp <= T.
       - For price impact: use only backward historical impact estimated through T (never future return used for evaluation).
       - Feature normalizers (z-score mu/sigma, winsorization limits) fit STRICTLY on TRAIN fold, applied forward without lookahead.
       - Missing feature semantics: carry quality mask; if a channel is unavailable, do not inject arbitrary zeros; use channel masking or fallback to close-only baseline with quality flag.
    2. In control_plane/db.py:
       - Add additive DDL for TimesFM feature consumption tables:
         - timesfm_microstructure_experiments (experiment_id, condition_name, instrument, timeframe, horizon, feature_channels, sample_count, mae_baseline, mae_augmented, delta_mae, rmse_baseline, rmse_augmented, delta_rmse, dir_acc_baseline, dir_acc_augmented, delta_dir_acc, dm_stat, raw_p_value, adjusted_p_value, status, latency_baseline_ms, latency_augmented_ms, created_at)
  </action>
  <verify>
    .venv/Scripts/python.exe -c "from control_plane import timesfm_adapter; print('TimesFMCovariateAdapter imported successfully')"
  </verify>
  <done>
    Adapter constructed; causal alignment and train-only normalization enforced; experiment persistence table ready.
  </done>
</task>

<task type="auto">
  <name>Execute Controlled Walk-Forward Conditions A through F and Measure Incremental Value</name>
  <files>
    control_plane/timesfm_adapter.py
    control_plane/microstructure_evaluation.py
    scratch/run_timesfm_microstructure_experiments.py
  </files>
  <action>
    1. Create scratch/run_timesfm_microstructure_experiments.py:
       - For each asset (BTC-USDT, ETH-USDT, SOL-USDT) and horizon (5m, 15m, 30m, 1h):
         - Run Condition A: TIMESFM_CLOSE_ONLY (baseline)
         - Run Condition B: TIMESFM + FLOW_DURATION (signed_flow, arrival_intensity)
         - Run Condition C: TIMESFM + ORDERBOOK_LIQUIDITY (obi_l5, relative_spread)
         - Run Condition D: TIMESFM + IMPACT_TOXICITY (kyle_lambda, vpin_imbalance)
         - Run Condition E: TIMESFM + HASBROUCK_VECM (cumulative_impact_H20, basis_spot_perp)
         - Run Condition F: TIMESFM + ALL_MICROSTRUCTURE (all 8 feature channels)
       - Measure forecast accuracy on identical test cutoffs:
         MAE, RMSE, directional accuracy, pinball loss ($q_{10}, q_{50}, q_{90}$), quantile spread.
       - Compute statistical differences:
         Delta MAE = MAE_augmented - MAE_baseline
         Diebold-Mariano test statistic
         Benjamini-Hochberg FDR adjusted p-value
       - Measure performance overhead:
         feature construction time, model inference time, peak memory usage, CPU load.
       - Persist results to timesfm_microstructure_experiments in SQLite.
  </action>
  <verify>
    .venv/Scripts/python.exe scratch/run_timesfm_microstructure_experiments.py --dry-run
  </verify>
  <done>
    Walk-forward experiments A-F executed; deltas, DM stats, and FDR p-values recorded; resource metrics captured.
  </done>
</task>

<task type="auto">
  <name>Build Phase 6F Test Suite, Verify Failure Isolation, and Deploy to VPS</name>
  <files>
    tests/test_timesfm_phase6f.py
    scratch/deploy_phase6f_vps.py
  </files>
  <action>
    1. Create tests/test_timesfm_phase6f.py:
       - Test 1: Adapter correctly formats past_only_covariates shape (C, L).
       - Test 2: Zero lookahead in covariate alignment (timestamps <= T).
       - Test 3: Normalization leakage test (fitted only on TRAIN fold).
       - Test 4: Missing feature handling (no silent zero substitution).
       - Test 5: Exact reproduction of TimesFM close-only baseline when covariates are omitted.
       - Test 6: Quantile monotonicity under covariate conditioning (q10 <= q50 <= q90).
       - Test 7: Failure isolation: simulated microstructure engine failure leaves TimesFM inference healthy.
       - Test 8: Failure isolation: simulated TimesFM failure leaves microstructure engine healthy.
       - Test 9: Execution barrier test: running TimesFM + microstructure experiments never places orders, mutates slots, or alters risk.
    2. Run local pytest:
       .venv/Scripts/python.exe -m pytest tests/test_timesfm_phase6f.py -v
    3. Deploy to VPS (15.235.193.47), execute full experiment suite on real historical BingX data, and record performance metrics.
  </action>
  <verify>
    .venv/Scripts/python.exe -m pytest tests/test_timesfm_phase6f.py -v
  </verify>
  <done>
    Phase 6F test suite passing (100% green); failure isolation verified; VPS experiments complete; zero trading authority.
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] TimesFMCovariateAdapter utilizes verified native past_only_covariates interface.
- [ ] Causal feature alignment strictly verified (timestamps <= T; no future returns used in inputs).
- [ ] Normalization parameters fitted exclusively on TRAIN splits.
- [ ] Controlled experiments A through F run on identical cutoffs against TIMESFM_CLOSE_ONLY.
- [ ] Incremental value evaluated with Diebold-Mariano tests and Benjamini-Hochberg FDR correction.
- [ ] Latency, CPU, and RAM overhead measured; Phase 5.5 optimization preserved.
- [ ] Mutual failure isolation between TimesFM and Microstructure verified.
- [ ] Zero orders placed, zero slots mutated, zero risk changes.

## Success Criteria
- [ ] All 3 tasks verified passing
- [ ] Must-haves confirmed
- [ ] Zero regressions across Phase 1-6
