---
phase: 10
plan: 3
wave: 2
---

# Plan 10.3: Cross-Venue Basis Engine & Execution Translation

## Objective
Build a dedicated cross-venue basis translation subsystem in `control_plane/cross_venue_basis.py`:
- Track `binance_price` vs `bingx_price` in real time.
- Calculate `basis_abs = bingx_price - binance_price`, `basis_pct = (bingx_price - binance_price) / binance_price * 100`, rolling `basis_zscore`, and `timestamp_delta_ms`.
- Track data ages: `binance_data_age_ms`, `bingx_data_age_ms`.
- Classify states: `ALIGNED`, `NORMAL_BASIS`, `ELEVATED_BASIS`, `DISLOCATED`, `STALE`, `NOT_AVAILABLE`, `DEGRADED`.
- Provide translation interface: Translates Binance signal prices and structures into BingX execution context with contract precision, min notional, and leverage constraints.

## Context
- `control_plane/cross_venue_basis.py`
- `models/instrument.py`
- `control_plane/instruments.py`
- `control_plane/bingx_client.py`

## Tasks

<task type="auto">
  <name>Implement Cross-Venue Basis Engine</name>
  <files>control_plane/cross_venue_basis.py</files>
  <action>
    - Create `control_plane/cross_venue_basis.py` with:
      - `CrossVenueBasisSnapshot`: Dataclass holding price, timestamps, basis metrics, quote ages, and basis state.
      - `CrossVenueBasisEngine`: Maintains rolling window of basis observations to compute historical baseline, standard deviation, and winsorized z-score.
      - Threshold evaluation:
        - `ALIGNED`: $|basis\_pct| \le 0.05\%$
        - `NORMAL_BASIS`: $0.05\% < |basis\_pct| \le 0.20\%$
        - `ELEVATED_BASIS`: $0.20\% < |basis\_pct| \le 0.50\%$
        - `DISLOCATED`: $|basis\_pct| > 0.50\%$
        - `STALE`: `data_age > 10000ms`
      - Signal-to-Execution Translation:
        - `translate_signal_to_execution(signal_price, canonical_instrument)`: Translates Binance signal price into valid BingX order tick/lot constraints.
  </action>
  <verify>python -c "from control_plane.cross_venue_basis import CrossVenueBasisEngine; engine = CrossVenueBasisEngine(); snap = engine.compute_basis('BTC', 86300.0, 86320.0, 1000, 1000); assert snap.basis_abs == 20.0; assert snap.state in ('ALIGNED', 'NORMAL_BASIS')"</verify>
  <done>Cross-venue basis engine accurately measures divergence and translates signal price to execution context.</done>
</task>

<task type="auto">
  <name>Author Unit Tests for Basis Engine and Preflight Translation</name>
  <files>tests/test_cross_venue_basis.py</files>
  <action>
    - Test basis calculation with known Binance and BingX prices.
    - Test state classifications (`ALIGNED`, `NORMAL_BASIS`, `ELEVATED_BASIS`, `DISLOCATED`, `STALE`).
    - Test translation to BingX price and quantity precision with minimum notional enforcement.
    - Test handling of missing or stale quotes (`NOT_AVAILABLE`, `STALE`).
  </action>
  <verify>pytest tests/test_cross_venue_basis.py -v</verify>
  <done>All basis engine and translation tests pass with strict validation.</done>
</task>

## Success Criteria
- [ ] Basis engine tracks price divergence and execution quote freshness.
- [ ] Explicit preflight gate prevents execution when basis is dislocated or quote is stale.
- [ ] Translation preserves precision and sizing rules without leakage.
