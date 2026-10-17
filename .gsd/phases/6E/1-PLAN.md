---
phase: 6E
plan: 1
wave: 1
gap_closure: false
---

# Plan 6E.1: Integrated Microstructure Empirical Evaluation Framework

## Objective
Establish an empirical evaluation harness to determine whether the 8 microstructure modules contain reproducible, incremental information beyond simple market baselines:
1. Create research experiment registry with immutable metadata tracking in SQLite.
2. Implement strict chronological train/validation/test splits with purged and embargoed evaluation windows matching forecast horizons (5m, 15m, 30m, 1h) to prevent label overlap leakage.
3. Extract features across all 8 modules (Trade Flow, Duration, OBI, Liquidity Stress, Price Impact, Toxicity, Hasbrouck VAR, VECM) alongside baselines (Naive persistence, EMA, VWAP, simple return, TimesFM close-only).
4. Run group ablations (Baseline vs each module, FLOW_GROUP, LIQUIDITY_GROUP, IMPACT_GROUP, ECONOMETRIC_GROUP, ALL_GROUPS) evaluated on MAE, RMSE, MASE, directional accuracy, rank IC, and pinball loss.
5. Compute Diebold-Mariano test statistics with Benjamini-Hochberg False Discovery Rate (FDR) multiple-testing correction.
6. Test regime robustness (low/normal/high volatility, liquidity, trend) and cross-asset robustness (BTC-USDT, ETH-USDT, SOL-USDT, GOLD/XAU, TradFi).

## Context
Load these files for context:
- control_plane/microstructure_engine.py
- control_plane/db.py
- control_plane/instruments.py
- tests/test_microstructure_phase6a.py
- tests/test_microstructure_phase6b.py
- tests/test_microstructure_phase6c.py
- tests/test_microstructure_phase6d.py

## Tasks

<task type="auto">
  <name>Build Research Experiment Registry Schema and Temporal Splitting Harness with Purge/Embargo</name>
  <files>
    control_plane/db.py
    control_plane/microstructure_evaluation.py
    models/microstructure.py
  </files>
  <action>
    1. In control_plane/db.py:
       - Add additive DDL for research evaluation tables:
         - microstructure_experiments (experiment_id, dataset_id, instrument, venue, asset_class, start_ts, end_ts, sampling_interval_ms, forecast_horizon_s, feature_schema_version, methodology_versions, code_commit, config_hash, created_at)
         - microstructure_experiment_metrics (experiment_id, model_name, feature_group, horizon, metric_name, metric_value, sample_count)
         - microstructure_ablation_results (experiment_id, baseline_name, feature_group, delta_mae, delta_rmse, delta_dir_acc, dm_stat, raw_p_value, adjusted_p_value, is_significant)
         - microstructure_regime_results (experiment_id, regime_name, feature_group, metric_name, metric_value, sample_count)
         - microstructure_cross_asset_results (experiment_id, instrument, asset_class, feature_group, metric_name, metric_value)
       - Add CRUD helper functions in db.py.
    2. In control_plane/microstructure_evaluation.py:
       - Implement TemporalSplitter:
         - Chronological TRAIN (60%), VALIDATION (20%), TEST (20%).
         - Purge window: purge_len = forecast_horizon_steps (removes training points whose forward target overlaps test/val boundaries).
         - Embargo window: embargo_len = ceil(forecast_horizon_steps * 0.5) (removes points immediately following boundary).
         - All normalizers, scaling parameters, and winsorization thresholds fitted STRICTLY on TRAIN.
    AVOID: Random train/test shuffling.
    USE: Strict chronological split with purge + embargo windows.
  </action>
  <verify>
    .venv/Scripts/python.exe -c "from control_plane import db, microstructure_evaluation; print('Evaluation harness imported successfully')"
  </verify>
  <done>
    Experiment tables created in SQLite; temporal splitter with purge and embargo windows operational.
  </done>
</task>

<task type="auto">
  <name>Implement 8-Module Feature Extractors, Baseline Forecasting Suite, and Statistical Comparison Engine</name>
  <files>
    control_plane/microstructure_evaluation.py
    control_plane/microstructure_engine.py
  </files>
  <action>
    1. In control_plane/microstructure_evaluation.py:
       - Feature extractor mapping:
         - FLOW_GROUP: signed_flow, flow_innovation, flow_zscore
         - DURATION_GROUP: duration_delta_t, arrival_intensity, duration_zscore
         - OBI_GROUP: obi_l1, obi_l5, obi_l10
         - LIQUIDITY_GROUP: relative_spread, spread_stress, depth_stress
         - IMPACT_GROUP: kyle_lambda, impact_asymmetry, impact_r2
         - TOXICITY_GROUP: vpin_imbalance, adverse_price_response, flow_intensity
         - HASBROUCK_GROUP: cumulative_impact_H20, variance_share_flow
         - VECM_GROUP: basis_spot_perp, alpha_1, alpha_2, bounded_speed_share
       - Baseline models:
         - Naive Persistence: y_hat_{t+h} = y_t
         - EMA Baseline: exponential moving average of returns
         - VWAP Baseline: volume-weighted average price projection
         - Momentum Baseline: rolling past return
       - Target generation: forward log return ln(P_{t+h} / P_t), absolute return |ln(P_{t+h} / P_t)|, directional sign.
       - Statistical comparison engine:
         - Diebold-Mariano test with Newey-West / HAC standard errors for forecast error differences.
         - Benjamini-Hochberg procedure for False Discovery Rate (FDR) control: p_{(i)} <= (i / m) * Q.
         - Persist both raw_p_value and adjusted_p_value.
  </action>
  <verify>
    .venv/Scripts/python.exe -c "from control_plane.microstructure_evaluation import DieboldMarianoTest, BenjaminiHochberg; print('Statistical comparison engine ready')"
  </verify>
  <done>
    Feature extractors across all 8 modules, baseline models, Diebold-Mariano tests, and Benjamini-Hochberg FDR correction operational.
  </done>
</task>

<task type="auto">
  <name>Execute Multi-Asset, Multi-Regime Ablation Study and Validate on Local & VPS</name>
  <files>
    tests/test_microstructure_phase6e.py
    scratch/run_phase6e_evaluation.py
  </files>
  <action>
    1. Create tests/test_microstructure_phase6e.py:
       - Test 1: Registry table schema persistence and retrieval.
       - Test 2: Chronological train/val/test splitting with purge and embargo window verification.
       - Test 3: Zero lookahead in feature extraction (target timestamps strictly after feature cutoff T).
       - Test 4: Baseline model projections (Naive, EMA, VWAP).
       - Test 5: Diebold-Mariano test calculation and HAC variance.
       - Test 6: Benjamini-Hochberg FDR p-value adjustment.
       - Test 7: Feature group ablation orchestration.
       - Test 8: Regime segmentation (low, normal, high volatility).
       - Test 9: Cross-asset dataset support (BTC-USDT, ETH-USDT, SOL-USDT, GOLD).
       - Test 10: Missing feature handling (no arbitrary zero fills).
       - Test 11: Feature stability (drift and missingness metrics).
       - Test 12: Isolation from trading execution (zero orders, zero slot changes).
    2. Run full local pytest suite:
       .venv/Scripts/python.exe -m pytest tests/test_microstructure_phase6e.py -v
    3. Run scratch/run_phase6e_evaluation.py on VPS to execute empirical study over historical data and live feeds.
    4. Persist ablation and regime matrices into SQLite.
  </action>
  <verify>
    .venv/Scripts/python.exe -m pytest tests/test_microstructure_phase6e.py -v
  </verify>
  <done>
    Full Phase 6E test suite passes (100% green); empirical evaluation study completes and populates SQLite registry on VPS; zero trading execution.
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] Research experiment registry records immutable metadata and config hashes.
- [ ] Chronological train/val/test splits strictly enforce purge and embargo windows.
- [ ] All 8 microstructure modules participate in evaluation framework.
- [ ] Baseline models (Naive, EMA, VWAP) provide rigorous control comparison.
- [ ] Diebold-Mariano tests report HAC-adjusted p-values with Benjamini-Hochberg FDR control.
- [ ] Cross-asset and market regime breakdowns computed without lookahead.
- [ ] Missing features preserve missing state without synthetic zero-fills.
- [ ] Zero orders placed, zero slots reserved or modified.

## Success Criteria
- [ ] All 3 tasks verified passing
- [ ] Must-haves confirmed
- [ ] No regressions across Phase 6A-6D
