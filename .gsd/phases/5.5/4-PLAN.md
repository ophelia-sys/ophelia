---
phase: 5.5
plan: 4
wave: 4
depends_on: [5.5.3]
---

# Plan 5.5.4: Critical Trading Path Verification, Long Shadow Workload & Gate Sign-Off

## Objective
Verify critical trading services (API, automation, position manager, reconciliation) during peak TimesFM CPU load, execute an extended multi-cycle shadow run, verify the full regression test suite, and generate the final Phase 5.5 Resource Gate report.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [PROJECT_RULES.md](file:///c:/Users/dopa.mine/Desktop/ophelia/PROJECT_RULES.md)
- [OPHELIA_TIMESFM.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_TIMESFM.md)

## Tasks

<task type="auto">
  <name>Peak-Load Critical Path & Long Shadow Workload Verification</name>
  <files>scratch/vps_phase55_long_test.py</files>
  <action>
    Execute a rigorous multi-stage verification on VPS:
    1. Critical Path Protection: Trigger concurrent TimesFM inference while exercising API health, automation evaluation, position manager loop, and reconciliation. Prove zero state skips, zero delayed transitions, and latencies remain within bounds.
    2. Extended Realistic Shadow Workload: Run multiple consecutive 5m forecast cycles across universal watchlist (BTC, ETH, SOL, XRP, XAU) alongside active market data ingestion. Record CPU, RAM, swap I/O, queue depth, and ensure zero missed cycles or crashes.
  </action>
  <verify>python scratch/vps_phase55_long_test.py</verify>
  <done>Zero missed deadlines, sub-second core latencies during peak inference, zero swap thrashing, and stable memory footprint across consecutive cycles.</done>
</task>

<task type="auto">
  <name>Full Regression Suite & Phase 5.5 Resource Gate Report</name>
  <files>tests/, OPHELIA_TIMESFM.md, docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md</files>
  <action>
    1. Run full regression test suite (89 tests) on Local and VPS ensuring 100% pass rate.
    2. Verify Android application build parity (assembleAdminDebug, assembleUserDebug).
    3. Compile and publish the comprehensive Phase 5.5 Resource Gate Report with exact required fields:
       TIMESFM_CPU_BASELINE, TIMESFM_THREAD_BENCHMARK, TIMESFM_BATCH_BENCHMARK, RESOURCE_CONTENTION_ANALYSIS, SWAP_IO_ANALYSIS, CRITICAL_PATH_LATENCY_ANALYSIS, OPTIMIZATION_RECOMMENDATION, SELECTED_CONFIGURATION, REASON_FOR_SELECTION, FORECAST_CORRECTNESS, PHASE_1_5_REGRESSION, PHASE_5_5_RESOURCE_GATE.
  </action>
  <verify>pytest tests/</verify>
  <done>Full 89-test regression suite green, Android builds verified, and Phase 5.5 Resource Gate Report published with all required metrics.</done>
</task>

## Success Criteria
- [ ] Critical trading path latencies verified under peak TimesFM load
- [ ] Extended shadow test completes multiple cycles without crashes or queue build-up
- [ ] 100% regression tests passing on Local and VPS
- [ ] Phase 5.5 Resource Gate signed off with all 12 mandatory sections
