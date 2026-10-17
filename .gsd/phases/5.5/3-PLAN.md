---
phase: 5.5
plan: 3
wave: 3
depends_on: [5.5.2]
---

# Plan 5.5.3: Redundant Work Elimination & CPU Isolation Strategies

## Objective
Detect and eliminate redundant computations in scheduler/features/persistence, and evaluate CPU isolation strategies (shared process vs dedicated worker vs process priority/affinity) ensuring trading-critical path headroom.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [PROJECT_RULES.md](file:///c:/Users/dopa.mine/Desktop/ophelia/PROJECT_RULES.md)
- [control_plane/forecast_service.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/forecast_service.py)
- [control_plane/core.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/core.py)

## Tasks

<task type="auto">
  <name>Redundant Work Audit & Deduplication Verification</name>
  <files>scratch/vps_phase55_redundancy.py</files>
  <action>
    Inspect the live scheduler, feature builder, and database for redundant work:
    - Verify duplicate forecast prevention per (instrument, timeframe, forecast_ts)
    - Verify cache hits prevent redundant PyTorch model invocations on unchanged candle history
    - Check for repeated SQLite reads of identical candle segments
    - Audit health-check frequency to ensure no continuous heavyweight dummy inference runs
    - Add optimization instrumentation where necessary to prevent re-execution of identical states.
  </action>
  <verify>python scratch/vps_phase55_redundancy.py</verify>
  <done>Zero duplicate forecasts generated for identical timestamps, cache hit eliminates forward pass, and redundant DB queries verified eliminated.</done>
</task>

<task type="auto">
  <name>CPU Isolation & Resource Allocation Evaluation</name>
  <files>scratch/vps_phase55_isolation.py</files>
  <action>
    Evaluate and benchmark CPU isolation approaches on VPS:
    - Policy A: Current shared process in control plane
    - Policy B: Dedicated forecast worker process with IPC/SQLite boundary
    - Policy C: Process priority / CPU affinity reserving at least 1 vCPU equivalent for core trading operations
    Measure the impact of each policy on core trading latency and forecast duration.
  </action>
  <verify>python scratch/vps_phase55_isolation.py</verify>
  <done>Isolation benchmark demonstrates measurable impact on trading headroom and identifies the optimal isolation policy.</done>
</task>

## Success Criteria
- [ ] Redundant inference and repeated calculations eliminated
- [ ] CPU isolation policy benchmarked ensuring at least 1 vCPU headroom for trading operations
