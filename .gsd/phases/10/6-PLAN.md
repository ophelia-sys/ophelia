---
phase: 10
plan: 6
wave: 4
---

# Plan 10.6: Review Gates, System Regression, Sustained VPS Benchmark, Android Observability & Final Report

## Objective
Execute the full review and verification protocol:
1. Review Gate 1: Architecture Review (Multi-venue separation, data lineage, causal boundaries, execution isolation).
2. Review Gate 2: Code Review (Race conditions, async/threading safety, memory leaks, DB WAL locks).
3. Review Gate 3: Quant / Statistical Review (Zero lookahead, train-only normalization, walk-forward, FDR control).
4. Review Gate 4: Execution / Safety Review (`TRADING_AUTHORITY = FALSE`, zero orders, zero slot mutations).
5. Review Gate 5: Live Runtime Review (VPS deployment, commit parity, service health, Binance & BingX live freshness).
6. Android UI Observability: Add multi-venue telemetry card (Binance market data + basis + TimesFM compatibility) in `AutonomousTradingScreen.kt` and compile APKs.
7. Sustained VPS Stability Benchmark: Monitor CPU, RAM, swap, load, and DB WAL over active ingestion cycles.
8. Deliver Comprehensive Final Report: `docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md` answering all 19 mandatory questions with machine-readable status block.

## Context
- `control_plane/api.py`
- `android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt`
- `docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md`
- `.gsd/ROADMAP.md`
- `.gsd/STATE.md`

## Tasks

<task type="auto">
  <name>Implement FastAPI Multi-Venue and Compatibility Endpoints</name>
  <files>control_plane/api.py</files>
  <action>
    - Add authenticated read-only observability endpoints:
      - `GET /api/binance/diagnostics`: Feed status, server time, stream health.
      - `GET /api/binance/candles`: Latest closed 1m and derived 5m candles.
      - `GET /api/cross-venue/basis/{symbol}`: Latest basis, basis %, z-score, quote freshness, basis state.
      - `GET /api/timesfm/candidate-forecast/{candidate_id}`: Frozen candidate forecast path and quantiles.
      - `GET /api/timesfm/compatibility/{candidate_id}`: Three distinct dimensions (`direction`, `dispersion`, `compatibility`).
    - Enforce JWT authentication with user scoping.
  </action>
  <verify>python -c "from control_plane import api; assert hasattr(api, 'app')"</verify>
  <done>FastAPI endpoints exposed and protected with JWT authentication.</done>
</task>

<task type="auto">
  <name>Update Android Observability & Build Check</name>
  <files>android-app/app/src/main/java/com/ophelia/app/ui/screens/AutonomousTradingScreen.kt</files>
  <action>
    - Add Multi-Venue & TimesFM Compatibility card in `AutonomousTradingScreen.kt`:
      - Shows `DATA_VENUE: BINANCE (USD-M)`, `EXECUTION_VENUE: BINGX (SWAP)`.
      - Shows live Basis %, Basis State (`ALIGNED`, `NORMAL`, `DISLOCATED`).
      - Shows TimesFM Compatibility badge (`COMPATIBLE`, `INCOMPATIBLE`, `NEUTRAL`) and 15m-60m path trajectory.
      - Clearly labeled `RESEARCH / SHADOW ONLY • ZERO LIVE TRADING AUTHORITY`.
    - Run Gradle check or ensure Kotlin models match API models.
  </action>
  <verify>git status -s android-app/</verify>
  <done>Android observability telemetry updated and synchronized with API models.</done>
</task>

<task type="auto">
  <name>Execute Review Gates, VPS Synchronization, Regression & Publish Report</name>
  <files>docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md</files>
  <action>
    - Sync all modified files to VPS (`15.235.193.47`).
    - Run full local test suite and remote VPS test suite (137+ tests + new Phase 10 test suite).
    - Measure sustained VPS resource utilization (RAM, swap, CPU load).
    - Author `docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md` answering all questions A through S from Section 55.
    - Append machine-readable status block and strictly enforce `TRADING_AUTHORITY = FALSE`.
  </action>
  <verify>python scratch/vps_helper.py "ls -la /opt/ophelia/docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md"</verify>
  <done>Complete final report delivered, synchronized to VPS, and verified with zero safety violations.</done>
</task>

## Success Criteria
- [ ] Review Gates 1 through 5 fully executed and documented.
- [ ] Full regression passes on both Local and VPS.
- [ ] VPS services active and healthy in SHADOW mode.
- [ ] `docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md` authored and synced.
- [ ] Invariant confirmed: `TRADING_AUTHORITY = FALSE`.
