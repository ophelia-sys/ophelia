---
phase: 10
plan: 1
wave: 1
---

# Plan 10.1: Canonical Multi-Venue Instrument Model & Dynamic Resolvers

## Objective
Extend `models/instrument.py` and `control_plane/instruments.py` to support dual-venue architecture:
- `DATA_VENUE = BINANCE` (USD-M Futures)
- `EXECUTION_VENUE = BINGX` (Perpetual Swap)
Represent canonical instrument identity, dynamic metadata discovery from both venues, price/qty precisions, min order size/notional, mapping states (`UNRESOLVED`, `RESOLVED`, `TRADABLE_BOTH`, `BINANCE_ONLY`, `BINGX_ONLY`, `MISMATCH`, `STALE`, `INVALID`), and zero-leakage translation.

## Context
- `models/instrument.py`
- `control_plane/instruments.py`
- `.gsd/phases/10/AUDIT_MATRIX.md`
- `.gsd/phases/10/CONTRACT_VERIFICATION.md`

## Tasks

<task type="auto">
  <name>Extend CanonicalInstrument Model to Dual-Venue Schema</name>
  <files>models/instrument.py</files>
  <action>
    - Add explicit dual-venue attributes to `CanonicalInstrument`:
      - `binance_symbol`, `binance_product`, `binance_contract_type`, `binance_status`, `binance_price_precision`, `binance_quantity_precision`, `binance_min_quantity`, `binance_min_notional`, `binance_discovery_timestamp`
      - `bingx_symbol`, `bingx_product`, `bingx_status`, `bingx_price_precision`, `bingx_quantity_precision`, `bingx_min_quantity`, `bingx_min_notional`, `bingx_discovery_timestamp`
      - `mapping_status` (Enum: `UNRESOLVED`, `RESOLVED`, `TRADABLE_BOTH`, `BINANCE_ONLY`, `BINGX_ONLY`, `MISMATCH`, `STALE`, `INVALID`)
      - `mapping_source`, `mapping_confidence`, `last_refreshed`
    - Retain existing properties (`display_symbol`, `internal_instrument_id`, `asset_class`, etc.) with backward-compatible defaults.
    - Implement `to_dict()` and `from_dict()`.
  </action>
  <verify>python -c "from models.instrument import CanonicalInstrument; c = CanonicalInstrument.from_dict({'display_symbol': 'BTC', 'binance_symbol': 'BTCUSDT', 'bingx_symbol': 'BTC-USDT', 'mapping_status': 'TRADABLE_BOTH'}); assert c.mapping_status == 'TRADABLE_BOTH'"</verify>
  <done>CanonicalInstrument represents both venues explicitly without loss of precision or status.</done>
</task>

<task type="auto">
  <name>Implement Multi-Venue Dynamic Resolver</name>
  <files>control_plane/instruments.py</files>
  <action>
    - Extend `InstrumentResolver` to discover both Binance USD-M Perpetual metadata (`https://fapi.binance.com/fapi/v1/exchangeInfo`) and BingX Swap V2 metadata (`https://open-api.bingx.com/openApi/swap/v2/quote/contracts`).
    - Correlate by underlying base asset (`BTC`, `ETH`, `SOL`, `XRP`, `GOLD`).
    - Compute mapping status deterministically (`TRADABLE_BOTH` if active on both, `BINANCE_ONLY`, `BINGX_ONLY`, etc.).
    - Thread-safe caching with TTL (10 minutes) and explicit invalidation.
    - Provide lookup helpers: `resolve_canonical(symbol_or_alias)`, `get_binance_symbol(canonical_id)`, `get_bingx_symbol(canonical_id)`.
  </action>
  <verify>python -c "from control_plane.instruments import InstrumentResolver; r = InstrumentResolver.get_instance(); count = r.refresh(force=True); assert count > 0; inst = r.resolve_canonical('BTC'); assert inst.binance_symbol == 'BTCUSDT'; assert inst.bingx_symbol == 'BTC-USDT'; assert inst.mapping_status == 'TRADABLE_BOTH'"</verify>
  <done>InstrumentResolver resolves base symbols to canonical dual-venue representations dynamically.</done>
</task>

<task type="auto">
  <name>Author Unit Tests for Canonical Multi-Venue Instruments</name>
  <files>tests/test_canonical_multi_venue.py</files>
  <action>
    - Test serialization, deserialization, and equality.
    - Test mapping status transitions (`TRADABLE_BOTH`, `BINANCE_ONLY`, `BINGX_ONLY`, `MISMATCH`).
    - Test cache invalidation and fallback handling.
    - Verify zero hardcoded Netflix hacks or unmapped shortcuts.
  </action>
  <verify>pytest tests/test_canonical_multi_venue.py -v</verify>
  <done>All tests pass with 100% assertions on dual-venue canonical attributes.</done>
</task>

## Success Criteria
- [ ] Dual-venue `CanonicalInstrument` model passes all type checks.
- [ ] `InstrumentResolver` dynamically correlates Binance USD-M and BingX Swap instruments.
- [ ] Unit tests pass locally and are ready for VPS synchronization.
