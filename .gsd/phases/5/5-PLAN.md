---
phase: 5
plan: 5
wave: 5
---

# Plan 5.5: Real VPS Runtime Verification, Benchmarking, Documentation & Sign-off

## Objective
Deploy all changes to VPS, benchmark real `google/timesfm-3.0-pytorch` inference on VPS hardware, verify zero regressions on existing Phase 1-4 tests, establish exact Local/VPS git commit parity, write comprehensive documentation (`OPHELIA_TIMESFM.md`), update GSD state, and produce the final engineering report.

## Context
- `scratch/vps_helper.py`
- `OPHELIA_TIMESFM.md`
- `.gsd/STATE.md`
- `.gsd/ROADMAP.md`

## Tasks

<task type="auto">
  <name>Task 5.5.1: Synchronize all code and migrations to VPS and verify services</name>
  <files>scratch/vps_helper.py</files>
  <action>
    - Commit all local changes to git.
    - Create deployment bundle and push to VPS `/opt/ophelia`.
    - Apply database migration on VPS SQLite database (`market_1m.db`).
    - Restart systemd services: `ophelia-api.service` and `ophelia-control.service`.
    - Verify services report `active (running)` with 0 error loops.
    - Confirm local and VPS git commit hashes match 100%.
  </action>
  <verify>python -c "from scratch.vps_helper import run_vps_command; out, err = run_vps_command('systemctl is-active ophelia-api ophelia-control && cd /opt/ophelia && git log -n 1 --oneline'); print(out); print(err)"</verify>
  <done>VPS services active and running on identical git commit.</done>
</task>

<task type="auto">
  <name>Task 5.5.2: Execute real VPS benchmark and run existing Phase 1-4 regression tests</name>
  <files>scratch/vps_helper.py</files>
  <action>
    - On VPS:
      * Execute real model load of `google/timesfm-3.0-pytorch` with startup health inference.
      * Measure and record: RAM before load, RAM after load, peak RAM during inference, CPU utilization, cold start latency, warm p50 and p95 inference latency on real 100-bar series.
      * Store real forecast in SQLite database and retrieve it via curl `/api/timesfm/forecasts`.
      * Run existing Phase 1-4 regression tests on VPS to verify autonomous trading and slot reconciliation are completely unaffected.
  </action>
  <verify>python -c "from scratch.vps_helper import run_vps_command; out, err = run_vps_command('/opt/ophelia/.venv/bin/pytest tests/test_phase4_reconciliation_identity.py tests/test_slot_allocation_service.py'); print(out); print(err)"</verify>
  <done>Real benchmark telemetry captured; 100% regression test pass on VPS.</done>
</task>

<task type="auto">
  <name>Task 5.5.3: Author OPHELIA_TIMESFM.md, update GSD state, and produce report</name>
  <files>OPHELIA_TIMESFM.md, .gsd/STATE.md, .gsd/ROADMAP.md</files>
  <action>
    - Create `OPHELIA_TIMESFM.md`:
      * Architecture, pinned versions, checkpoint, input/output schemas, scheduler, VPS resource measurements, benchmark latencies, failure isolation guarantees, shadow evaluation procedure.
    - Update `.gsd/STATE.md` and `.gsd/ROADMAP.md` setting Phase 5 status to `REAL_RUNTIME_VERIFIED`.
    - Push documentation updates to VPS to maintain exact commit parity.
    - Produce final report answering all 38 points in prompt.
  </action>
  <verify>python -c "import os; assert os.path.exists('OPHELIA_TIMESFM.md'); print('OPHELIA_TIMESFM.md verified')"</verify>
  <done>Comprehensive documentation authored; exact parity verified; final report delivered.</done>
</task>

## Success Criteria
- [ ] Real TimesFM 3.0 inference completes on VPS hardware.
- [ ] Telemetry measured: RAM before/after, peak RAM, CPU %, cold/warm latency.
- [ ] Existing Phase 1-4 tests pass 100% on VPS.
- [ ] Local and VPS git commit hashes match exactly.
- [ ] Comprehensive documentation and final report delivered.
- [ ] Phase 5 marked `PHASE_5 = REAL_RUNTIME_VERIFIED`.
