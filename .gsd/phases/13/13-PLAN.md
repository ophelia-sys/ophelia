---
phase: 13
plan: 1
wave: 1
---

# Plan 13.1: Alpha Discovery Reset & Structural Stop-Room Research

## Objective
Reset the research methodology from micro-tuning 5m retest filters to broad, unbiased alpha discovery and empirical structural stop-room research. Determine where Binance market microstructure contains repeatable forward relationships across multiple horizons (1m to 120m), establish the empirical MAE/MFE distribution of genuine opportunities, conduct the "Stop Hit -> Thesis Resumption" study, evaluate multi-timeframe structural invalidation (5m vs 15m vs 1H), and audit economic survivability under verified BingX notional execution costs.

## Context
- .gsd/SPEC.md
- .gsd/ROADMAP.md
- .gemini/GEMINI.md
- PROJECT_RULES.md
- docs/PHASE_12_FRICTION_ACCOUNTING_AUDIT.md
- docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md
- data/processed/phase12_fresh_universe_1m.parquet
- data/processed/binance_um_universe_1m_v2.parquet

## Tasks

<task type="auto">
  <name>Task 1: Build Broad Event Universe & Multi-Horizon Forward Engine</name>
  <files>control_plane/phase13_discovery_engine.py</files>
  <action>
    - Build `control_plane/phase13_discovery_engine.py` defining broad causal event families:
      1. Momentum Displacement ($\ge 1.5$ ATR)
      2. RVOL Expansion (RVOL $\ge 2.0$)
      3. CVD / Order Flow Acceleration & Signed Volume Imbalance
      4. VWAP Deviation ($\ge 1.5\sigma$) & Reclaim / Rejection
      5. Liquidity Sweep / Swing Failure Pattern (15m/1H swing breach + reversal)
      6. Volume Profile Value-Area Boundary Interaction
      7. HTF 1H/4H Trend & Volatility Interactions
    - Track causal forward outcomes across 8 horizons: 1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m.
    - Measure direction, absolute return, MFE, MAE, time to target, and volatility expansion.
    - Enforce chronological Train / Validation / Test partitions with 24h purge embargo.
  </action>
  <verify>python -c "from control_plane.phase13_discovery_engine import Phase13DiscoveryEngine; print('Engine imported successfully')"</verify>
  <done>Discovery engine constructed with broad event classes and 8 forward horizons.</done>
</task>

<task type="auto">
  <name>Task 2: Implement Empirical Structural Stop-Room & Thesis-Resumption Architecture</name>
  <files>control_plane/phase13_discovery_engine.py</files>
  <action>
    - Implement multi-timeframe structural invalidation models:
      1. 5m local swing
      2. 15m swing structure
      3. 1H macro swing
      4. ATR volatility envelope ($1.5 \times \text{ATR}_{14}$)
    - Implement the "Stop Hit -> Thesis Resumption" classifier:
      - Class A: SL hit and thesis never resumes
      - Class B: SL hit and price later reaches original TP (Premature stop-out / suffocated trade)
      - Class C: SL not hit and TP reached
      - Class D: SL not hit and no meaningful move
      - Class E: Neither SL nor TP, then structural invalidation
      - Class F: Ambiguous / horizon expired
    - Measure MAE distribution of eventual winners vs eventual losers.
    - Map stop-distance regimes (0.2-0.3%, 0.3-0.5%, 0.5-0.75%, 0.75-1.0%, 1.0-1.5%, >1.5%) to net expectancy.
  </action>
  <verify>python -c "from control_plane.phase13_discovery_engine import classify_thesis_resumption; print('Resumption classifier verified')"</verify>
  <done>Structural stop-room and thesis-resumption mechanics fully implemented.</done>
</task>

<task type="auto">
  <name>Task 3: Execute Full Alpha Discovery & Stop-Room Runner</name>
  <files>scripts/run_phase13_alpha_discovery.py, data/phase13_stop_room.json, data/phase13_results.json</files>
  <action>
    - Build `scripts/run_phase13_alpha_discovery.py` and run full discovery across BTCUSDT, ETHUSDT, SOLUSDT.
    - Recompute all events under 4 verified economic scenarios (0 bps, 7 bps fee-only, 9.1 bps fee+slip, 12.1 bps taker, 14.1 bps conservative).
    - Evaluate 4 core questions separately: Directional Edge, Magnitude Edge, Timing Edge, Path/MAE Edge.
    - Apply Benjamini-Hochberg FDR multiple-testing control ($\alpha=0.05$) and cluster-robust bootstrap CIs.
    - Compare against simple baselines (Persistence, VWAP, Momentum, Mean Reversion).
    - Output `data/phase13_events.parquet`, `data/phase13_forward_outcomes.parquet`, `data/phase13_stop_room.json`, `data/phase13_results.json`.
  </action>
  <verify>python -c "import json; r=json.load(open('data/phase13_results.json')); print('Results verified, events count:', r['total_events'])"</verify>
  <done>Discovery run complete, all machine-readable artifacts generated.</done>
</task>

<task type="auto">
  <name>Task 4: Write Comprehensive Unit Tests</name>
  <files>tests/test_phase13_discovery.py</files>
  <action>
    - Create `tests/test_phase13_discovery.py` covering:
      1. Safety invariants (`TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`)
      2. Event extraction causality (no future bar contamination)
      3. Multi-horizon MAE/MFE calculation monotonicity
      4. Multi-timeframe stop hierarchy (5m vs 15m vs 1H)
      5. Thesis-resumption classification logic (A, B, C, D, E, F)
      6. Verified BingX notional friction accounting in R
      7. Benjamini-Hochberg FDR ranking and critical value math
  </action>
  <verify>pytest tests/test_phase13_discovery.py -v</verify>
  <done>All unit tests passing 100%.</done>
</task>

<task type="auto">
  <name>Task 5: Author All 5 Required Phase 13 Reports</name>
  <files>docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md, docs/PHASE_13_STOP_ROOM_RESEARCH.md, docs/PHASE_13_EVENT_UNIVERSE_REPORT.md, docs/PHASE_13_STATISTICAL_VALIDATION.md, docs/PHASE_13_ECONOMIC_VALIDATION.md</files>
  <action>
    - Author all 5 authoritative reports answering all 19 mandated questions in prompt Section 30:
      1. `PHASE_13_ALPHA_DISCOVERY_REPORT.md` (Overarching findings, executive summary, questions 1-19 answered)
      2. `PHASE_13_STOP_ROOM_RESEARCH.md` (MAE of winners vs losers, thesis resumption, minimum breathing room)
      3. `PHASE_13_EVENT_UNIVERSE_REPORT.md` (Event definitions, frequencies, baseline comparisons)
      4. `PHASE_13_STATISTICAL_VALIDATION.md` (FDR control, chronological OOS stability, cluster CIs)
      5. `PHASE_13_ECONOMIC_VALIDATION.md` (4 friction scenarios, notional fee vs stop-distance economics)
  </action>
  <verify>test -f docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md</verify>
  <done>All 5 comprehensive reports authored and linked.</done>
</task>

<task type="auto">
  <name>Task 6: Deploy & Verify Parity on VPS</name>
  <files>/opt/ophelia/control_plane/phase13_discovery_engine.py, /opt/ophelia/tests/test_phase13_discovery.py</files>
  <action>
    - Transfer all Phase 13 engine, scripts, data, tests, and documentation to `/opt/ophelia/` on VPS (`15.235.193.47`).
    - Execute remote unit tests to confirm 100% pass parity on Ubuntu VPS.
  </action>
  <verify>ssh ubuntu@15.235.193.47 "/opt/ophelia/.venv/bin/python -m unittest tests/test_phase13_discovery.py"</verify>
  <done>Local and VPS in 100% parity with zero test failures.</done>
</task>
