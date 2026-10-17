---
phase: 12
plan: 1
wave: 1
---

# Plan 12.1: Fresh-Period Incremental TimesFM Validation

## Objective
Determine whether genuine Google TimesFM 3.0 forecast-distribution information adds incremental value (target reachability, downside risk gating, and T+15m reforecast management) on top of the frozen repaired deterministic strategy (D4H: Variant D + 4H Trend Alignment) on a completely fresh, unexamined 122-day chronological dataset (2023-12-01 to 2024-03-31) across BTCUSDT, ETHUSDT, and SOLUSDT. Apply Benjamini-Hochberg FDR multiple-testing control, evaluate friction sensitivity (0 to 14 bps), and verify parity on Local and VPS.

## Context
- .gsd/SPEC.md
- .gsd/ROADMAP.md
- .gemini/GEMINI.md
- PROJECT_RULES.md
- docs/PHASE_11_5_HTF_REGIME_TRADE_MANAGEMENT_REPORT.md
- control_plane/phase12_timesfm_engine.py
- scripts/prepare_phase12_dataset.py
- scripts/run_phase12_incremental_timesfm.py

## Tasks

<task type="auto">
  <name>Task 1: Ingest and Validate Completely Fresh 122-Day Dataset</name>
  <files>scripts/prepare_phase12_dataset.py, data/processed/phase12_fresh_universe_1m.parquet</files>
  <action>
    - Build `scripts/prepare_phase12_dataset.py` to ingest 1-minute klines for Dec 2023, Jan 2024, Feb 2024, and Mar 2024 across BTCUSDT, ETHUSDT, and SOLUSDT.
    - Consolidate 122 continuous calendar days (2023-12-01 to 2024-03-31), completely disjoint from the Oct-Nov 2023 test dataset.
    - Validate dataset integrity: exactly 175,680 bars per symbol (527,040 total), zero missing bars, zero timestamp reversals.
  </action>
  <verify>python -c "import pandas as pd; df=pd.read_parquet('data/processed/phase12_fresh_universe_1m.parquet'); assert len(df)==527040; print('Dataset verified: 527,040 rows')"</verify>
  <done>Fresh dataset successfully created and forensically validated.</done>
</task>

<task type="auto">
  <name>Task 2: Build Causal Incremental TimesFM Engine with Frozen D4H Specification</name>
  <files>control_plane/phase12_timesfm_engine.py</files>
  <action>
    - Implement `Phase12IncrementalTimesFMEngine` in `control_plane/phase12_timesfm_engine.py`.
    - Enforce frozen spec hash `cf8267d78105b14f`:
      - Variant D: Displacement $\ge 1.20$ ATR, Rejection Body Ratio $\ge 0.45$, RVOL $\ge 1.00$.
      - 4H Trend: 4H EMA20 vs EMA50 with 0.1% buffer, causally resampled with zero lookahead.
    - Implement progression cohorts:
      - A: Raw Baseline Retest
      - B: Variant D
      - C: D4H
      - D: D4H + TimesFM Reachability ($q_{90} \ge \text{TP1}$ for Longs, $q_{10} \le \text{TP1}$ for Shorts)
      - E: D + TimesFM Downside Gate (Reject if $q_{10} \le \text{SL}$ for Longs, $q_{90} \ge \text{SL}$ for Shorts)
      - F: E + T+15m Reforecast Management (Dynamic early exit if updated median drifts adversely)
    - Enforce strict chronological splits: Train (40d), Embargo 1 (24h), Val (36d), Embargo 2 (24h), Test (44d).
  </action>
  <verify>python -c "from control_plane.phase12_timesfm_engine import Phase12IncrementalTimesFMEngine; print('Engine import successful')"</verify>
  <done>Engine built with strict causality, frozen spec hash, and all 6 progression cohorts.</done>
</task>

<task type="auto">
  <name>Task 3: Execute Incremental Validation and Multiple-Testing Control</name>
  <files>scripts/run_phase12_incremental_timesfm.py, data/phase12_incremental_timesfm_results.json</files>
  <action>
    - Run full neural validation across all 2,207 candidates.
    - Apply Benjamini-Hochberg False Discovery Rate (FDR) control at $\alpha = 0.05$ across 4 pre-registered hypotheses:
      - H1: Target Reachability Improves Net Mean R
      - H2: Downside Distribution Informs MAE/SL
      - H3: Distribution Differentiates Feasible Targets
      - H4: T+15m Reforecast Improves Management
    - Compute cluster-robust confidence intervals ($N_{\text{eff}} = 113.5$).
    - Compute friction sensitivity sweeps (0, 5, 9, 14 bps) and cross-asset/regime breakdowns.
    - Output complete audit JSON to `data/phase12_incremental_timesfm_results.json`.
  </action>
  <verify>python -c "import json; res=json.load(open('data/phase12_incremental_timesfm_results.json')); assert res['spec_hash']=='cf8267d78105b14f'; print('Audit JSON verified')"</verify>
  <done>All empirical results computed, FDR registered, and verified.</done>
</task>

<task type="auto">
  <name>Task 4: Write Unit Test Suite and Authoritative Report</name>
  <files>tests/test_phase12_incremental_timesfm.py, docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md</files>
  <action>
    - Build test suite `tests/test_phase12_incremental_timesfm.py` testing:
      1. Safety invariants (`TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`)
      2. Fresh data boundaries and zero-overlap audit
      3. Frozen D4H specification hash
      4. Target reachability canonical geometry
      5. Causal forward trajectory & same-bar SL precedence
      6. Future corruption invariance
      7. Benjamini-Hochberg FDR logic
    - Author full 23-section report in `docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md`.
  </action>
  <verify>pytest tests/test_phase12_incremental_timesfm.py -v</verify>
  <done>All 7 unit tests pass 100%, and authoritative report is fully drafted.</done>
</task>

<task type="auto">
  <name>Task 5: Deploy & Synchronize to VPS</name>
  <files>/opt/ophelia/control_plane/phase12_timesfm_engine.py, /opt/ophelia/tests/test_phase12_incremental_timesfm.py</files>
  <action>
    - Sync all Phase 12 engine, scripts, data, tests, and documentation to `/opt/ophelia/` on VPS (`15.235.193.47`).
    - Run pytest on VPS to ensure 100% test pass parity.
  </action>
  <verify>ssh ubuntu@15.235.193.47 "/opt/ophelia/.venv/bin/python -m pytest /opt/ophelia/tests/test_phase12_incremental_timesfm.py"</verify>
  <done>Local and VPS in 100% parity with zero test failures.</done>
</task>
