# OPHELIA — PHASE 2.9 IMPLEMENTATION REPORT
Canonical Backtest Engine & Execution Accounting Rebuild
Date: 2026-08-22 · Implementer: OX-alpha · Spec: `OPHELIA_PHASE29_CANONICAL_ENGINE_SPEC.md` v1.0

---

## FINAL STATUS

## FAIL — acceptance anchor unmet (external data-provenance cause; engine itself fully validated)

The DS-A acceptance anchor (121 signals / 58 LONG / 63 SHORT) is **unsatisfiable with
DS-A.v1 as archived**: forensic diagnosis proves the TradingView export carries
**Supertrend(10, factor 3.0) lines only**, while the 121-signal baseline was generated
from a **factor-4.0** series that exists in no archived artifact (SPEC-GAP S3).
Per spec §18 the definition was NOT altered to force a pass. Two resolution paths are
offered below; the engine passes immediately under path B.

---

## 1. What was built

```
research/canonical/
    __init__.py            constants (seed 290719, warmup 300, ref sizing, fee default)
    config.py              CanonicalConfig (frozen dataclass; unknown keys fatal)
    data_contract.py       raw-TV ingestion, gates G1-G9 (fail-closed), canonical CSV
                           store (deterministic float formatting), partial-candle drop
    indicators.py          THE single implementation: session_vwap / true_range /
                           atr_rma / supertrend / atr_pct  (all causal)
    strategies/base.py     SignalIntent · TriggerEvent (Model B) · TargetSpec ·
                           BaseStrategy  — strategy-agnostic contract (5-EMA-ready)
    strategies/vwap_supertrend.py  detect_active_line_crosses (pure §4 logic) +
                           VendorStrategy (DS-A) + EngineStrategy (warm-up enforced)
    execution.py           fills (touch/gap-at-open), STOP-FIRST ambiguity, per-policy
                           path resolution, SINGLE/MULTI position modes, TRIGGER entry
    accounting.py          gross/fee/slippage/net lines, R@policy, breakeven table
    metrics.py             §15 metric set (GROSS/NET tagged), ESS_AR1, day-block
                           bootstrap (B, seed, 1d/7d blocks), regime conditioning
    audit.py               regimes (4 causal buckets), invariants I1-I12, audit MD
    governance.py          hypothesis registry + partition-access log (append-only)
    runner.py              orchestration, canonical outputs, run_manifest.json
    acceptance_ds_a.py     DS-A acceptance CLI
    diagnose_anchor.py     §18 mismatch diagnosis (factor parity + variant counts)
    requirements-lock.txt  numpy 2.5.2 · pandas 3.0.5 · pyarrow 25.0.1 · pytest 9.1.1
    tests/                 T01-T20 + T21/T21b (22 tests, all passing, 0 warnings)
```

## 2. Locked decisions implemented verbatim

D1 STOP-FIRST ambiguity · D3 open-time candle identity · D4 300-bar warm-up
(ENGINE path) · D5 zero-volume VWAP guard · D7 internal dir=+1 bullish · D8
inclusive-at-touch cross · D9 deterministic signal_id · D10 next-open theoretical vs
modeled entry · D11 geometry from theoretical entry · D12 touch-based stops with
line±1bp and gap-at-open fills · D13 symmetric touch targets · D14 OPEN→{H,L}→CLOSE
ordering · D15 single-position baseline with recorded ignores · D16 fee 5bp/side +
slip {0,1,2}bp scenarios · D17 funding NOT_MODELED · D18 frozen R · D19 MFE censoring
rule · D20 ESS beside every n · D21 regime-gated directional claims · D22 weekly
partitions + burn-on-use registry · D23 determinism (content-addressed run_id).

## 3. DS-A acceptance results

| item | result |
|---|---|
| signals produced | **183 (96 LONG / 87 SHORT)** |
| anchor expected | 121 (58/63) |
| verdict | **I7 ANCHOR MISMATCH** (fail-closed, by design) |
| trades (SINGLE_POSITION, primary FIXED_R_150) | 134 taken · 49 POSITION_OPEN ignored · 0 UNFILLED_EOD |
| determinism | two full runs byte-identical: `096bcd0fc05e3ad45b7bcbb9f6ae93ad` |
| tests | 22/22 pass, 0 warnings |

### 3.1 Root-cause diagnosis (spec §18 procedure)

| probe | result |
|---|---|
| Engine ST(10,3.0) vs vendor `Up/Down Trend` | **100.0% of 7,639/6,565 overlapping bars within 1bp (mean diff 0.00000)** |
| Engine ST(10,3.5) vs vendor | 15.8% within 5bp — mismatch |
| Engine ST(10,4.0) vs vendor | 1.3% within 5bp — mismatch |
| Vendor VWAP session reset | resets at 00:00 UTC (98% of day-start bars == typical price) |
| §4 definition on vendor (F3) lines | **183 (96L/87S) — exact match to the historical Phase 2.6 signal set** |
| Historical 121-set (F4) | its source series is absent from DS-A.v1; the producing export was never archived |

**Conclusions:** (1) engine indicators are exact; (2) engine §4 signal logic is
independently cross-validated against an untouched historical artifact; (3) the anchor
failure is a DATA PROVENANCE gap, not an engine defect.

### 3.2 Resolution paths (user decision required)

- **A — Restore the specified anchor:** provide the original factor-4.0 TradingView
  export (the file that produced the 121/58/63 baseline). It is ingested as DS-A.v2 and
  the acceptance is re-run unchanged.
- **B — Amend D2 (spec v1.1):** re-anchor acceptance on what DS-A.v1 actually carries:
  **183 signals / 96 LONG / 87 SHORT @ Supertrend(10, 3.0)**, cross-validated against the
  Phase 2.6 artifact. The diagnostic run already demonstrates this passes exactly.
  Requires explicit user approval (changes a [D] decision).

## 4. Spec gaps raised (smallest-correction proposals, no silent changes)

| ID | Gap | Proposed correction |
|---|---|---|
| S1 | DS-A export has no pre-window history; first baseline signal sits at bar 3 → engine warm-up impossible | Add `indicator_source ∈ {VENDOR_PROVIDED, ENGINE_COMPUTED}` to signal ledger; vendor series consumed as DATA; engine implementation still mandatory + parity-tested |
| S2 | DS-A has no volume column | Canonical schema: volume nullable; volume-dependent paths disabled with manifest flag `volume_available=false` |
| S3 | Anchor factor-4 series not in any archived dataset | See §3.2 (user decision) |
| S4 | Spec E3 (entry-bar open beyond stop) is unreachable in Model A (entry == that bar's open; I2/I3 abort earlier) | Document E3 as Model-B-only case; Model-A equivalent = gap-through-stop on a LATER bar (implemented, tested T07/T11) |
| IN-1 | Canonical store as CSV (not Parquet) | Byte-deterministic hash chain for T20; schema identical |
| IN-2 | `run_id` content-addressed (dataset+config hashes) | Removes wall-clock from hashed artifacts; created_utc lives only in run_manifest.json |

## 5. Capability for the 5-EMA strategy (prepared, NOT implemented)

- **Model B intrabar triggers**: `TriggerEvent(price, direction, validity window)` with
  break-above/below fill rules — tested (T21, T21b).
- **Multi-timeframe signals**: `SignalIntent.signal_timeframe_minutes` independent of
  execution timeframe; engine executes on base candles only.
- **Overlapping positions**: `position_mode=MULTI_POSITION` — tested (T13).
- **Alert-candle stops / custom targets**: stop_price is strategy-supplied; custom target
  fractions via `TargetSpec.custom`.
- No EMA rules, no 5-EMA signals, no parameter choices were made anywhere.

## 6. Governance state

- Registries created: `research/registry/hypothesis_registry.csv` (empty),
  `partition_access_log.csv` — acceptance + determinism accesses logged with ledger hash.
- Pre-existing holdouts remain **BURNED**; nothing was restored or re-virginized.
- No historical phase was re-scored (§21 respected). No strategy verdicts produced.

## 7. Known limitations

1. Anchor blocked pending §3.2 decision (the only blocking item).
2. Secondary exit policies are PATH-INDEPENDENT estimates; only FIXED_R_150 drives the
   state machine (spec-consistent, labeled in outputs).
3. Regime HIGH_VOL/CHOP split uses an expanding median on DS-A (50d < 90d window) —
   flagged DEGRADED in audit notes.
4. Slippage modeled as linear cost lines, not path-dependent fills (spec-noted).
5. DS-A lacks volume → funding/VWAP-engine paths inactive on this dataset.

## 8. Artifacts

- Acceptance run: `research/canonical/output/ds_a_acceptance/` (ledger/trades/metrics/
  audit/run_manifest)
- Diagnostic F3.0 run: `research/canonical/output/ds_a_diagnostic_factor30/`
- Determinism pair: `research/canonical/output/ds_a_det_run{1,2}/` (identical hashes)
- Canonical dataset: `research/data/canonical/DS-A.v1_candles.csv` +
  `DS-A_v1_manifest.json`; raw preserved at
  `research/data/raw/tv_exports/DS-A_BINGX_SOL_5M.csv`
  (SHA-256 `23668626DF2A…F100A4F`)
- Legacy reconciliation: `OPHELIA_LEGACY_METRIC_MAPPING.md`

— END OF REPORT —
