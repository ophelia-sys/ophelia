# OPHELIA — PHASE 2.9 MASTER SPECIFICATION
# CANONICAL BACKTEST ENGINE & EXECUTION ACCOUNTING REBUILD

Spec version: 1.0-draft-for-implementation
Date: 2026-08-22
Author: OX-alpha (quantitative architecture) · Implementer: AG · Auditor: OX (second-stage)
Status: SPECIFICATION ONLY — DO NOT IMPLEMENT UNTIL APPROVED, DO NOT USE FOR STRATEGY SELECTION

---

## 0. SCOPE AND NON-GOALS

Phase 2.9 rebuilds the measurement layer only. It answers exactly one question:

> "If Ophelia generates a signal, exactly how is that trade represented, executed,
> exited, accounted for, and evaluated?"

NON-GOALS (hard prohibitions for this phase):
- No filter discovery, no parameter search, no factor optimization, no new trading rules.
- No modification of historical reports or CSVs. Legacy artifacts are frozen as-is.
- No VPS, deployment, Telegram, or live-trading changes.
- No claims about which strategy is best. Phase 2.9 produces NO strategy verdicts.

Locked design decisions are labeled **[Dn]**. AG implements them verbatim; changing a
[Dn] requires a new spec version and OX re-audit.

---

## 1. OBJECTIVES

O1. ONE canonical signal ledger (`OPHELIA_CANONICAL_SIGNAL_LEDGER.csv`) that every future
    experiment consumes by reference. Signals are never silently regenerated.
O2. ONE deterministic execution/exiting/accounting engine producing
    `OPHELIA_CANONICAL_TRADE_LEDGER.csv` with unambiguous fills.
O3. Touch-based, exchange-realistic stop AND target conventions, symmetrically applied.
D1  Explicit same-candle ambiguity policy: STOP-FIRST (conservative).
O4. Separation of GROSS vs NET (fees/slippage explicit, funding explicitly NOT MODELED).
O5. Unambiguous R accounting: R frozen at entry from theoretical entry and stop;
    every R metric names its exit policy. Common absolute targets mandatory alongside R.
O6. Metrics standard (§15) incl. ESS and day-block bootstrap CIs.
O7. Reproducibility: committed code/config/dataset hashes/seeds; byte-identical reruns.
O8. Fail-closed integrity gates and baseline invariants.
O9. Research governance: hypothesis registry, hypothesis caps, holdout burn-on-use registry.
O10. Legacy reconciliation: deprecated-metric mapping and historical-phase classification.

ACCEPTANCE ANCHOR D2: On dataset DS-A (BingX SOLUSDT.P 5m, TradingView export,
2026-07-03 → 2026-08-21) with Supertrend(10, factor 4.0) and the §4 signal definition,
the canonical engine MUST reproduce exactly the historical baseline of 121 signals
(58 LONG / 63 SHORT) matching Phase 2.1/2.8 baselines. Any mismatch blocks Phase 2.9
completion until the definitional discrepancy is resolved and documented.

---

## 2. DATA CONTRACT

### 2.1 Sanctioned datasets

| ID | Name | Venue/Source | Symbol | TF | Window | Role |
|----|------|--------------|--------|----|--------|------|
| DS-A | BINGX_SOL_5M_TV_2026H2 | TradingView export of BINGX:SOLUSDT.P | SOLUSDT | 5m | 2026-07-03 → 2026-08-21 | Continuity/reference set (acceptance anchor D2) |
| DS-B | PARQUET_SOL_5M_2022_2023 | Repo `data/processed/v2_fixed_timestamp/SOLUSDT.parquet` (Binance-derived research corpus) | SOLUSDT | 5m | 2022-01-01 → 2023-12-31 | Primary statistical sample going forward |

Rules:
- No other dataset may feed a canonical ledger without a new dataset ID and manifest.
- DS-A raw export currently lives OUTSIDE the repo. Ingestion procedure (mandatory):
  1. Copy the raw export verbatim into `research/data/raw/tv_exports/<DS-A>.csv`.
  2. Record SHA-256, row count, first/last timestamp in the manifest (§2.2).
  3. Convert to canonical Parquet via a COMMITTED script; never edit the raw file.
  4. From then on, experiments read ONLY the canonical Parquet, never the raw CSV.

### 2.2 Dataset manifest (JSON, one per dataset version)

Required fields:
```
dataset_id, version (e.g., DS-A.v1), venue, source_description,
symbol, timeframe, timezone ("UTC"),
first_candle_open_time, last_candle_open_time, candle_count,
missing_candle_count, duplicate_timestamp_count, invalid_ohlc_count,
zero_volume_bar_count, volume_available (bool),
raw_export_filename, raw_export_sha256,
canonical_parquet_filename, canonical_parquet_sha256,
ingestion_script_path, ingestion_git_commit, created_utc
```

### 2.3 Canonical candle schema (Parquet)

| column | type | notes |
|---|---|---|
| candle_open_time | int64 ms epoch UTC | bar START |
| candle_close_time | int64 ms epoch UTC | = open_time + tf_ms |
| open, high, low, close | float64 | price units |
| volume | float64 | base units; may be 0 (see §3.1 guard) |

Timestamp convention D3: candles are identified by OPEN time. A candle "10:25" spans
10:25→10:30. `candle_close_time` is a derived convenience field; logic keys on open time.

### 2.4 Integrity gates (FAIL CLOSED — engine refuses to start on violation)

G1 Monotonic strictly-increasing unique candle_open_time (no dups, no out-of-order).
G2 Uniform 5m spacing; report every gap; gaps > 60 min are FATAL unless listed in an
   approved exceptions file inside the manifest.
G3 OHLC validity: high ≥ max(open,close); low ≤ min(open,close); all prices > 0; high ≥ low.
G4 No NaN/None in any column.
G5 Volume ≥ 0 (zero ALLOWED but counted; negative FATAL).
G6 Partial final candle: drop last candle if `last_open_time + tf_ms > ingest_now_utc`;
   log the drop in the manifest.
G7 Timezone: inputs must be UTC epoch or UTC-labeled; mixed naive/local timestamps FATAL.
G8 Duplicate-export check: manifest SHA-256 must match file hash at load time.
G9 Warm-up reserve: engine evaluates signals only after ≥300 bars (D4) from dataset start;
   bars consumed by indicators are excluded from signal eligibility and counted in audit.

---

## 3. INDICATOR CONTRACT

One implementation only (`research/canonical/indicators.py`). Experiments MUST import it;
re-implementations are prohibited. All formulas below are normative.

### 3.1 Session VWAP

```
tp_i      = (high_i + low_i + close_i) / 3
pv_i      = tp_i * volume_i
session_k = UTC calendar date of candle_open_time_i
VWAP_i    = sum(pv_j, j<=i, session_j == session_k) / sum(vol_j, same set)
```
- Reset boundary: first candle whose open_time UTC date differs from previous candle.
- Volume==0 guard D5: bars with volume==0 are EXCLUDED from both cumsums (numerator and
  denominator) but remain valid candles for OHLC logic. If an entire session has zero
  cumulative volume, VWAP is NaN for that session and signals requiring VWAP are suppressed.
- Causality note: VWAP_i includes bar i's own volume; legal because signals evaluate at
  bar-close time. No other lookahead exists.

### 3.2 True Range / ATR / RMA

```
TR_0 = high_0 - low_0                                  # first-bar fallback
TR_i = max(high_i - low_i, |high_i - close_{i-1}|, |low_i - close_{i-1}|)
RMA seed:  rma[L-1] = mean(TR[0..L-1])
RMA step:  rma[i] = (1/L)*TR_i + (1 - 1/L)*rma[i-1]
ATR = RMA(TR, L=10)                                    # Supertrend's ATR source, D6
```

### 3.3 Supertrend (length=10, factor F; current research reference F=4.0)

```
hl2_i        = (high_i + low_i) / 2
basicUpper_i = hl2_i + F * ATR_i
basicLower_i = hl2_i - F * ATR_i

finalUpper_0 = basicUpper_0 ; finalLower_0 = basicLower_0 ; dir_0 = +1
for i >= 1:
    finalUpper_i = basicUpper_i if (basicUpper_i < finalUpper_{i-1} or close_{i-1} > finalUpper_{i-1}) else finalUpper_{i-1}
    finalLower_i = basicLower_i if (basicLower_i > finalLower_{i-1} or close_{i-1} < finalLower_{i-1}) else finalLower_{i-1}
    if   dir_{i-1} == +1 and close_i < finalLower_i : dir_i = -1
    elif dir_{i-1} == -1 and close_i > finalUpper_i : dir_i = +1
    else                                            : dir_i = dir_{i-1}
activeLine_i = finalLower_i if dir_i == +1 else finalUpper_i
```
- Convention D7: internal `dir=+1` means bullish (line below price). Any Pine-imported
  series must be converted explicitly; polarity bugs are a known historical failure mode.
- Warm-up D4: indicators require ≥300 bars before the first eligible signal
  (ATR seed 10 bars × safety margin for band stabilization). Suppressed warm-up signals
  are counted in `OPHELIA_CANONICAL_AUDIT.md`, never silently dropped.
- Parity tests against `research/experiments/vwap_supertrend/indicators.py` outputs on a
  fixed fixture are REQUIRED (§22, T02/T03).

---

## 4. SIGNAL CONTRACT (canonical entry definition, locks acceptance anchor D2)

Let UP_i = activeLine_i when dir_i==+1 else NaN; DOWN_i = activeLine_i when dir_i==-1 else NaN.
Let V_i = VWAP_i. All values at candle i are known at `candle_close_time_i`.

LONG signal at candle i (all conditions required):
```
dir_{i-1} == +1 and dir_i == +1                       # line is the UpTrend on both bars
UP_{i-1} <  V_{i-1}
UP_i     >= V_i                                        # inclusive-at-touch semantics, D8
close_i  >  V_i
```
SHORT signal at candle i:
```
dir_{i-1} == -1 and dir_i == -1
DOWN_{i-1} >  V_{i-1}
DOWN_i     <= V_i                                      # inclusive-at-touch semantics, D8
close_i    <  V_i
```
Rules:
- S1 Both directions on one candle are impossible by construction; engine asserts this.
- S2 Any NaN among required inputs ⇒ no signal that bar.
- S3 Signals inside warm-up (§3.3) are suppressed and counted.
- S4 signal_time = candle_close_time of candle i. entry_time = candle_open_time of candle i+1.
- S5 Deterministic ID D9:
  `signal_id = {SYMBOL}_{TF}_{dataset_version}_{yyyymmdd_HHMM of open_time}_{LONG|SHORT}`
  e.g. `SOLUSDT_5M_DS-A.v1_20260703_1315_LONG`. IDs are unique by construction; duplicates abort the run.

Signal ledger row (one per signal): symbol, timeframe, dataset_version, signal_id,
signal_candle_open_time, signal_candle_close_time, signal_time, entry_time, direction,
signal_price (=close_i), theoretical_entry_price (=open_{i+1}), vwap_at_signal,
supertrend_line_at_signal, st_direction_at_signal, atr_at_signal, stop_price, risk_price,
risk_pct, regime_at_signal, ignored_reason (nullable).

---

## 5. ENTRY CONTRACT

D10: Theoretical execution = market order at next candle OPEN, exact price, no partial fills.
- theoretical_entry_price = open_{i+1}
- modeled_entry_price = theoretical_entry_price * (1 - s*10^-4) for LONG,
                        theoretical_entry_price * (1 + s*10^-4) for SHORT, where s ∈ {0,1,2} bps
  (slippage scenarios SLIP0/SLIP1/SLIP2; reported as separate cost scenarios, never mixed).
- GEOMETRY RULE D11: stop, risk, and all targets derive from THEORETICAL entry price so
  geometry is identical across slippage scenarios; slippage enters P&L only as a cost line.
- Edge case E1: if candle i+1 does not exist (end of data), signal status = UNFILLED_EOD,
  no trade row, counted in audit.
- Edge case E2: gap between signal close and next open is accepted as-is; the fill IS that
  open (no rejection rule in baseline).

---

## 6. STOP CONTRACT (primary executable convention)

D12 TOUCH-BASED STOPS (symmetric with targets; replaces all historical close-based variants):

Stop placement (frozen at signal time):
```
LONG  stop_price = supertrend_line_at_signal * (1 - 1e-4)    # Active UpTrend − 1 bp
SHORT stop_price = supertrend_line_at_signal * (1 + 1e-4)    # Active DownTrend + 1 bp
risk_price      = |theoretical_entry_price − stop_price|
risk_pct        = risk_price / theoretical_entry_price       # frozen for life of trade
```
Trigger & fill evaluation, per bar j from entry bar onward:
```
LONG:  triggered iff low_j  <= stop_price
       fill = open_j   if open_j  <= stop_price            # gapped through → fill at open
              else stop_price                               # touched intrabar → fill at stop
SHORT: triggered iff high_j >= stop_price
       fill = open_j   if open_j  >= stop_price
              else stop_price
```
- Entry bar IS eligible for stop (open precedes high/low within the bar; see §8 ordering).
- E3: LONG with open_j ≤ stop on the ENTRY bar itself (extreme gap): position opens and
  stops at the same open price → realized price return 0, fees still applied. Recorded,
  not filtered.
- Prohibited: "close must finish beyond stop" conventions; any MFE-derived stop credit.

---

## 7. TARGET CONTRACT

Symmetric touch-based model (same philosophy as stops, D13):
```
Target from R (k ∈ {1.5, 2, 3}):  target_price = theoretical_entry ± k * risk_price
Absolute targets (p ∈ {50, 75, 100} bps): target_price = theoretical_entry * (1 ± p*10^-4)
LONG:  triggered iff high_j >= target_price
       fill = open_j if open_j >= target_price             # gap up → better fill at open
             else target_price
SHORT: triggered iff low_j <= target_price
       fill = open_j if open_j <= target_price
             else target_price
```
Targets are static for the life of the trade. No trailing, no recalculation (baseline).
Every R-based number must name its policy: e.g. `mean_R@FIXED_R_150`.
Common absolute targets (§13/§16) are MANDATORY whenever two stop architectures are compared.

---

## 8. AMBIGUITY POLICY

Within-bar sequence assumption D14: `OPEN → {HIGH, LOW in unknown order} → CLOSE`.

A1 Same-candle stop AND target both inside range:
    resolve as **STOP FIRST** (conservative). Outcome = loss at stop fill rules.
    Bias: systematically understates performance. Quantified later via sub-5m overlay.
A2 Entry-candle exits: allowed (entry occurs at open; H/L occur after open under D14).
A3 Open beyond a level: gap rule (fill at open) takes precedence over touch rules.
A4 Open beyond BOTH levels: impossible for one side (stop and target lie on opposite sides
    of entry); engine asserts non-occurrence.
A5 If sub-minute/tick data later becomes available, replace A1 via config flag
    `ambiguity_policy = STOP_FIRST | TICK_ORDERED`; default remains STOP_FIRST.

---

## 9. POSITION STATE MACHINE

D15: ONE position at a time. No reversals, no pyramiding, no scaling in the canonical baseline.

States: `FLAT → ENTRY_PENDING → OPEN → STOPPED | TARGETED | CLOSED_EOD`

| Event \ State | FLAT | ENTRY_PENDING | OPEN |
|---|---|---|---|
| LONG/SHORT signal | → ENTRY_PENDING (order for next open) | record IGNORED_SIGNAL_PENDING | record IGNORED_POSITION_OPEN |
| Next bar opens | fill → OPEN (or UNFILLED_EOD) | — | — |
| Stop touched | — | — | → STOPPED (exit same bar) |
| Target touched | — | — | → TARGETED (exit same bar) |
| Stop AND target same bar | — | — | → STOPPED (policy A1) |
| Dataset ends | — | — | → CLOSED_EOD (censored) |

- ENTRY_PENDING resolves at the very next bar open; it never spans >0 bars in this engine.
- Signals arriving while OPEN or ENTRY_PENDING are WRITTEN to the signal ledger with
  `ignored_reason ∈ {POSITION_OPEN, SIGNAL_PENDING}` and excluded from the trade ledger.
  They are counted in the audit (coverage statistics), never silently discarded.
- CLOSED_EOD trades: excluded from realized metrics; included in diagnostics with
  `censored=true`; MFE/MAE reported over observed portion only.
- Terminal states are terminal: no exit event may follow STOPPED/TARGETED (invariant I4).

---

## 10. COST MODEL

D16 (configurable, defaults from measured BingX fills):
```
fee_rate_per_side_bps = 5.0          # measured: $253→$0.1269 (5.02bp), $88→$0.0444 (5.05bp)
slippage_scenarios_bps_per_side = {0, 1, 2}   # SLIP0 / SLIP1 / SLIP2
```
- Fees apply to notional at BOTH entry and exit: `round_trip_fee_bps = 2 × fee_rate_per_side_bps`.
- Slippage is a per-side adverse price adjustment (§5) reported as its own cost line.
- GROSS metrics exclude fees and slippage. NET metrics include both. Every metric row is
  tagged GROSS or NET. Hiding fees inside R is PROHIBITED.
- Funding is NOT part of the cost model (§11).

---

## 11. FUNDING MODEL

D17: `funding = NOT_MODELED`. All funding fields are null and every output carries the
literal marker `funding_status: NOT_MODELED`. Do NOT assume zero economic effect silently;
the audit must state: "funding drag unmodeled; avg holding ~5.5h ⇒ up to ~1 funding event
per trade unaccounted." A future funding overlay (external data join) is a spec v2 item.

---

## 12. P&L ACCOUNTING

Separate quantities, never mixed (per trade, per exit policy, per slippage scenario):
```
price_return_frac_gross = dir * (exit_price / entry_price_theoretical − 1)
slippage_cost_frac      = (s_entry + s_exit) * 10^-4            # from scenario
fee_cost_frac           = 2 * fee_rate_per_side_bps * 10^-4
price_return_frac_net   = gross − slippage_cost_frac − fee_cost_frac
```
Reporting layers (all derived, all labeled):
| layer | definition | use |
|---|---|---|
| price return (bps) | frac × 10^4 | PRIMARY expectancy unit |
| notional P&L ($) | frac × reference_notional (default $100) | convenience only |
| R | gross price return / risk_frac | risk-normalized view, policy-tagged |
| margin ROI (%) | frac × leverage (declared ref: 10x) | SECONDARY; never primary; never mixed into expectancy |

Reference sizing constants (reporting only): `reference_notional_usd = 100`,
`reference_margin_usd = 10`, `reference_leverage = 10`. They never affect signals, fills,
or primary metrics.

---

## 13. R ACCOUNTING

D18: `R = risk_price = |theoretical_entry_price − stop_price|`, frozen at entry.
`risk_frac = risk_price / theoretical_entry_price`.

- `realized_R@<policy>` = dir × (exit_price/theoretical_entry − 1) / risk_frac, defined
  ONLY under a named exit policy (FIXED_R_150, FIXED_R_200, FIXED_R_300, ABS_50BP,
  ABS_75BP, ABS_100BP).
- Outcome representation per policy: `WIN@kR | LOSS(−1R) | CENSORED`. One outcome per
  policy per trade. Combining rungs into one number is PROHIBITED (this bans the legacy
  oracle `final_R`; see §24).
- Breakeven arithmetic is mandatory output. With c = round_trip_cost_bps / risk_bps:
  `p*_breakeven(k) = (1 + c) / (k + c)`.
  Report p* for k ∈ {1.0, 1.5, 2.0, 3.0} × round-trip cost ∈ {0, 10, 12, 14, 16} bps,
  next to observed win rate, at portfolio level AND per risk-quartile.

---

## 14. MFE / MAE (UNREALIZED DIAGNOSTIC ONLY)

- Computed over the trade's OBSERVED life (entry bar → exit bar inclusive), from
  theoretical entry price. Never converted into realized P&L.
  `MFE_price = best favorable price seen; MAE_price = worst adverse price seen`
  plus `MFE_pct, MAE_pct, MFE_R = MFE_price/risk_price, MAE_R`.
- Censoring rule D19: winner MFE is censored at exit; loser MFE is not. Any comparison of
  winner-vs-loser excursions must state this asymmetry explicitly.
- Diagnostics are excluded from expectancy, profit factor, and every primary metric.

---

## 15. METRICS — CANONICAL STANDARD

Every metric tagged GROSS or NET and, where R-based, suffixed `@<policy>`. Primary
reporting policy: FIXED_R_150 (continuity); all policies reported side by side.

Primary (1–10):
1. net_bps_per_trade (primary metric of the entire program)
2. gross_bps_per_trade
3. profit_factor = Σwins / |Σlosses| (net)
4. median_net_trade_bps
5. max_drawdown_bps (chronological equity of net bps)
6. max_drawdown_R@policy
7. max_losing_streak
8. trades_per_week (+ trades/month)
9. exposure_time_pct = Σ trade durations / dataset span
10. net_return_per_exposure_hour

Secondary (11–20):
11. fixed-target hit rates per policy
12. mean_R@<single declared policy>
13. common absolute target hit rates (50/75/100 bp)
14. MFE diagnostics (§14) · 15. MAE diagnostics (§14)
16. time_to_target minutes (per policy, winners only)
17. time_to_stop minutes
18. regime-conditioned performance (≤4 buckets, §17)
19. ESS estimate (§16)
20. day-block bootstrap CI of net bps/trade (B=5000, seed=290719, blocks=1d and 7d)

---

## 16. EFFECTIVE SAMPLE SIZE

Mandatory outputs:
- n_trades; unique_days_with_trades; unique_weeks; calendar span days;
- trades/day histogram; max trades in any rolling 24h window;
- lag-1 autocorrelation of chronological outcome series (signed returns);
- ESS_AR1 = n × (1 − ρ)/(1 + ρ);
- day-block bootstrap CI (blocks of 1 day and 7 days) for net bps/trade and win rate.

Presentation rule D20: "n trades" may never be quoted as independent evidence without the
ESS line next to it.

---

## 17. REGIMES (≤4, predeclared, causal at signal close)

Computed from 5m data only (no new data dependencies), thresholds frozen in config:

| bucket | rule (evaluated in order) |
|---|---|
| TREND_UP | ret_24h ≥ +1.0% |
| TREND_DOWN | ret_24h ≤ −1.0% |
| HIGH_VOL | else, AND atr_pct_14 ≥ trailing-90d median of atr_pct_14 |
| CHOP | otherwise |

`ret_24h = close_i / close_{i−288} − 1`. Warm-up bars lacking 288-bar history ⇒ regime NULL
and that signal is ineligible for regime-stratified claims (still tradable).
Rule D21: direction-specific conclusions are ONLY stated within regime buckets; a "LONG
edge" claim spanning TREND_UP-only holdouts is invalid by construction.

---

## 18. OOS / WALK-FORWARD DESIGN

D22:
- Partitioning by CALENDAR WEEK blocks: DEV = first ~60% of weeks, VAL = next ~20%,
  HOLDOUT = final ~20%. Exact week boundaries recorded in config.
- The HOLDOUT is accessed EXACTLY ONCE per research cycle, then renamed HOLDOUT_BURNED.
- Append-only Partition Access Registry (`research/registry/partition_access_log.csv`):
  `timestamp_utc, experiment_id, partition_accessed, ledger_hash_at_access, purpose`.
- Multiple experiments share ONE holdout budget per data window; when burned, new data
  (time must pass) or explicit governance approval is required to designate a successor.
- Walk-forward rolling evaluation is permitted for robustness checks; selection decisions
  still use DEV/VAL only.

---

## 19. MULTIPLE-TESTING CONTROL

Research Registry (`research/registry/hypothesis_registry.csv`), append-only:
```
hypothesis_id, date_utc, phase, feature_or_rule, threshold_values,
dataset_id, split_used, primary_metric, result_value, decision(ACCEPTED|REJECTED|INCONCLUSIVE), reason, git_commit
```
Caps per research cycle (phase): **≤5 primary hypotheses + ≤5 pre-declared interactions**.
Exceeding caps requires closing the cycle and opening a new registered one.
Registry review is part of OX's second-stage audit; unregistered experiments are void.

---

## 20. REPRODUCIBILITY

Every canonical run emits `run_manifest.json`:
```
engine_version, spec_version, git_commit, git_dirty_flag,
dataset_id + dataset_sha256, config_sha256, bootstrap_seed(290719),
created_utc, output_file_hashes {ledger_csv, trades_csv, metrics_json}
```
Rules D23:
- Determinism test T20: two consecutive runs on the same inputs produce byte-identical
  CSV/JSON (hash equality). Any nondeterminism blocks completion.
- No stochastic operations anywhere except the seeded bootstrap.
- Config is a committed JSON; no hidden defaults; unknown config keys are FATAL.
- Python/pandas/numpy versions pinned in `research/canonical/requirements-lock.txt`.

---

## 21. BASELINE INVARIANTS (runtime assertions — FAIL CLOSED)

| ID | Invariant |
|----|-----------|
| I1 | entry bar index == signal bar index + 1 for every trade |
| I2 | stop side correct: LONG stop < theoretical_entry < all LONG targets; mirrored SHORT |
| I3 | 0 < risk_pct ≤ 5% for every trade (violations abort) |
| I4 | unique signal_id; every signal row has exactly one of {trade, ignored_reason} |
| I5 | at most one OPEN position at any time; no exit event after terminal state |
| I6 | fills respect bars: touch-fills equal level price; gap-fills equal that bar's open; never any price outside [low_j, high_j] of the triggering bar except documented gap rule |
| I7 | DS-A acceptance anchor: signal count == {total 121, LONG 58, SHORT 63} (D2); first/last signal timestamps match frozen reference once OX verifies run #1 |
| I8 | gross/net fields non-null for resolved trades; funding fields null with NOT_MODELED marker |
| I9 | dataset integrity gates G1–G9 passed before engine start |
| I10 | outcome per policy ∈ {WIN, LOSS, CENSORED}; exactly one per policy per trade; LOSS ⇒ realized_R == −1.0 exactly |
| I11 | regime bucket ∈ declared enum or NULL; NULL share reported |
| I12 | audit file lists counts: signals, suppressed_warmup, ignored_position_open, unfilled_eod, censored, resolved |

---

## 22. TEST SUITE (pytest, synthetic fixtures with hand-computed expectations)

| ID | Test | Fixture / expected |
|----|------|--------------------|
| T01 | VWAP session reset | 2-day series; day2 bar1 VWAP == tp(day2bar1) exactly |
| T02 | Supertrend band recursion vs legacy impl | fixture → columns identical to `vwap_supertrend/indicators.py` to 1e-12 |
| T03 | Supertrend flip rule | constructed series flipping at known bar k; dir[k]==−1, activeLine==finalUpper |
| T04 | Signal detection incl. inclusive-at-touch | UP crosses to exactly-equal VWAP with close>VWAP ⇒ signal fires (D8) |
| T05 | Next-open entry | entry_price == open[i+1]; entry_time == open_time[i+1] |
| T06 | Touch stop long | low<stop<open → fill==stop_price |
| T07 | Gap-through stop long | open<stop → fill==open (worse than stop) |
| T08 | Gap-through target long | open>target → fill==open (better), reason TARGETED |
| T09 | Same-candle stop+target | both inside range → STOPPED at −1R (policy A1) |
| T10 | Entry-candle stop | stop hit on entry bar itself → STOPPED, hold≈0 |
| T11 | E3 same-open entry+stop | open==stop boundary case → return 0, fees charged |
| T12 | End-of-data open position | CLOSED_EOD, censored=true, excluded from realized metrics |
| T13 | Opposite/same signal while open | recorded IGNORED_POSITION_OPEN; exposure unchanged |
| T14 | Fees & slippage math | net = gross − 2×5bp − scenario bps on $100 notional reference |
| T15 | R & target geometry | target_1.5R == entry ± 1.5×risk_price to 1e-12; risk_pct frozen |
| T16 | Absolute target | ABS_75BP triggers on touch; fill rules mirror stops |
| T17 | Short-side mirror | T05–T16 mirrored for SHORT |
| T18 | Integrity gate failures | dup timestamp, non-monotonic, invalid OHLC each raise and abort |
| T19 | Volume-zero VWAP guard | zero-volume bar excluded from cumsums; session all-zero ⇒ NaN VWAP |
| T20 | Determinism | two runs → identical SHA-256 outputs |

---

## 23. CANONICAL OUTPUTS

1. `OPHELIA_CANONICAL_SIGNAL_LEDGER.csv` — one row per signal (schema §4).
2. `OPHELIA_CANONICAL_TRADE_LEDGER.csv` — one row per taken trade × exit policy ×
   slippage scenario. Fields: signal_id, data_source(dataset_version), direction,
   signal_time, entry_time, entry_price_theoretical, entry_price_modeled, slippage_bps_entry,
   stop_price, risk_price, risk_pct, [exit_policy], target_price, exit_time, exit_price,
   exit_reason(STOP|TARGET), realized_price_return_gross_bps, fees_bps, slippage_bps_exit,
   realized_price_return_net_bps, realized_R@policy, pnl_notional_usd, margin_roi_pct(ref),
   funding_status(NOT_MODELED), MFE_pct, MAE_pct, MFE_R, MAE_R, time_to_target_min,
   time_to_stop_min, holding_minutes, regime_at_signal, censored.
3. `OPHELIA_CANONICAL_METRICS.json` — §15 metrics × {GROSS,NET} × policies × scenarios ×
   direction × regime + ESS block + breakeven table (§13).
4. `OPHELIA_CANONICAL_AUDIT.md` — human-readable run report: integrity gates, invariant
   results, suppression counts (warm-up, ignored, EOD), acceptance-anchor check, manifest.

---

## 24. LEGACY MAPPING & HISTORICAL CLASSIFICATION

### 24.1 Deprecated/invalid legacy metrics (do NOT use in new work)

| old metric | meaning | problem | replacement |
|---|---|---|---|
| `final_R` (Phases ≥2.5) | highest target rung touched | oracle/hindsight credit; not realizable | `realized_R@<single declared policy>` |
| `hit_10/15/20/30` flags | MFE-reached-rung booleans | MFE-based, mixed with exits | time_to_target + per-policy outcomes |
| unlabeled "Mean R" | ambiguous aggregate | mixed policies/rungs; sometimes bps mislabeled (Phase 2.8 report A: "Mean R 10.49") | `mean_R@<policy>` and `net_bps_per_trade` |
| sums of R in RESULTS.json | Σ per-trade net-R | misread as expectancy | label SUM explicitly; report per-trade mean |
| close-based stop backtests | stop only if candle closes through | forgiving fills; inflated winners (+34.5R artifact) | touch-based stops (§6) |
| WR@kR across different stops | win rate at "same" R | compares 8× different absolute distances | mandatory common absolute targets |
| MFE-as-expectancy (pre-2.8) | floating profit credited | already acknowledged invalid in Phase 2.8 correction | §14 diagnostics only |

### 24.2 Historical phase classification

| conclusion / phase | classification | note |
|---|---|---|
| ML track rejections (Phases 5.x–8.x: no net edge after costs) | STILL VALID | gross EV ≤ cost hurdle everywhere; methodology audited |
| Supertrend/VWAP indicator math | STILL VALID | verified Pine-equivalent, causal (OX audit 2026-08-22) |
| Signal definition & 121-signal baseline (2.1/2.8 parity) | STILL VALID as reference; REQUIRES RECOMPUTATION under canonical engine for all derived metrics |
| Factor 3 vs 4 selection | INCONCLUSIVE → REQUIRES RECOMPUTATION | both gross-negative at fixed targets; spread ≤1.1bps ≈ noise |
| Risk ≤ 0.60% filter | INVALIDATED | dev-only effect; failed holdout twice (2.0/2.2); resurrect-then-drop cycle |
| Separation filter | INVALIDATED | near-zero unique BAD coverage; overlaps risk width |
| VWAP-slope filter | INVALIDATED | constant (rejects zero trades) yet carried through 4 phases |
| ATR-0.50 SHORT advantage | INVALIDATED | R-denominator + wick-forgiveness artifact (−17R realistic) |
| Stop architecture ranking (Phase 2.6 zoo incl. C/D/E; E≡A duplicate) | REQUIRES RECOMPUTATION | R-denominator drift; baseline set drift (183 vs 121) |
| Phase 2.6C common-target comparisons | METHOD VALIDATED, RESULTS REQUIRES RECOMPUTATION | right idea; underlying fills/outcomes from legacy engine; scripts absent |
| Phase 2.7 entry-quality feature table | DIAGNOSTICS PROVISIONAL | descriptive diffs valid; outcomes need canonical re-score; n tiny |
| Phase 2.8 directional filters | REQUIRES RECOMPUTATION on larger data | accounting corrected by its own admission; holdout n=3–14 insufficient; holdout burned |
| V1.1 SOL walk-forward (+8.3bp net, 9 trades) | INCONCLUSIVE | n far too small; different entry def than TV-line |
| All prior holdout "confirmations" | HOLDOUT_BURNED | accessed repeatedly across 2.0→2.8 |

### 24.3 Legacy mapping document
AG must also emit `OPHELIA_LEGACY_METRIC_MAPPING.md` (content = tables above, expanded
with per-file examples). Historical reports themselves are NEVER edited.

---

## 25. RESEARCH GOVERNANCE

Roles:
- AG implements the engine exactly to this spec; raises SPEC-GAP issues instead of guessing.
- OX performs second-stage audit: reproduces ledgers independently, attacks outputs,
  verifies invariants/tests/determinism, signs off each gate below.

Completion gate (ALL twelve must pass):
1 signal ledger reproducible · 2 trade ledger deterministic · 3 exit convention implementable ·
4 ambiguity resolved explicitly · 5 gross/net separated · 6 R unambiguous · 7 absolute targets present ·
8 costs explicit · 9 ESS+bootstrap reported · 10 invariants pass · 11 tests pass · 12 OX audit pass.

Only after ALL twelve may strategy research resume (Phase 3.0), under registry caps and
holdout rules of §18–19.

---

## 26. ADVERSARIAL SELF-AUDIT OF THIS SPECIFICATION

| # | attack vector | residual risk | control |
|---|---|---|---|
| A1 | Future-info leak via indicators | LOW — VWAP includes own bar (legal at close); bands recursive causal | T02–T04; code-review checklist item: no `.shift(-…)`, no full-series normalization |
| A2 | Ambiguity reintroduced via gap rules | gap-fill-at-open is deterministic and bounded by bar extremes | I6 asserts fill ∈ {level, open} ∩ [low_j, high_j] logic; T06–T09 |
| A3 | Invisible R-denominator change | risk frozen at entry from theoretical entry | D11/D18; I3; geometry scenario-independent |
| A4 | Double credit of one move | one position max; ignored-signal records | state machine §9; I4/I5; T13 |
| A5 | Impossible fills in gaps | handled by explicit gap rule; E3 zero-return case documented | T07/T08/T11 |
| A6 | Holdout contamination | burn-on-use + access registry | §18 registry; OX audits access log |
| A7 | Multiple-testing false discoveries | caps + registry voids unregistered results | §19 |
| A8 | Two datasets silently producing different signals | dataset_version inside every signal_id + manifest hashes | G8; run manifest; acceptance anchor D2 pins DS-A |
| A9 | Unrealistic execution assumptions | slippage scenarios explicit but trigger levels remain theoretical | documented limitation: slippage-as-cost-line approximation; v2 upgrade path noted |
| A10 | Silent regeneration drift of the ledger | write-once ledgers + output hashes in registry; regeneration requires new version tag | D23; I7 |
| A11 | Regime buckets redefined mid-program to flatter results | thresholds are config-hash-pinned; changes require new registry entry | §17/D21 |
| A12 | Funding drag hidden | forced NOT_MODELED marker surfaces in every output | §11/I8 |

Residual known limitations (accepted, documented): 5m-bar granularity cannot order intrabar
events (A1 bias conservative); slippage modeled as linear cost not path-dependent fills;
funding unmodeled; single-symbol focus until DS-B expansion.

---

## WHAT PHASE 2.9 WILL MAKE TRUSTWORTHY

- A single, reproducible definition of "an Ophelia trade" from signal to net P&L.
- Exchange-realistic, symmetric stop/target fills with an explicit, conservative ambiguity policy.
- Honest accounting: gross vs net, fees visible, funding flagged, no oracle credit.
- Comparisons that cannot confuse target-size effects with stop-quality effects (absolute targets mandatory).
- Statistical honesty: ESS, clustering-aware bootstrap CIs, regime-stratified views.
- Governance that makes p-hacking visible (registry, caps, burned-holdout tracking).

## WHAT REMAINS UNKNOWN

- Whether ANY configuration of this entry has positive net expectancy (Phase 2.9 deliberately does not answer this).
- True intrabar ordering at 5m resolution (needs tick/sub-minute overlay).
- Actual funding drag, spread/slippage distribution on BingX at trade times.
- Whether DS-B (Binance-derived) signals transfer to BingX price reality (venue-parity study pending).
- Effective edge stability beyond the 50-day / 2-year windows currently available.

## WHAT HISTORICAL CONCLUSIONS MUST BE RECOMPUTED

Under the canonical engine, before any future use: factor 3-vs-4; stop-architecture rankings
(Phase 2.6 family); common-target stop comparison (2.6C); entry-quality feature deltas (2.7);
directional filters LONG Risk+ATR / SHORT Risk+ATR (2.8); all prior holdout confirmations
(burned). Already-invalid without recomputation: Risk≤0.60%, separation-only, VWAP-slope,
ATR-0.50 SHORT advantage. Still valid without recomputation: ML-track economic rejections;
indicator mathematics; the 121-signal baseline as a definitional reference.

## WHAT PHASE 3.0 SHOULD TEST AFTER THE ENGINE PASSES

(Outline only — design AFTER sign-off.) First candidate: re-run the existing frozen 10/4
baseline through the canonical engine on BOTH datasets to establish the honest gross/net
profile and breakeven table at adequate sample size; then ONE pre-registered hypothesis
family (e.g., trailing-exit variant H1 from the OX audit) tested under registry discipline.
No new filters, no factor tuning, before the first honest baseline numbers exist.

— END OF SPECIFICATION —





