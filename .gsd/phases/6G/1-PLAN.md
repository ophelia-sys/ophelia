---
phase: 6G
plan: 1
wave: 1
gap_closure: false
---

# Plan 6G.1: Research Review Matrix, Full System Safety Regression, Sustained Stability & Final Report

## Objective
Conclude Phases 6D.1, 6E, and 6F with comprehensive research governance:
1. Synthesize final research matrix for all 8 microstructure modules and all TimesFM feature conditions with honest, unhyped designations (`IMPLEMENTATION_VALIDATED`, `EMPIRICALLY_SUPPORTED`, `INCONCLUSIVE`, `NOT_ROBUST`, `NO_INCREMENTAL_VALUE`).
2. Run full system safety regression suite across all components:
   - Full Phase 1–5 regression
   - Manual order terminal regression
   - Full TimesFM regression
   - Phase 6A, 6B, 6C, 6D.1, 6E, 6F regressions
3. Execute sustained resource profile and stability verification on VPS (`15.235.193.47`): CPU, RAM, swap I/O, TimesFM latency, microstructure calculation latency, DB latency, API latency, automation latency, position manager latency, queue depth, missed cycles, restart recovery.
4. Verify local/VPS/app parity, compile and distribute Android Admin & User release APKs (`/download/admin`, `/download/user`).
5. Author final report `docs/PHASE_6D1_6E_6F_RESEARCH_REPORT.md` and enforce strict stopping condition (no autonomous trading authority enabled).

## Context
Load these files for context:
- control_plane/forecast_service.py
- control_plane/microstructure_engine.py
- control_plane/microstructure_evaluation.py
- control_plane/timesfm_adapter.py
- docs/PHASE_6D_MICROSTRUCTURE_REPORT.md

## Tasks

<task type="auto">
  <name>Synthesize Final Research Matrix and Execute Full System Safety Regression</name>
  <files>
    tests/test_master_system_regression_phase6.py
    scratch/run_full_system_regression.py
  </files>
  <action>
    1. Create scratch/run_full_system_regression.py:
       - Run Phase 1-5 core regression tests.
       - Run Phase 5.6 manual terminal regression.
       - Run TimesFM forecast service regression.
       - Run Phase 6A, 6B, 6C, 6D.1, 6E, 6F microstructure tests.
       - Verify safety invariants: zero real exchange orders, zero manual orders created, zero slots reserved or modified, trading authority strictly FALSE.
       - Verify multi-user isolation: Admin vs User account data partitioning.
       - Verify restart recovery: services restart cleanly without state corruption.
    2. Execute locally and verify 100% passing tests.
  </action>
  <verify>
    .venv/Scripts/python.exe scratch/run_full_system_regression.py
  </verify>
  <done>
    Full regression passes across all subsystems; zero safety violations detected.
  </done>
</task>

<task type="auto">
  <name>Run Sustained Resource Profile & Stability Benchmark on VPS and Build Release APKs</name>
  <files>
    scratch/benchmark_sustained_stability_vps.py
    android-app/app/build.gradle.kts
  </files>
  <action>
    1. Run scratch/benchmark_sustained_stability_vps.py on VPS:
       - Monitor CPU, RAM, Swap, inference latency, DB latency, and API latency under continuous concurrent TimesFM + microstructure workload.
       - Confirm zero thread contention and memory stability (preserving Phase 5.5 optimization).
    2. Build fresh Android Admin and User release APKs locally:
       cd android-app && ./gradlew assembleRelease
    3. Deploy APKs and all modified code to VPS (/opt/ophelia and /opt/ophelia/static).
    4. Verify Nginx /download/admin and /download/user endpoints return HTTP 200 with matching binary hashes.
  </action>
  <verify>
    .venv/Scripts/python.exe scratch/benchmark_sustained_stability_vps.py
  </verify>
  <done>
    VPS stability benchmark verified; APKs built and deployed to VPS static endpoints.
  </done>
</task>

<task type="auto">
  <name>Author Comprehensive Final Research Report and Enforce Strict Stop</name>
  <files>
    docs/PHASE_6D1_6E_6F_RESEARCH_REPORT.md
    .gsd/STATE.md
    .gsd/ROADMAP.md
  </files>
  <action>
    1. Author docs/PHASE_6D1_6E_6F_RESEARCH_REPORT.md documenting all sections requested in prompt:
       - PHASE_6D1_CORRECTION_STATUS (VECM sample size >= 300, raw & bounded GG, cumulative impact H20 vs permanent impact, signed-sqrt volume robustness)
       - HASBROUCK_STATUS & VECM_STATUS
       - MICROSTRUCTURE_6E_STATUS & TIMESFM_6F_STATUS
       - IMPLEMENTATION_VALIDITY, RUNTIME_VALIDITY, EMPIRICAL_VALIDITY, PREDICTIVE_VALIDITY, ROBUSTNESS_STATUS
       - TIMESFM_BASELINE_STATUS, TIMESFM_AUGMENTED_STATUS, TIMESFM_INCREMENTAL_VALUE
       - Pass/Fail checklist (No-lookahead, temporal splits, multiple testing, reproducibility, research isolation, multi-user isolation, resource stability, full regressions)
       - TRADING_AUTHORITY = DISABLED
       - FINAL_RESEARCH_CONCLUSION distinguishing implemented vs empirically supported vs predictively supported vs robust.
    2. Update .gsd/STATE.md and .gsd/ROADMAP.md.
    3. STRICT STOP: Do not integrate into live candidate ranking, do not enable trading authority.
  </action>
  <verify>
    Test-Path "docs/PHASE_6D1_6E_6F_RESEARCH_REPORT.md"
  </verify>
  <done>
    Final research report authored; roadmap updated; strict stop enforced.
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] 8-module research matrix complete with honest designations.
- [ ] Full regression passes across all phases without regressions.
- [ ] Sustained VPS stability benchmark captures latency, CPU, and RAM metrics.
- [ ] Android Admin and User release APKs compiled and hosted on VPS.
- [ ] Comprehensive final report authored in docs/PHASE_6D1_6E_6F_RESEARCH_REPORT.md.
- [ ] Strict stop condition enforced with zero trading authority enabled.

## Success Criteria
- [ ] All 3 tasks verified passing
- [ ] Must-haves confirmed
- [ ] Final report complete
