---
phase: 7
plan: 1
wave: 1
---

# Plan 7.1: Multi-Market Parity (US Market & Gold)

## Objective
Harden multi-market parity across the 3 first-class domains: Crypto, US Market, and Commodities / Gold. Eliminate any lingering Indian market references. Ensure Market Movers rank by volume/impact, Sectors provide detailed intelligence, the Overnight engine operates causally, Gold discovers contracts dynamically on BingX, and all market feeds reflect honest data provenance (`REAL_TIME`, `DELAYED`, `NOT_AVAILABLE`).

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `control_plane/us_market.py`
- `control_plane/config.py`
- `control_plane/symbols.py`

## Tasks

<task type="auto">
  <name>Task 7.1: Harden US Market Top 100, Market Movers, and Collapsible Sectors</name>
  <files>control_plane/us_market.py</files>
  <action>
    - In `control_plane/us_market.py`:
      * Verify Top 100 universe consists of actual major Nasdaq/NYSE equities.
      * Market Movers: Rank by multi-factor score: $|\Delta \%| \times \text{RVOL} \times \text{Dollar Volume}$, prioritizing tradability and market impact rather than trivial low-volume percentage spikes.
      * Sectors: Provide structured collapsible data: Technology, Semiconductors, Healthcare, Financials, Energy, Industrials, Consumer, Communication, Materials.
        - Include sector performance, constituent stocks, structural vs temporary catalyst classification with evidence and confidence.
      * US Overnight Engine:
        - Incorporate closing structure, RVOL, order flow, after-hours moves, earnings/macro events.
        - Output actionable states: `CONTINUATION`, `REVERSAL`, `NO_TRADE`, `WAITING`.
        - Enforce session states: `PREMARKET`, `RTH`, `AFTER_HOURS`, `OVERNIGHT`, `CLOSED`, `HOLIDAY`.
      * Data Honesty: If a stock lacks baseline reference or real-time feed, return `NOT_AVAILABLE` or `DELAYED`. Never display `0.0%` or fabricated CVD/GEX.
  </action>
  <verify>python -m pytest tests/test_autonomous_slots_and_us_api.py -v</verify>
  <done>US Market endpoints return honest, non-fabricated data; sectors and movers rank with multi-factor impact.</done>
</task>

<task type="auto">
  <name>Task 7.2: Gold / Commodities Dynamic Discovery & TradFi Registry</name>
  <files>control_plane/config.py, control_plane/symbols.py</files>
  <action>
    - In `control_plane/config.py` & `control_plane/symbols.py`:
      * Ensure Gold is treated as a first-class citizen under `COMMODITIES / GOLD` (never categorized under Crypto).
      * Dynamically query BingX Perpetual contracts endpoint (`/openApi/swap/v2/quote/contracts`) with 5-minute TTL cache.
      * Target observed symbol `NCCOGOLD2USD-USDT` dynamically while supporting aliases (`GOLD(XAU)`, `XAUT-USDT`, `PAXG-USDT`).
      * Maintain `bingx_tradfi_registry` table in SQLite, mapping US equities and Commodities to active BingX Perpetual contracts.
  </action>
  <verify>python -m pytest tests/test_fastapi.py -v</verify>
  <done>Gold resolves dynamically from BingX metadata; TradFi registry updates without hardcoded brittle dependencies.</done>
</task>

## Success Criteria
- [ ] 3-domain structure (Crypto, US Market, Commodities/Gold) fully functional.
- [ ] US Top 100, Market Movers, and Sectors populated with honest, verified market data.
- [ ] Zero Indian market references in codebase.
- [ ] Gold dynamically resolves from BingX contract quote specifications.
