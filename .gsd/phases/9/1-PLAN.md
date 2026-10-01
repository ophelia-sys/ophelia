---
phase: 9
plan: 1
wave: 1
---

# Plan 9.1: End-to-End Runtime Validation & Final Artifact Release

## Objective
Deploy all synchronized changes to the VPS, restart services, execute a complete end-to-end autonomous trading cycle with verifiable runtime traces, and author all 8 comprehensive engineering reports demanded by the project mandate.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- All prior phase implementations (Phases 1 through 8)

## Tasks

<task type="auto">
  <name>Task 9.1: Synchronize backend and database to VPS and verify services</name>
  <files>control_plane/</files>
  <action>
    - Sync all modified files in `control_plane/` and database migrations to VPS `/opt/ophelia/control_plane/`.
    - Restart systemd services via sudo:
      `systemctl restart ophelia-api.service`
      `systemctl restart ophelia-control.service`
    - Verify services are active and inspect logs via journalctl to guarantee zero startup errors, no unhandled exceptions, and clean lease acquisition.
  </action>
  <verify>ssh ubuntu@15.235.193.47 "systemctl is-active ophelia-api.service; systemctl is-active ophelia-control.service"</verify>
  <done>Both services return active (running) with zero syntax or import errors.</done>
</task>

<task type="auto">
  <name>Task 9.2: Execute controlled end-to-end runtime lifecycle validation</name>
  <files>tests/test_dry_run_e2e_trace.py</files>
  <action>
    - Run an end-to-end trace exercising the complete autonomous pipeline:
      1. Active automation discovered by worker loop.
      2. 5/7 structural setup candidate reaches `ENTRY_READY` with confirmed retest.
      3. Automatic slot discovery queries `SlotAllocationService`.
      4. Atomic reservation locks the slot.
      5. Immutable `ExecutionIntent` is persisted.
      6. Order is placed in SHADOW mode.
      7. Position created with stops and TP targets.
      8. TP1 50% reduction executed.
      9. Mathematical net breakeven stop loss applied.
      10. Trailing stop ratcheted monotonically.
      11. Position closed on exit signal.
      12. Reconciliation releases slot back to `AVAILABLE`.
    - Record exact IDs, timestamps, and parameters for the audit log.
  </action>
  <verify>python -m pytest tests/test_dry_run_e2e_trace.py -v -s</verify>
  <done>Complete autonomous lifecycle runs with verifiable trace from detection to slot release.</done>
</task>

<task type="auto">
  <name>Task 9.3: Generate all 8 comprehensive engineering reports</name>
  <files>
    OPHELIA_CURRENT_STATE.md,
    OPHELIA_AUTONOMOUS_EXECUTION_AUDIT.md,
    OPHELIA_SLOT_ENGINE.md,
    OPHELIA_AUTOMATION_ENGINE.md,
    OPHELIA_TIMESFM.md,
    OPHELIA_MICROSTRUCTURE.md,
    OPHELIA_RELEASE.md,
    OPHELIA_RUNTIME_EVIDENCE.md
  </files>
  <action>
    - Author and persist all 8 mandatory engineering artifacts:
      * `OPHELIA_CURRENT_STATE.md`: Update matrix with final post-implementation statuses.
      * `OPHELIA_AUTONOMOUS_EXECUTION_AUDIT.md`: Complete forensic report answering all questions in §83.
      * `OPHELIA_SLOT_ENGINE.md`: Architecture, state machine, reservation locking, auto-provisioning envelope.
      * `OPHELIA_AUTOMATION_ENGINE.md`: Worker lifecycle, fleet evaluation, diagnostics, heartbeat.
      * `OPHELIA_TIMESFM.md`: Pinned checkpoint, architecture, multivariate/covariate feature schema, shadow benchmark results.
      * `OPHELIA_MICROSTRUCTURE.md`: Modules A-E, toxicity scoring, ADAOT research score, data availability.
      * `OPHELIA_RELEASE.md`: Commit hash, backend version, DB migration version, Admin/User APK hashes, Telegram download links.
      * `OPHELIA_RUNTIME_EVIDENCE.md`: Real audit logs, candidate ID, slot ID, intent ID, position ID, fill, breakeven, trailing, and release.
  </action>
  <verify>Test-Path "OPHELIA_RUNTIME_EVIDENCE.md" -and Test-Path "OPHELIA_RELEASE.md"</verify>
  <done>All 8 engineering reports generated with empirical proof and zero empty claims.</done>
</task>

## Success Criteria
- [ ] Complete autonomous trading loop proven end-to-end with concrete runtime evidence.
- [ ] Services active on VPS with clean logs.
- [ ] All 8 engineering reports authored, accurate, and persisted in workspace root.
- [ ] Full parity and synchronization across Local, VPS, Admin, and User environments.
