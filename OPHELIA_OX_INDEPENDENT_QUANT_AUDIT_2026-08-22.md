# WHAT OPHELIA MAY HAVE GOT WRONG

**OX-ALPHA INDEPENDENT ADVERSARIAL QUANT AUDIT**
Date: 2026-08-22 07:12 UTC · Scope: VWAP/Supertrend research line (Phases 1.6–2.7A), ML-line accounting, methodology
Mode: READ-ONLY. No code, data, VPS, or configuration was modified. All new computations were performed on copies in a temp directory from repo CSVs.

---

## Executive verdict (one paragraph)

The deterministic VWAP/Supertrend line did **not** validly establish what works and what doesn't. Three measurement artifacts — an **oracle "highest-rung" exit metric**, an **asymmetric fill convention (targets on touch, stops only on close-beyond)**, and **R-denominator drift between compared architectures** — jointly manufactured the appearance of edge (+0.40 to +0.46 Mean R, "+12 bps net"). Recomputed under implementable conventions, the current thesis (10/4 baseline, Stop A LONG, ATR-0.50 SHORT) collapses: Stop A ≈ **−3.8 bps net/trade**, ATR-0.50 ≈ **−13.3 bps net/trade**, and every fixed-target variant sits below its fee-adjusted breakeven win rate. Separately, the sample (121 signals over 50 days, ESS≈67, one dominant regime) cannot statistically support the directional conclusions drawn from it. The prior *rejections* (filters, ML track) remain broadly sound; the recent *promotions* are not.

---

## 1. VERIFIED RESEARCH FINDINGS

Reconstruction performed from artifacts + independent recomputation of every headline number from `OPHELIA_PHASE26B_ALL_TRADES.csv` (121 trades), `OPHELIA_PHASE26_ALL_TRADES.csv` (183 rows), and `OPHELIA_PHASE21_ALL_TRADES.csv` (298 rows).

### 1.1 What is actually verified

| # | Finding | Status | Evidence |
|---|---|---|---|
| V1 | Supertrend implementation matches Pine canonical math (TR max of 3 terms, RMA seeded with SMA, band ratchet with prev-close reset, close-vs-band flips, active line = final_lower/upper) | VERIFIED | `research/experiments/vwap_supertrend/indicators.py:24–95`; recursion uses only bar-i and earlier data → no indicator lookahead |
| V2 | Session VWAP = typical price × volume, cumsum grouped by UTC calendar date; resets 00:00 UTC | VERIFIED | same file, lines 5–21; pinned by `tests/test_vwap_supertrend.py::test_session_vwap_reset` |
| V3 | Execution timing "signal candle close → next candle open" is consistently implemented where code exists (exp_013, exp_014, V1, V1.1); Phase 2.x CSVs carry distinct crossover_time vs entry_time exactly one 5m bar apart | VERIFIED | e.g. Phase2_1 row 1: cross 06:05 → entry 06:10 |
| V4 | BingX taker fee ≈ **0.05 % per fill** measured from the user's real fills ($253→$0.1269 = 5.02 bps; $88→$0.0444 = 5.05 bps; close $0.1793 ≈ 5 bps on ~$358 accumulated notional) | VERIFIED (arithmetic) | user-reported trade; consistent with BingX VIP-0 taker 0.05% |
| V5 | ML-track rejection is sound: every phase (5.1–8.1) gross EV ≤ +4.2 bps vs 12 bps friction; best locked-OOS top-decile net −7.79 bps | VERIFIED | `research/PHASE5_1_REPORT.md`, `PHASE5_3_REPORT.md`, `PHASE8_BACKTEST_REPORT.md`, RESEARCH_STATE.md |
| V6 | Filter candidates Risk≤x%, Separation≥x%, slope filters all failed holdout when honestly tested (Phase 2.0/2.2) | VERIFIED as tested | `PHASE2_2_RESEARCH_REGISTRY.csv`: all candidates REJECTED |
| V7 | Entry-failure dominance (Phase 2.6 Q18): most baseline losses never recover after stopping ("Original Stop Valid") | SUPPORTED | rescue tables: LONG 29/58, SHORT 21/53 still-loss under widest stops |
| V8 | Anti-chop Variant A ≥ B everywhere it was tested | SUPPORTED | V1.1 sweeps: B never selected |

### 1.2 What was *believed* but does not survive recomputation

| # | Prior claim | Reality |
|---|---|---|
| F1 | "Stop A Mean R 0.397 / +12 bps net" (Phases 2.5–2.6B) | Oracle-metric artifact → see §3.1; realizable exits give −15.7…−5.3 bps net |
| F2 | "ATR 0.50 SHORT advantage: Mean R 0.690 vs 0.325" (Phase 2.6B) | Denominator artifact + fill-convention artifact → §8; realistic fills: −17.0R total |
| F3 | "Factor 4 higher WR at every target" (Phase 2.1/2.3) | In absolute bps both factors are gross-negative at 1R/1.5R/2R; differences ±1 bps = noise → §8.3 |
| F4 | "LONG holdout edge (Mean R 0.89)" | n=14 trades, all inside the August rally leg → §10 |
| F5 | "Risk ≤0.60% improves LONG" | Dev-only; SHORT variant destroys more good (21) than bad (19); already failed holdout in Phase 2.2 → §7.2 |

---

## 2. METHODOLOGICAL PROBLEMS

### 2.1 Lookahead audit — indicators are clean; the *accounting* is not

- TR/RMA/band ratchet/flip logic: causal (verified line-by-line, V1 above).
- VWAP at bar i includes bar i's volume — known only at that bar's close; since signals evaluate at close and enter next open, this is causal. No hidden one-candle lookahead found in any indicator layer.
- exp_014's 200MA regime filter requires two completed 1h closes joined backward by evaluation time (`exp_014...py:132–164`) — correctly causal.
- Anti-chop features (ER, NES, nslope, BBS, RVOL, NATR, MRS) are rolling windows evaluated at signal-bar close — causal.
- **However**: the exit metric itself (`final_R`) embeds hindsight (§3.1). This is not indicator leakage, but it functions like lookahead in the P&L.

### 2.2 Signal-timestamp semantics

Consistent across the Python line: crossover candle close → next open. The TV-line CSVs confirm one-bar offset. **One unresolved case**: 81 of 121 Stop-B trades have `hold_time_mins == 0` — entered and resolved within the entry candle. How the engine ordered open-fill vs high/low touch within that single candle cannot be audited because the generating scripts for Phases 2.4–2.7A are absent from the repository (**NOT VERIFIED**). At Stop-B distances (~9 bps) this single-candle ordering decides nearly every trade.

### 2.3 Exit-definition changed mid-stream without announcement

Fixed-target evaluation (Phase 2.1/2.2: separate 1.5R/2R/3R outcomes) silently became highest-rung-reached credit (`final_R`) from Phase 2.5 onward. Identical phrase "Mean R" refers to different accounting before and after Phase 2.5.

### 2.4 Baseline drift across consecutive phases

| Phase | Signal set | Source |
|---|---|---|
| 2.0 / 2.2 / 2.4 / 2.5 / 2.6B | 121 (58L+63S), factor 4.0 | `OPHELIA_PHASE22_BASELINE_10_4.csv`, 2.6B file |
| 2.6 stop zoo | **183 (96L+87S)** — matches neither F3 (177) nor F4 (121) | `OPHELIA_PHASE26_ALL_TRADES.csv` |
| 2.7A factor comparison | 177 / 157 / 121 | report §1 |

The stop-architecture conclusions ("Stop A PROVISIONALLY VALIDATED") were drawn on a different signal set than the filter conclusions immediately before them. No changelog exists.

### 2.5 Execution model realism

- All backtests fill at exact next open, zero spread/slippage; no funding modeled (avg hold 328 min ⇒ ~0.7 funding events per trade).
- The dominant execution assumption is the stop convention: **close-based stops forgive intrabar wicks**. Swing impact quantified in §8.2: +34.5 R of the reported +48 R depends on winners surviving sub-stop dips.
- V1/V1.1 used the opposite (conservative, touch-based, gap-through-open handled) convention — so phases disagree on fill realism while sharing conclusions space.

---

## 3. METRIC PROBLEMS

### 3.1 THE BIG ONE — `final_R` is an oracle ladder, not a strategy outcome

Decoded from the joint distribution (audit script output):

```
final_R == 3.0  ⇔ hit_30 (33 trades)
final_R == 2.0  ⇔ hit_20 & !hit_30 (9+1)
final_R == 1.5  ⇔ hit_15 & !hit_20 (3+1)
final_R == −1   ⇔ no rung touched (75); losers' max MFE_R = 1.448 (< 1.5)
```

Every trade is credited with the **highest target rung it touched at any point before its stop**. No realizable rule produces this distribution:
- "Exit at first 1.5R touch": total = 46×1.5 − 75×1 = **−6 R** (−0.05 R/trade) — matches Phase 2.1's independently computed fixed-1.5R result.
- "Hold for 3R or stop": 33×3 − 88×1 = **+11 R** (+0.091 R/trade).
- Reported oracle ladder: **+48 R** (+0.397 R/trade).

A trader cannot sell the top without knowing it was the top. Phases 2.5, 2.6, 2.6B, 2.7A all report this oracle number as if it were expectancy.

### 3.2 Implementable fixed-target economics (Stop A geometry, 121 trades)

| Exit | Gross R/trade | Gross bps | Net @12 bps | Breakeven WR needed | Observed WR |
|---|---|---|---|---|---|
| Fixed 1.0R | −0.008 | −0.6 | **−12.6** | 55.9% | ~46%* |
| Fixed 1.5R | −0.050 | −3.7 | **−15.7** | 69.9% | 38.0% |
| Fixed 2.0R | +0.066 | +4.9 | **−7.1** | 53.8% | 35.5% |
| Fixed 3.0R | +0.091 | +6.7 | **−5.3** | 36.8% | 27.3% |
| Oracle ladder (reported) | +0.397 | +24.0 | +12.0 | — | — |

\* hit-flag approximation; see §8 caveats. **Every implementable exit is below fee-adjusted breakeven.** The project never once printed the breakeven-WR column.

### 3.3 R-denominator drift invalidates cross-architecture comparisons

"1.5R" means 110 bps for Stop A and 13.5 bps for Stop B(0.50). Win rates at "the same" R are win rates at **8× different absolute distances**. Mean-R comparisons compound this because the loss unit also differs 8×. Any table comparing Stops A/B/C/D/E on R metrics (all of Phase 2.6) mixes target-size effects with stop-quality effects. Correct comparisons must be made in common absolute units (done in §8).

### 3.4 Sums misread as expectancies

`PHASE2_2` RESULTS.json aggregates (−20.90/−24.88/−28.86) are **sums of per-trade net R over 121 trades** (≈ −0.17…−0.24 R each). Nothing in the file labels them as sums; they invite misquotation as per-trade figures.

### 3.5 Metric overemphasis

Reporting centers on Win-Rate-at-kR and Mean R. Never reported anywhere in the line: profit factor, net bps/trade, median trade, drawdown in account terms, return-per-hour, MFE-capture ratio, regime-stratified net expectancy, or effective sample size. §15 proposes the framework.

---

## 4. ACCOUNTING PROBLEMS

### 4.1 Basis check — margin ROI vs position P&L vs R

Good news: **no code path confuses margin ROI with position P&L.** All deterministic-line returns are unlevered price returns (`ret_pct = exit/entry − 1`, ×side); leverage appears only in `paper_broker` quantity sizing. The ML line likewise reports price-bps. The genuine accounting risks found:

1. **Costs omitted from the primary metric.** Phase 1.8–2.7A R-tables are gross; costs appear only in Phase 2.2 side-analyses and V1 cost-sensitivity grids. Headline claims therefore quote gross numbers.
2. **Flat 12 bps round-trip friction is now known to be fee-dominated, not slippage-dominated**: measured fees alone ≈ 10 bps round trip (V4), leaving ~2 bps for spread+slippage on taker market orders — optimistic. Sensitivity: at 16 bps friction, even the oracle-ladder net falls from +12 to +8 bps; at 20 bps, to +4 bps. Under implementable exits everything is negative at any plausible friction.
3. **Multi-fill drag ignored.** The user's live trade shows entries split into two fills plus a close (three fee events). Research assumes one entry + one exit; scaling-in multiplies fee load relative to the model.
4. **Fee/target ratio explodes for tight stops** (§4.2): this interaction — small risk × fixed fee — was never examined and is what kills ATR-fraction stops.

### 4.2 Target/fee ratio worked examples ($10 margin × 10 leverage = $100 notional)

| | Stop A trade (risk 0.737% = $0.74) | Stop B trade (risk 0.091% = $0.09) |
|---|---|---|
| 1.5R target gross | $1.106 | $0.137 |
| Entry + exit fees @0.05% | $0.100 | $0.100 |
| Net win @1.5R | **+$1.01 (+10.1% of margin)** | **+$0.037 (+0.37% of margin)** |
| Net full loss | −$0.84 (−8.4%) | −$0.191 (−1.91%) |
| Fee ÷ gross target | 9% | **73%** |

Generalization across actual trades: friction becomes dominant when avg risk ≲ 2× round-trip cost (≲ 24 bps here). At Stop-B scale the strategy is structurally a fee-donation program regardless of signal quality. **Where costs dominate:** any architecture whose stop distance is within ~2× the friction budget, and any holding pattern that adds fills (scale-ins, partials) without adding proportional target distance.

---

## 5. DATA PROBLEMS

1. **Three unbridgeable data sources** feed "the" strategy narrative:
 - Repo parquet (Binance-derived v2 dataset, 2022–2023): V1/V1.1 results.
 - Fresh Binance REST fetch (Jul 10–Aug 22, 2026): exp_014 only.
 - TradingView export of **BingX** SOLUSDT (Jul 3–Aug 21, 2026): Phases 1.6–2.7A — and the source file lives **outside the repo** (`C:\Users\dopa.mine\Pictures\BINGX_SOLUSDT.P, 5.csv`, referenced by `exp_019_loss_reduction.py:178`). The decisive recent phases are **not reproducible from version control**.
2. **Cross-venue OHLC divergence is unquantified.** Supertrend/ATR/VWAP values differ by a few bps between venues; at Stop-A widths (55–74 bps) tolerable, at Stop-B widths (9 bps) fatal. exp_014 already showed local-vs-TV trade-list mismatches (local systematically better).
3. **No generating scripts exist for Phases 1.6–1.8, 2.0, 2.2, 2.4, 2.5, 2.6, 2.6B, 2.7A.** Only outputs. Methodological details (intrabar rules, exact feature definitions) are unrecoverable except by inference from outputs.
4. Scratch candle cache covers only Aug 18–21, 2026 (1,001 bars) — insufficient for any re-audit of the full window without refetching.
5. Phase-numbering collision (ML-era EXPERIMENT_013/014 vs deterministic exp_013/exp_014) invites wrong-file citations in future audits.

---

## 6. LEAKAGE RISKS

- **Indicator leakage: none found** (§2.1).
- **Selection leakage: pervasive.** Dev→Val→Holdout discipline existed nominally, but the holdout block (25 trades) was evaluated repeatedly across Phases 2.0→2.7A (every candidate table includes a Holdout column). A holdout consulted ~30 times is dev data.
- **Post-hoc direction switching**: "Risk≤0.60% helps LONG, hurts SHORT" was derived from the same sample later used to propose direction-specific architectures.
- **Survivorship in reporting**: Phase 2.5 ships "Candidate A (Risk Only)" classifications as [TBD] while Phase 2.6 proceeds on a different baseline — the audit trail cannot show whether selections preceded or followed holdout inspection.
- **Oracle metric as implicit leakage**: crediting the best touched rung is equivalent to peeking at the future maximum (§3.1).

## 7. OVERFITTING RISKS

### 7.1 Research degrees of freedom

Counted hypotheses evaluated against essentially the same 121–183 signals:

| Phase | Candidate hypotheses |
|---|---|
| 1.9 loss reduction | ~15 filters |
| 2.0 TV-only | ~20 (incl. conditionals) |
| 2.2 registry | **67** |
| 2.4 forensics | 23 filters + pairwise grid |
| 2.5 | 4 architectures × 2 directions |
| 2.6 | 9 stops × 3 targets × 2 directions ≈ 54 cells |
| 2.6B / 2.7A | 2 + 3 factor configs |

Cumulative ≈ **150–200 hypotheses on ~121 trades** (dev n=72). With zero multiplicity correction, several "significant" dev results are expected by chance alone; observed holdout failures (everything rejected in 2.0/2.2) are exactly what multiplicity predicts.

### 7.2 The Risk ≤ 0.60% lifecycle (asked explicitly)

- Phase 1.9: selected as best dev filter (LONG WR 37→47%).
- Phase 2.0: three Risk-cap variants flagged PROMISING then **Failed Holdout**.
- Phase 2.2: all Risk caps REJECTED again.
- Phase 2.5: resurrected as "Candidate A"; LONG dev Mean R −0.01→+0.39; SHORT removes 19 BAD but **21 GOOD** (net harmful), yet carried forward anyway.
- Phase 2.6: dropped entirely (stop research ran without it).
Verdict: **never validated out-of-sample; repeatedly resurrected after failing** — textbook garden-of-forking-paths behavior. Separation/VWAP-slope/ST-slope add almost nothing beyond risk width (Phase 2.4 Jaccard: slope filters reject 0–12 trades; separation overlaps risk-width heavily; VWAP-slope rejects literally zero trades — it is a constant).

---

## 8. STOP/TARGET PROBLEMS

### 8.1 Fill-convention asymmetry discovered (material, previously unnoticed)

Winners whose path exceeded their own stop before winning:
- **Stop A: 12 of 46 winners (26%) had MAE ≥ 1.0R** (max 1.56R). Impossible under touch-based stops.
- **Stop B: 25 of 51 winners (49%) had MAE ≥ 1.0R** (max **5.54R**).

Conclusion: targets are credited on **touch** while stops fire only on **close beyond**. Losers' MAE min = 1.003R confirms stops bind at ~1R for losers. This asymmetry systematically converts would-be losses into winners. It also contradicts V1/V1.1's documented conservative convention — the two halves of the research line disagree on fill physics.

### 8.2 Path-dependency counterfactuals (Stop A, same 121 signals)

| Accounting | Total R | Per trade | Gross bps | Net @12 bps |
|---|---|---|---|---|
| Oracle ladder (as reported) | +48.0 | +0.397 | +24.0 | **+12.0** |
| Touch-based stops (winners with MAE≥1R become losses) | **+13.5** | +0.112 | +8.2 | **−3.8** |
| Fixed 3R-or-stop | +11.0 | +0.091 | +6.7 | −5.3 |
| Fixed 1.5R | −6.0 | −0.050 | −3.7 | −15.7 |

**+34.5 R of the reported edge — 72% — exists only because simulated stops forgive wicks.** With exchange-realistic stop-market fills, Stop A is gross-marginal and net-negative.

Same counterfactual for Stop B (ATR 0.50): oracle +55.5R → touch-based **−17.0R** (−13.3 bps net). Its entire apparent profitability is wick forgiveness on a 9-bp stop.

### 8.3 The "ATR 0.50 SHORT advantage" — artifact decomposition (asked directly)

Phase 2.6B SHORT: Mean R 0.690 (B) vs 0.325 (A). Decomposition:

| Quantity (SHORT) | Stop A | Stop B | Ratio |
|---|---|---|---|
| Avg risk (denominator) | 74.7 bps | 9.2 bps | 8.1× |
| Avg 1.5R **absolute** target | 112 bps | 13.7 bps | 8.2× |
| Avg **absolute** MFE | 101.7 bps | 16.7 bps | 6.1× |
| Gross expectancy (price bps) | **+28.1** | **+5.9** | A better |
| Net @12 bps | **+16.1** | **−6.1** | A better |
| Realistic fills (touch stops, whole book incl. LONG) | +8.2 gross | **−1.3 gross** | A better |

The B "advantage" exists only in R-units. In price units A dominates every row; under realistic fills B is deeply negative. **Answer: it is not a stop improvement — it is R-denominator shrinkage plus wick-forgiveness, i.e., a measurement artifact.** The same artifact affects the Factor 3.5 rescue table (Phase 2.7A "saved Mean R 2.29") and every B/C/D/E row of Phase 2.6.

### 8.4 Factor 3 vs 3.5 vs 4 — apples-to-apples?

Code-level: yes — identical function, single parameter changed. Metrics-level: no — the comparisons were made in R-space with drifting denominators (avg risk 55 / ~65 / 74 bps). Converted to common absolute terms (Phase 2.1 file):

| Config | 1.5R gross | 1.5R net@12 | 3R gross | 3R net@12 |
|---|---|---|---|---|
| 10/3.0 (177) | −2.1 bps | −14.1 | +3.0 | −9.0 |
| 10/4.0 (121) | −3.2 bps | −15.2 | +3.6 | −8.5 |

Both factors gross-negative at actionable targets; spread between them ≤1.1 bps — far inside noise. **The F3-vs-F4 question was never answerable with this sample, and neither option shows edge.** Factor choice is currently immaterial; treating it as decided (either way) is unsupported.

### 8.5 Static-ness check

Stops and targets are static per trade in the 2.x line (verified: targets = k × risk_pct recorded at entry; no recalculation). V1.1's milestone+trail is dynamic by design and documented as such. No hidden recalculation found.

---

## 9. ENTRY PROBLEMS

- Median loser MFE = 0.41R and loser MAE ≈ 1.10R: typical losing entry goes almost straight to stop. Typical winning entry absorbs 0.63R adverse before running. Entries do not display short-horizon momentum; the strategy's value (if any) lives entirely in the fat right tail (33 trades reached 3R+).
- 39% of consecutive signals re-enter the same direction within 12h — repeated exposure to the same move; "trade count" overstates opportunity count.
- The entry definition itself drifted three times (line-cross vs flip vs flip+close-confirm) — see prior forensic review; the TV-line entry (active-line cross) has never been tested under the corrected accounting of this report.

---

## 10. DIRECTIONAL ASYMMETRY

Structural metrics are near-symmetric (risk 0.727% vs 0.747%; MFE 101 vs 102 bps; MAE 67 vs 74 bps; hold 358 vs 301 min). The real asymmetry is **temporal**:

| Month | LONG meanR_A | SHORT meanR_A |
|---|---|---|
| July (n=31 L / 42 S) | +0.06 | **+0.54** |
| August (n=27 L / 21 S) | **+0.94** | −0.10 |

July chop favored shorts; the August rally (≈ +20% SOL) favored longs. Chronological Dev(Jul-heavy)/Val/Holdout(Aug-heavy) splits therefore confound direction with regime: "SHORT works in dev, LONG works in holdout" is one observation of regime beta, not two structural findings. Also notable: 9 of the 12 deep-dip winners (MAE≥1R) are SHORTs concentrated in July — whipsaw exposure is regime-dependent too. Current evidence does **not** support direction-specific stops or targets; it supports direction-specific *regime conditioning*, untested under honest accounting.

---

## 11. MFE/MAE FINDINGS (capture & timing)

- **Realization ratio** (realized/MFE): losers realize −1R on median MFE ≈ 0.45R (they give back nothing because there was nothing); winners exit exactly at rungs (ratio ≈ 1 by construction of the oracle metric). The informative stat is elsewhere:
- **Winners' uncensored potential**: 33 of 46 winners had MFE ≥ 3R; winner mean MFE 3.0R vs realized 2.4R average — fixed-rung exits leave the tail uncaptured, while the oracle metric pretends to capture it.
- **14 losers touched +1R before dying.** A break-even-after-+1R rule would have saved 14R — but would have killed 12 deep-dip winners worth 22.5R. Net −8.5R: **break-even stops hurt this entry population** (fragile-entry signature).
- **Time-to-move** (Phase 2.6 timestamps): Stop A median 142 min to reach 1.5R (mean 298); Stop B median **0 min** — same-candle resolution, i.e., B outcomes are decided by one candle's intrabar path, not by any tradable continuation property.
- MFE/MAE are computed off actual entry prices (consistent across files) ✓; but winner MFE is censored at the exit rung while loser MFE runs to the stop — asymmetric censoring that flatters winner MFE statistics in R-space.

---

## 12. EFFECTIVE SAMPLE SIZE

- 121 trades over **50 calendar days = 8 distinct weeks**; every day traded; max 5/day; median inter-trade gap 7.7h; 47/120 consecutive pairs same-direction within 12h.
- Lag-1 autocorrelation of outcomes: **+0.284** → AR(1) ESS ≈ **67**, before regime clustering, which pushes true ESS lower.
- Day-block bootstrap (5,000 draws) 95% CI of mean Stop-A R: **[0.05, 0.80]** — includes near-zero.
- Drawdown reality (chronological): max loss streak **11**, max drawdown **−11R** even under the flattering oracle metric.
- Split sizes: dev 72 / val 24 / holdout 25 (holdout = 14L + 11S). **No directional claim survives this n.** Conclusions requiring ±0.2R precision on mean R need roughly 10–30× the current data depending on clustering assumptions.
- Explicitly impossible with the current ~50-day dataset: factor selection, stop selection, direction-specific edges, filter validation, and anything about "robustness."

## 13. CURRENT THESIS AUDIT (adversarial challenge)

Thesis under examination: *"10/4 Supertrend, VWAP-active-line crossover, Stop A (ST±1bp) for LONG, possibly ATR-0.50 for SHORT."*

Attacks mounted, all successful:

1. **Metric artifact**: headline Mean R is an oracle ladder (§3.1). Realizable variants: −0.05…+0.09 R gross.
2. **Fill artifact**: 72% of reported R depends on close-based stop forgiveness (§8.2). Realistic fills: A +8.2 bps gross / **−3.8 net**.
3. **Short-side artifact**: ATR-0.50 SHORT advantage fully explained by denominator shrinkage + wick forgiveness; realistic fills → −17R total (§8.3).
4. **Regime confound**: LONG holdout edge = August rally on n=14; July favors SHORT (§10). Chronological holdout ≠ regime diversity.
5. **Statistical non-significance**: day-block CI spans near-zero; ESS≈67 (§12).
6. **Multiplicity**: ~150–200 hypotheses tested against one 121-trade sample; holdout reused dozens of times (§6, §7).
7. **Fee geometry**: at Stop-B scale fees consume 73% of the 1.5R target; at Stop-A scale breakeven WRs (54–70%) exceed observed WRs at every fixed target (§3.2, §4.2).
8. **Provenance**: decisive phases not reproducible (scripts missing; input CSV outside repo); baselines drift between phases (§2.4, §5).
9. **Counterexample search**: no hidden indicator lookahead found (that attack failed); no double-counting of overlapping trades found (single-position simulation); no fabricated data detected in CSVs (internal consistency checks passed — hit flags ↔ MFE ↔ final_R perfectly coherent, which is how the oracle rule was decoded).

**Result: the thesis is NOT supported by valid evidence.** Nothing here proves the entry lacks value; it proves the measurement system cannot currently tell.

## 14. FINDINGS THAT PREVIOUS RESEARCH MISSED

1. The oracle-ladder nature of `final_R` (undocumented, undetected since Phase 2.5).
2. The touch/close fill asymmetry and the 12 deep-dip winners carrying +22.5R.
3. Absolute-unit conversion reverses the ATR-0.50 conclusion and nullifies F3/F4.
4. Fee-to-target ratio scaling law (costs dominate when risk ≲ 2× friction).
5. Direction×regime confound embedded in the chronological splits.
6. Holdout burn-in through repeated consultation.
7. Baseline set drift (183 vs 121 signals) between adjacent phases.
8. Breakeven-win-rate arithmetic never surfaced (69.9% at 1.5R vs 38% observed).
9. Break-even-stop analysis proving entries are fragile rather than mis-stopped (BE rule nets −8.5R).
10. VWAP-slope filter is a constant (rejects zero trades) — it was carried through four phases as a "candidate."
11. `E` (min 0.5 ATR) stop is bit-for-bit identical to `A` on this data — the ST stop is always wider than 0.5 ATR; one of nine "architectures" was a duplicate.
12. Phase 2.6's own numbers contain the refutation of its R-based rankings (gross bps column shows B-family negative) — visible but unremarked.

## 15. REVISED METRIC FRAMEWORK (minimum reporting standard going forward)

Primary (per strategy config, per direction):
1. **Net bps/trade** after explicit per-side fee (5 bps measured) + declared slippage band (e.g., 0/1/2 bps scenarios).
2. Profit factor and median trade (net).
3. Max drawdown in R *and* in bps-of-price; max loss streak.
4. Trades/week, ESS (day-block bootstrap CI of net expectancy).
Secondary:
5. Outcome distribution (counts at −1R / partials / 1R / 1.5R / 2R / 3R+) under ONE declared, implementable exit.
6. Time-to-target curves (median minutes to +0.5R/+1R/+1.5R).
7. Regime-stratified expectancy (predeclared regime tags, ≤4 buckets).
8. MFE capture ratio under trailing policies; MAE percentile of winners vs losers.
9. Cost-dominance ratio: friction ÷ avg target distance; implied breakeven WR next to observed WR.
Formatting rules: one exit policy per table; common absolute targets when comparing stops; sums labeled as sums; every number tagged GROSS or NET.

## 16. HIGH-VALUE NEW HYPOTHESES (untested; few parameters; falsifiable)

| # | Hypothesis | Variable changed (rest frozen) | Mechanism | Falsifier |
|---|---|---|---|---|
| H1 | **Trailing exit captures the tail the rung system fakes** | Exit policy only (ATR-chandelier or VWAP-follow trail from entry) | Winner MFE averages 3.0R; trail monetizes what oracle credited | Trail net ≤ fixed-3R net on dev+val |
| H2 | **Touch-based restatement stands** | Fill convention only | If edge survives touch-stops + 10–16bps on reconstructed paths, prior work underestimated | Already largely falsified for current configs (−3.8 bps) |
| H3 | **Early-abort time-stop** | Add "exit at market if trade < −0.4R after N=3 bars" | Losers reveal themselves (loser MAE 1.14R vs winner 0.63R; median loser reaches stop fast) | Net improvement < 0 or unstable across weeks |
| H4 | **Regime-gated direction** (trade long only above rising 1h structure; short only below) using existing 200MA-two-close variable | One binary gate | July/Aug flip shows direction×regime dependence | Gate fails to improve day-block-bootstrapped net on both regimes |
| H5 | **Common-absolute-target geometry search** replaces R-multiple search: fix target ∈ {60,80,100} bps, stop ∈ {40,55,70} bps grid (12 combos, pre-registered) | Geometry only, on frozen signal list | Removes denominator illusion; tests whether ANY geometry clears costs | No combo positive net on val |
| H6 | **Separation-as-continuum**: expectancy monotone decreasing in \|entry−VWAP\|/ATR | Analysis variable only (no trading change) | Late/far crosses are exhausted moves | Non-monotone or flat relation |
| H7 | **Funding-drag materiality**: measure funding paid over 5h holds in trend legs | Data overlay only | Rally legs carry positive funding; longs bleed | Drag < 1 bp/trade → drop concern |
| H8 | **Venue parity bound**: quantify BingX-vs-Binance OHLC delta on overlap window | Data only | Determines which feed future tests must use; protects 9-bp-scale ideas | Delta > stop width → kill micro-stop concepts permanently |
| H9 | **Signal persistence**: require cross to survive 1 bar (confirm bar) | Entry timing only | False-flip cohort (54 F3-only flips) suggests noise crosses | Confirmed-entry net ≤ immediate-entry net |
| H10 | **Null calibration**: permutation test — randomize entry times within same days, preserve clustering | Statistical tool | Establishes the noise distribution of Mean R under this regime mix | (Calibration, no falsifier) |

Priority order: H2 (already done here — formalize), H5, H1, H3, H4. H8/H10 are cheap prerequisites for everything else.

## 17. PROPOSED PHASE 2.7 DESIGN — ENTRY QUALITY / REGIME CLASSIFICATION (do NOT execute yet)

**Question**: what conditions at the exact crossover distinguish continuation from immediate reversal?

**Prerequisites (blocking)**: (a) regenerate signal list from a scripted, committed pipeline (kill the outside-repo CSV dependency); (b) extend window OR switch to 2022–2023 parquet for n≥1,000 signals; (c) freeze accounting basis: touch-based stops, 5 bps/side fee + 1 bps slippage, next-open fills, ONE primary exit = fixed 2R with stop (secondary: H1 trail reported separately); (d) pre-register covariates and splits BEFORE looking at outcomes.

**Covariates measured at signal close (all causal)**: separation ÷ ATR; VWAP slope (1,3-bar, normalized by ATR); ST slope (1,3-bar normalized); signal-candle body/range ratio; range expansion (range ÷ ATR20); distance from session open; hour-of-day bucket (≤4 buckets); 1h regime state (two-close 200MA up/down/neutral); prior-24h return sign/magnitude; cross persistence (bars since ST direction established); RVOL bucket.

**Analysis protocol**:
1. Single chronological split 60/20/20 by WEEK blocks (not trade counts), holdout opened exactly once at project end.
2. Tercile/decile monotonicity of net expectancy per covariate, direction-specific, with day-block bootstrap CIs; require sign stability across ≥2 regime months before promotion.
3. Interaction screen limited to ≤5 pre-named pairs (e.g., separation×regime) — hard cap against multiplicity.
4. Deliverable: ranked covariate table with CIs; explicit "no covariate separates" outcome is an acceptable, publishable result.
5. Success criterion for the phase: ≥1 covariate with val net-bps spread > 2× bootstrap noise AND replicated in holdout. Anything less = entry quality is indistinguishable → pivot effort to exit engineering (H1) instead of more filtering.

## 18. FINAL CONFIDENCE ASSESSMENT — CURRENT OPHELIA STRATEGY

| Dimension | Rating | Reason |
|---|---|---|
| Data confidence | **LOW** | 50 days, one symbol, three inconsistent sources, key input outside repo, no scripts |
| Indicator confidence | **HIGH** | Supertrend/VWAP/ATR math independently verified correct and causal |
| Signal confidence | **LOW** | Three coexisting entry definitions; TV-line definition never validated end-to-end |
| Stop confidence | **LOW** | Close-vs-touch convention unresolved; results swing ±34.5R on it |
| Target confidence | **LOW** | Headline metric is an oracle; no implementable target shows positive net |
| Statistical confidence | **LOW** | ESS≈67, bootstrap CI includes zero, holdouts of n=11–25, ~200 hypotheses tried |
| Execution confidence | **LOW** | Zero spread/slippage/funding modeling; fee floor (10 bps) alone exceeds best realizable gross |
| Overall research confidence | **LOW** | Rejections are trustworthy; the single promoted architecture is not validated |

**Bottom line**: Ophelia's strongest demonstrated skill is rejection (ML track, filter grids) and its weakest is measurement. Before any further entry/stop/target optimization, rebuild the measurement layer per §15/§17 — otherwise the next ten phases will keep converting noise into narratives.

— END OF REPORT —
