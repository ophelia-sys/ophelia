# OPHELIA LEGACY METRIC MAPPING
Phase 2.9 canonical reconciliation · Generated 2026-08-22 · Status: NORMATIVE FOR ALL NEW RESEARCH

Rule: historical reports are NEVER edited. New work may not use deprecated metrics.

## 1. Deprecated / invalid metrics

| Legacy metric | Where used | Meaning | Why invalid | Canonical replacement |
|---|---|---|---|---|
| `final_R` | Phases ≥2.5 (2.5, 2.6, 2.6B, 2.7A trade CSVs) | Highest target rung touched at any point before stop | Oracle/hindsight credit; not realizable by any exit rule; inflated Mean R ~4-5× vs best implementable exit | `realized_R@<policy>` under ONE declared exit policy (FIXED_R_100/150/200/300, ABS_50/75/100BP) |
| `A_hit_10/15/20/30`, `B_hit_*` | Phase 2.6B / 2.6 CSVs | MFE-reached-rung booleans | MFE-based; conflates excursion with exit | `exit_reason` per policy + `time_to_target` diagnostics |
| Unlabeled "Mean R" | Phase reports 1.8→2.8 | Ambiguous aggregate | Mixed policies/rungs; Phase 2.8 report A quoted values like "Mean R 10.49" that are bps-scale, not R | `mean_R@<policy>` and `net_bps_per_trade` (always tagged GROSS/NET) |
| Sums of net-R in RESULTS.json | Phase 2.2 (`-20.90/-24.88/-28.86`) | Σ over 121 trades | Read as per-trade expectancy (≈ -0.17…-0.24 R/trade actual) | Report per-trade mean; label any sum `SUM_` explicitly |
| Close-based stop backtests | exp_013/014, Phase 2.x TV line | Stop only if candle CLOSES through | Forgiving fills; 12 of 46 winners survived sub-stop wicks (+34.5R artifact) | Touch-based stops with gap-at-open fills (canonical execution.py) |
| WR@kR across different stops | Phase 2.6 stop zoo | "Same R" comparisons | Denominators differ up to 8× (110bp vs 13.5bp targets) | Mandatory common absolute targets (ABS_50/75/100BP) alongside R |
| MFE-as-expectancy | Pre-2.8 phases | Floating profit credited as P&L | Already acknowledged invalid in Phase 2.8 correction | MFE/MAE = UNREALIZED DIAGNOSTIC ONLY |
| `E` stop candidate (min 0.5 ATR) | Phase 2.6 | Separate architecture | Bit-identical to A on this data (never binds) | Removed from consideration space |

## 2. Deprecated conventions

| Convention | Status | Canonical rule |
|---|---|---|
| Stop = close-beyond | BANNED | Stop = touch (low≤stop / high≥stop); gap fills at bar OPEN |
| Target = close-beyond | BANNED | Target = touch, symmetric with stop |
| Same-candle ambiguity = engine-specific | BANNED | STOP_FIRST (conservative, spec A1) |
| Signals regenerated ad hoc per experiment | BANNED | One canonical signal ledger; experiments reference signal_id |
| Holdout reused for selection | BANNED | Burn-on-use; Partition Access Registry (holdout already burned pre-2.9) |
| Unlabeled gross/net mixing | BANNED | Every metric tagged GROSS or NET; funding always NOT_MODELED marker |

## 3. Historical phase classification (spec §24.2)

| Conclusion | Classification |
|---|---|
| ML-track economic rejections (Phases 5.x-8.x) | STILL VALID |
| Supertrend/VWAP indicator mathematics | STILL VALID (100% parity verified vs vendor lines, 1bp tolerance) |
| 121-signal baseline as definitional reference | STILL VALID as reference; provenance of its factor-4 series UNRESOLVED (SPEC-GAP S3) |
| Factor 3 vs 4 selection | INCONCLUSIVE → REQUIRES RECOMPUTATION |
| Risk ≤ 0.60% filter | INVALIDATED |
| Separation filter | INVALIDATED |
| VWAP-slope filter | INVALIDATED (constant) |
| ATR-0.50 SHORT advantage | INVALIDATED (measurement artifact) |
| Stop-architecture ranking (Phase 2.6 family) | REQUIRES RECOMPUTATION |
| Phase 2.6C common-target results | REQUIRES RECOMPUTATION (method sound, fills legacy) |
| Phase 2.7 entry-quality feature deltas | DIAGNOSTICS PROVISIONAL |
| Phase 2.8 directional filters | REQUIRES RECOMPUTATION on larger data |
| All prior holdout confirmations | HOLDOUT_BURNED |
