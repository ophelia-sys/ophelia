---
phase: 1
plan: 1
wave: 1
---

# Plan 1.1: Multi-User Identity & Execution Safety Hardening

## Objective
Eliminate all insecure fallbacks to User 1, default credentials, or environment clients. Enforce strict cryptographic identity and per-user state isolation across database queries, notifications, execution helpers, and API endpoints.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `control_plane/db.py`
- `control_plane/core.py`
- `control_plane/credential_vault.py`
- `control_plane/api.py`

## Tasks

<task type="auto">
  <name>Task 1.1: Remove user_id=1 default arguments across database, notifications, and execution helpers</name>
  <files>control_plane/db.py, control_plane/core.py, control_plane/notifications.py, control_plane/opportunity_bus.py</files>
  <action>
    - In `control_plane/db.py`:
      * Refactor `list_automations(status=None, user_id=None)` so `user_id=None` queries across all users for fleet evaluation, while passing an integer filters strictly by that user.
      * Remove `user_id: int = 1` default parameters on `create_automation`, `set_automation_status`, `delete_automation`, `update_automation`, `record_shadow_trade`, `open_shadow_trades`, `ensure_seed_watchlist`, `watchlist_add`, `watchlist_remove`, `create_position`, `count_active_automations`, `get_capacity_metrics`, `has_open_position_for_automation`, `has_open_position_for_symbol`, `closed_positions_since`, `get_recent_completed_trades`, `get_equity_at_or_before`, `get_paginated_trade_history`, `get_performance_analytics`, `get_audit_events`, `audit`, `get_notifications`, `mark_notification_read`. Make `user_id` an explicit required parameter (or `user_id: int | None = None` where admin multi-user query is intended).
    - In `control_plane/core.py`:
      * In `_live_client(user_id=None, is_admin_caller=False)`: remove `effective_uid = user_id if user_id is not None and user_id > 0 else 1`. If `user_id is None` or `user_id <= 0`, raise `CoreReject("Explicit authenticated user_id is required for live execution")`.
      * In `_live_client()`: remove the fallback `if is_admin_caller and effective_uid == 1: c = bingx_client.from_env()`. Live orders must strictly use owned credentials from `credential_vault`.
      * Update all internal calls (`evaluate_open_positions_with_execution`, `close_position`, etc.) to pass the exact `user_id` of the position owner.
    - In `control_plane/notifications.py`:
      * Remove default `user_id: int = 1` from all notification dispatch functions, requiring the caller to supply the owner's `user_id`.
  </action>
  <verify>python -m pytest tests/test_user_account_isolation.py -v</verify>
  <done>Zero functions silently default to User 1; missing user_id raises explicit error rather than borrowing user 1.</done>
</task>

<task type="auto">
  <name>Task 1.2: Audit and harden credential vault and God Eye</name>
  <files>control_plane/credential_vault.py, control_plane/api.py</files>
  <action>
    - In `control_plane/credential_vault.py`:
      * Ensure `get_user_bingx_client(user_id, allow_trade=True)` strictly decrypts the user's registered AES-GCM credentials.
      * Prevent any cross-user leakage or fallback to environment variables.
    - In `control_plane/api.py`:
      * Audit God Eye overview (`/api/admin/god-eye/overview`): ensure `db.purge_synthetic_users()` removes synthetic accounts.
      * Unconnected users must display `bingx_connection: "NOT CONNECTED"`, `balance: null`, `equity: null`.
      * Verify that user endpoints (`/api/positions`, `/api/automations`, `/api/autonomous/slots`, etc.) use `get_current_user_id` or `require_authenticated_user` with strict scoping.
  </action>
  <verify>python -m pytest tests/test_role_authorization.py -v</verify>
  <done>God Eye displays only genuine users with honest statuses; unauthenticated or cross-user requests receive 401/403.</done>
</task>

## Success Criteria
- [ ] No function in `control_plane/db.py`, `core.py`, or `api.py` falls back to `user_id=1` or environment credentials.
- [ ] User A cannot query or mutate User B's state under any API path.
- [ ] Multi-user isolation unit tests pass cleanly.
