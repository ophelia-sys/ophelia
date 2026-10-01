---
phase: 4
plan: 1
wave: 1
---

# Plan 4.1: Position Manager Daemon Hardening

## Objective
Harden the VPS-authoritative position daemon (`control_plane/position_manager_daemon.py`) to manage open positions through their complete lifecycle: execute exact 50% TP1 partial exits, adjust stops to mathematical net breakeven accounting for execution fees and funding, enforce monotonic trailing stops, and reconcile state upon process restart.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `control_plane/position_manager_daemon.py`
- `control_plane/core.py`
- `control_plane/db.py`

## Tasks

<task type="auto">
  <name>Task 4.1: Implement exact 50% TP1, mathematical net breakeven, and monotonic trailing</name>
  <files>control_plane/position_manager_daemon.py, control_plane/core.py</files>
  <action>
    - In `control_plane/position_manager_daemon.py` & `control_plane/core.py`:
      * TP1 Execution:
        - When price reaches TP1, close exactly 50% of the active position quantity.
        - Record partial fill, calculate realized P&L, update remaining quantity on the position.
        - Dispatch notification with exact partial metrics.
      * Mathematical Net Breakeven:
        - Calculate actual cost basis:
          $$\text{Stop}_{\text{BE}} = \text{Entry} \pm \frac{\text{Total Entry/Exit Fees} + \text{Funding}}{\text{Remaining Quantity}}$$
        - Move stop loss to this net breakeven price. Never use raw `entry_price` without fee offset.
      * Monotonic Trailing:
        - For LONG: $\text{New Stop} \ge \text{Current Stop}$.
        - For SHORT: $\text{New Stop} \le \text{Current Stop}$.
        - Invariant: A trailing stop calculation must NEVER worsen the existing stop level.
      * Full Position Exit:
        - When stop or final TP is hit, close remaining quantity.
        - Transition position status to `CLOSED`.
        - Release associated slot back to `AVAILABLE`.
  </action>
  <verify>python -m pytest tests/test_live_partial_exit_order_construction.py -v</verify>
  <done>TP1 closes exactly 50%; breakeven covers calculated costs; trailing stop is strictly monotonic.</done>
</task>

<task type="auto">
  <name>Task 4.2: Implement restart recovery and exchange reconciliation</name>
  <files>control_plane/position_manager_daemon.py, control_plane/db.py</files>
  <action>
    - In `control_plane/position_manager_daemon.py`:
      * On daemon startup, run `reconcile_positions_on_startup()`:
        - Fetch all positions in `positions` table with status in (`OPEN`, `PARTIAL`, `TRAILING`).
        - For SHADOW mode: reconstruct in-memory state and resume monitoring.
        - For LIVE mode: query BingX REST `/openApi/swap/v2/user/positions` for each active user. If exchange shows position closed, reconcile SQLite position to `CLOSED` and release the slot.
        - If exchange shows partial fill or changed quantity, sync local tracking.
  </action>
  <verify>python -m pytest tests/test_funnel_accounting.py -v</verify>
  <done>Daemon reconstructs open trade state after process restart without orphaned positions or lost slots.</done>
</task>

## Success Criteria
- [ ] TP1 closes exactly 50% of position quantity.
- [ ] Breakeven stop incorporates trading fees and funding to ensure zero-loss protection.
- [ ] Trailing stop updates are strictly monotonic.
- [ ] On trade close, the associated trade slot is automatically released to `AVAILABLE`.
- [ ] Process restart recovers all open positions and resumes tracking seamlessly.
