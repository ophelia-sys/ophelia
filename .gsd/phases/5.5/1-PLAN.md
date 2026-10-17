---
phase: 5.5
plan: 1
wave: 1
---

# Plan 5.5.1: Baseline System Telemetry & Forecast Cycle Profiling

## Objective
Establish an empirical VPS resource baseline (CPU, memory, swap I/O, latencies) and profile a complete TimesFM forecast cycle down to its 9 core sub-components (features, DB, cache, PyTorch inference, quantiles, serialization, persistence, scheduler).

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [PROJECT_RULES.md](file:///c:/Users/dopa.mine/Desktop/ophelia/PROJECT_RULES.md)
- [OPHELIA_TIMESFM.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_TIMESFM.md)
- [control_plane/forecast_service.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/forecast_service.py)

## Tasks

<task type="auto">
  <name>VPS Baseline Telemetry Measurement</name>
  <files>scratch/vps_phase55_baseline.py</files>
  <action>
    Create and execute an empirical VPS telemetry script that measures:
    - Host CPU utilization and per-core breakdown
    - Per-process and per-thread CPU consumption (ophelia-control, ophelia-api, llama-server)
    - Load averages (1m, 5m, 15m) and context switches
    - RAM breakdown (total, used, free, buff/cache, available, TimesFM RSS, API RSS)
    - Swap usage and true swap I/O rate (vmstat 1 10 sampling si/so to prove thrashing vs passive swap)
    - Core service latencies (API /api/health, automation worker, position manager, reconciliation)
    - TimesFM steady-state inference and scheduler queue depth
    Avoid guessing or using fake data; gather directly from the live VPS environment.
  </action>
  <verify>python scratch/vps_phase55_baseline.py</verify>
  <done>Script returns structured JSON telemetry capturing all Section 1 baseline metrics with non-zero samples and true swap I/O rates.</done>
</task>

<task type="auto">
  <name>Forecast Cycle Sub-Component Breakdown Profiling</name>
  <files>scratch/vps_phase55_profiler.py</files>
  <action>
    Profile one complete TimesFM forecast cycle on the VPS across all 9 sub-components:
    A. Feature construction (OHLCV processing, covariates)
    B. Data retrieval (SQLite candle querying)
    C. Cache lookup (5-part key check)
    D. Model preparation (tensor allocation, numpy conversion)
    E. PyTorch inference (TimesFM forecaster forward pass)
    F. Quantile processing (q10, q25, q50, q75, q90 tensor slicing)
    G. Serialization (JSON formatting, dictionary transformation)
    H. Persistence (SQLite model_forecasts insertion)
    I. Scheduler overhead (loop latency, lock acquisition)
    Record wall-clock time and percentage contribution of each component.
  </action>
  <verify>python scratch/vps_phase55_profiler.py</verify>
  <done>Cycle profiling output identifies exact microsecond/millisecond timing and percentage share of each sub-component.</done>
</task>

## Success Criteria
- [ ] Baseline telemetry measured on live VPS with true swap I/O rate
- [ ] Sub-component profile isolates PyTorch inference vs feature/DB overhead
