---
phase: 5.6
plan: 2
wave: 2
depends_on:
  - "5.6.1"
files_modified:
  - control_plane/db.py
  - control_plane/api.py
  - control_plane/core.py
  - control_plane/us_market.py
  - tests/test_manual_order_terminal.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Manual order submission follows strict pre-flight pipeline: resolution -> status -> precision -> min size -> leverage -> margin -> risk -> submission"
    - "Order lifecycle distinguishes SUBMITTED, ACKNOWLEDGED, PARTIALLY_FILLED, FILLED, REJECTED without prematurely claiming FILLED"
    - "Manual orders persist to manual_orders table with internal_order_id, venue, venue_product, venue_symbol, client_order_id, user_id"
    - "Multi-user account isolation is enforced (no global client, scoped to owned BingX credentials)"
    - "API returns standard error codes: INSTRUMENT_NOT_FOUND, VENUE_SYMBOL_NOT_FOUND, TRADING_SUSPENDED, INVALID_PRECISION, MINIMUM_SIZE_FAILED, LEVERAGE_NOT_ALLOWED"
  artifacts:
    - "manual_orders table created and managed in control_plane/db.py"
    - "/api/orders/manual updated with full validation pipeline"
    - "tests/test_manual_order_terminal.py passes"
---

# Plan 5.6.2: Manual Order Execution Engine & Lifecycle Persistence

<objective>
Implement the hardened manual order execution engine, full lifecycle state machine, database persistence, and multi-user credential isolation across Crypto, US Equities, and Commodities.
</objective>

<context>
- control_plane/instruments.py
- control_plane/api.py
- control_plane/core.py
- control_plane/db.py
- control_plane/credential_vault.py
- control_plane/bingx_client.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Database Persistence for Manual Orders & Lifecycle State</name>
  <files>
    control_plane/db.py
  </files>
  <action>
    1. In control_plane/db.py, implement idempotent schema creation for manual_orders table:
       - internal_order_id (TEXT PRIMARY KEY)
       - venue (TEXT)
       - venue_product (TEXT)
       - venue_symbol (TEXT)
       - venue_order_id (TEXT)
       - client_order_id (TEXT)
       - asset_class (TEXT)
       - side (TEXT)
       - order_type (TEXT)
       - requested_quantity (REAL)
       - requested_price (REAL)
       - submitted_at (INTEGER)
       - acknowledged_at (INTEGER)
       - filled_quantity (REAL)
       - average_fill_price (REAL)
       - fees (REAL)
       - status (TEXT)
       - reconciliation_status (TEXT)
       - user_id (INTEGER)
       - detail_json (TEXT)
    2. Add CRUD helper methods:
       - create_manual_order(order_data: dict) -> str
       - get_manual_order(internal_order_id: str, user_id: int) -> dict | None
       - update_manual_order_status(internal_order_id: str, status: str, venue_order_id: str | None = None, fill_qty: float | None = None, fill_px: float | None = None, user_id: int | None = None)
       - list_manual_orders(user_id: int, limit: int = 50) -> list[dict]
  </action>
  <verify>
    python -c "from control_plane import db; db.init_db(); print('DB manual_orders OK')"
  </verify>
  <done>
    manual_orders table and helper methods implemented with idempotent schema.
  </done>
</task>

<task type="auto">
  <name>Task 2: Hardened Order Submission & Unified Endpoint</name>
  <files>
    control_plane/api.py
    control_plane/us_market.py
    tests/test_manual_order_terminal.py
  </files>
  <action>
    1. In control_plane/api.py:
       - Refactor api_manual_order (/api/orders/manual):
         a. Extract authenticated user_id from token.
         b. Resolve instrument using InstrumentResolver.resolve(req.symbol, req.asset_class).
         c. Check trading status (TRADABLE).
         d. Validate precision (price and quantity step/precision).
         e. Check minimum order size and minimum notional.
         f. Check leverage limit against instrument rules.
         g. Check margin and risk (canonical geometry: SL < Entry < TP1 < TP2 for LONG).
         h. Fetch user-scoped BingX client from credential_vault.
         i. Submit order (in SHADOW mode generate immediate ACKNOWLEDGED mock fill or simulated order; in LIVE submit to BingX).
         j. Persist to manual_orders and positions table.
         k. Return rich ManualOrderResponse with lifecycle status, resolved venue symbol, and order IDs.
       - Refactor /api/market/search to use InstrumentResolver so search returns clean display_symbol (e.g. NFLX) and authoritative venue_symbol (e.g. NCSKNETFLIX2USD-USDT).
    2. In control_plane/us_market.py:
       - Update map_stock_to_bingx to use InstrumentResolver.
    3. Create tests/test_manual_order_terminal.py:
       - Test matrix: Crypto (BTC, ETH, SOL), US Market (NFLX, AAPL, NVDA), Commodities (GOLD, SILVER).
       - Verify Netflix specifically executes with venue symbol NCSKNETFLIX2USD-USDT when user inputs 'NFLX'.
       - Verify multi-user isolation (User 2 cannot see or cancel User 1's orders).
       - Verify invalid geometry, invalid precision, and undersized orders fail with explicit error codes.
  </action>
  <verify>
    pytest tests/test_manual_order_terminal.py -v
  </verify>
  <done>
    Manual order endpoint refactored and verified across all asset classes with multi-user safety.
  </done>
</task>

</tasks>

<verification>
After tasks, verify:
- [ ] manual_orders table records persist properly
- [ ] /api/orders/manual validates and executes orders for BTC, NFLX, and GOLD
- [ ] All tests in tests/test_manual_order_terminal.py pass
</verification>

<success_criteria>
- [ ] Full order submission pipeline enforced
- [ ] Lifecycles distinguished without false FILLED state
- [ ] Multi-user isolation maintained
</success_criteria>
