---
phase: 2
plan: 1
wave: 1
---

# Plan 2.1: Slot Allocation Service & Autonomous Provisioning

## Objective
Build a dedicated, production-grade `SlotAllocationService` (`control_plane/slot_engine.py`) that enforces the slot state machine (`AVAILABLE -> RESERVED -> OCCUPIED -> RECONCILING -> AVAILABLE`), guarantees atomic reservation without race conditions, persists immutable `ExecutionIntent` records, and deterministically auto-provisions slots within user-authorized envelopes.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `control_plane/db.py`
- `control_plane/api.py`

## Tasks

<task type="auto">
  <name>Task 2.1: Implement SlotAllocationService and ExecutionIntent persistence</name>
  <files>control_plane/slot_engine.py, control_plane/db.py</files>
  <action>
    - In `control_plane/db.py`:
      * Create table `execution_intents` with fields: `execution_intent_id`, `candidate_id`, `automation_id`, `slot_id`, `user_id`, `account_id`, `instrument`, `direction`, `requested_margin`, `leverage`, `entry_policy`, `stop_policy`, `tp_policy`, `trailing_policy`, `created_at`, `status`, `idempotency_key`.
      * Add helper methods: `create_execution_intent`, `update_execution_intent_status`, `get_execution_intent`.
      * Ensure `autonomous_trade_slots` table has all necessary columns: `id`, `name`, `enabled`, `asset_scope`, `strategy_scope`, `slot_mode`, `allocated_margin_usdt`, `max_leverage`, `max_loss_usdt`, `max_loss_pct`, `trailing_enabled`, `trailing_pct`, `tp1_enabled`, `tp1_pct`, `breakeven_enabled`, `breakeven_mode`, `status`, `current_candidate_id`, `current_position_id`, `reserved_at`, `released_at`, `user_id`, `account_id`.
    - Create `control_plane/slot_engine.py`:
      * Implement class `SlotAllocationService`:
        - `find_eligible_slot(candidate, user_id)`: Selects active, compatible slot (`AVAILABLE`, scope match, strategy match).
        - `reserve_slot(slot_id, candidate_id, user_id)`: Atomic conditional update `UPDATE autonomous_trade_slots SET status='RESERVED', current_candidate_id=?, reserved_at=? WHERE id=? AND status='AVAILABLE' AND user_id=?`.
        - `auto_provision_slot(user_id, scope, template)`: Deterministically creates a new slot if user's slot count < max allowed and total allocated margin < global capital envelope.
        - `occupy_slot(slot_id, position_id, user_id)`: Transitions slot to `OCCUPIED`.
        - `release_slot(slot_id, user_id)`: Transitions slot back to `AVAILABLE`.
        - `reconcile_slots(user_id)`: Checks for stale reservations (e.g. > 60s without trade) or closed positions, releasing them back to `AVAILABLE`.
        - `create_execution_intent(...)`: Persists immutable intent prior to submission.
  </action>
  <verify>python -m pytest tests/test_cross_asset_and_slot_concurrency.py -v</verify>
  <done>SlotAllocationService passes unit checks, atomic reservation blocks double-spend, auto-provisioning adheres to envelope limits.</done>
</task>

<task type="auto">
  <name>Task 2.2: Concurrency & Slot State Machine Test Suite</name>
  <files>tests/test_slot_engine.py</files>
  <action>
    - Create `tests/test_slot_engine.py` testing:
      * State machine progression: `AVAILABLE -> RESERVED -> OCCUPIED -> RECONCILING -> AVAILABLE`.
      * Race conditions: Concurrent threads attempting to reserve the same slot; assert exactly 1 succeeds and 1 fails.
      * Auto-provisioning: Verified creation within authorized envelope; assert rejection when slot limit or capital ceiling is exceeded.
      * Auto-provisioning rejects arbitrary ML-selected parameters (must come from template).
      * Scoping: Asset scope (`CRYPTO`, `US_MARKET`, `COMMODITIES`, `ALL`) filtering.
  </action>
  <verify>python -m pytest tests/test_slot_engine.py -v</verify>
  <done>All tests in `tests/test_slot_engine.py` pass cleanly with zero race conditions.</done>
</task>

## Success Criteria
- [ ] `SlotAllocationService` handles finding, reserving, occupying, releasing, and reconciling slots.
- [ ] Atomic reservation guarantees zero duplicate occupancy.
- [ ] Auto-provisioning operates strictly within authorized capital policy envelopes.
- [ ] `execution_intents` records persisted and auditable.
