---
phase: 3
plan: 1
wave: 1
---

# Plan 3.1: Automation Worker & Candidate-to-Slot Pipeline

## Objective
Repair the continuous background worker loop so that all active user automations are discovered and evaluated. Bridge qualifying setup candidates (`current_state == 'ENTRY_READY'`) directly into the `SlotAllocationService`, create execution intents, validate deterministic risk, and execute orders in the permitted trading mode.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `control_plane/core.py`
- `control_plane/retest_engine.py`
- `control_plane/intelligence.py`
- `control_plane/slot_engine.py`
- `control_plane/db.py`

## Tasks

<task type="auto">
  <name>Task 3.1: Fix fleet automation evaluation in core.py and db.py</name>
  <files>control_plane/core.py, control_plane/db.py</files>
  <action>
    - In `control_plane/core.py`:
      * Update `evaluate_active_automations()`: Fetch all active automations with `db.list_automations(status="ACTIVE", user_id=None)`.
      * Loop over every active automation, updating `last_evaluated_ms`, `next_evaluation_at`, and `last_eval_reason`.
      * Update worker heartbeat in `AutomationExecutionLease.heartbeat()`.
      * Ensure the worker handles exceptions gracefully without crashing or abandoning the lease.
  </action>
  <verify>python -m pytest tests/test_control_plane_engine.py -v</verify>
  <done>Worker evaluates automations across all users, updating diagnostics and timestamps continuously.</done>
</task>

<task type="auto">
  <name>Task 3.2: Wire SetupCandidate ENTRY_READY to SlotAllocationService and Execution</name>
  <files>control_plane/core.py, control_plane/slot_engine.py, control_plane/intelligence.py</files>
  <action>
    - In `control_plane/slot_engine.py` & `control_plane/core.py`:
      * Implement `dispatch_candidate_to_execution(candidate, user_id=None)`:
        1. Verify candidate is `ENTRY_READY` with verified retest and valid HTF directional regime.
        2. Query `SlotAllocationService.find_eligible_slot(candidate, user_id)` for the user or auto-provision if authorized.
        3. Atomically reserve slot (`status -> 'RESERVED'`).
        4. Create immutable `ExecutionIntent` with idempotency key.
        5. Run deterministic risk check (max loss, margin limit, leverage limit).
        6. Submit order via BingX client (LIVE) or execute in Shadow broker (SHADOW).
        7. Upon fill, transition slot to `OCCUPIED` and create position in `positions` table.
      * Wire this dispatcher into the continuous evaluation loop so candidates are evaluated and executed in real-time.
  </action>
  <verify>python -m pytest tests/test_phase4_candidate_lifecycle.py -v</verify>
  <done>Qualifying candidate in ENTRY_READY triggers atomic slot reservation, execution intent, and position creation.</done>
</task>

## Success Criteria
- [ ] Active automations across all users are discovered and evaluated by the worker loop.
- [ ] Candidate with confirmed retest transition to `ENTRY_READY` triggers slot reservation without manual intervention.
- [ ] Immutable `ExecutionIntent` is persisted and audited before execution.
- [ ] System handles process restarts without duplicate executions or lost automations.
