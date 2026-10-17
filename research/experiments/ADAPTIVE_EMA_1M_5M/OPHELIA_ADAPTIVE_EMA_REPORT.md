# OPHELIA — ADAPTIVE EMA 1M/5M REPORT
Standalone hypothesis test · XRPUSDT perpetual · July 2026 (1 month) · Generated 2026-08-22

## Executive Summary

Three systems were compared on identical accounting: always-5m EMA9/20, always-1m EMA9/20,
and an ADAPTIVE system trading 1m signals only in classified 5m RANGE and 5m signals only
in classified 5m MOMENTUM (no new entries in TRANSITION). Over July 2026 every system was
gross expectancy-negative or flat (best single figure anywhere: 1m-only at 1:3, mean R
+0.010). The ADAPTIVE system improved win rate (30.2% vs 27.3% at 1:1) and cut trade count
by two-thirds versus 1m-only, but did NOT improve Mean R at any target. The user's core
observation was only partially supported: during RANGE, 1m beat 5m at 1:2 and 1:3 but LOST
to 5m at 1:1; during MOMENTUM the 5m system had only 3 entries, making H2 empirically
untestable this month. The regime classifier spent 57% of the month in TRANSITION and
switched states 1,462 times (~47/day), far more than the "persistent regime" design intent.

## Data and Methodology

- Symbol/venue: XRPUSDT perpetual, Binance USDⓈ-M `fapi/v1/klines`, 1-minute source,
  44,640 bars, 2026-07-01 00:00 → 2026-07-31 23:59 UTC; 8,928 5m bars aggregated from the
  same feed (open/high/low/close/volume-consistent).
- Indicators: EMA9/EMA20 seeded with SMA, computed independently per timeframe;
  regime features on 5m only: AvgMove20 (SMA20 of |Δclose|/prev), ER20, ATR20/ATR100 (Wilder).
- Regime rule (frozen, untuned): RANGE = AvgMove20 < causal rolling-median(288 bars) AND
  ER20 < 0.20; MOMENTUM = AvgMove20 ≥ rolling-median AND ER20 > 0.35; else TRANSITION.
- Interpretations forced by causality (documented in code header):
  - Entry: crossover confirmed at candle CLOSE, entry at NEXT candle open ("enter at the
    crossover candle's open" is look-ahead and impossible).
  - Stop: STATIC stop = OPEN of the most recent PAST opposite-direction crossover candle.
    The literal future reversal-candle open is retroactive; its causal analogue is the
    REVERSAL EXIT (opposite cross confirms at close U → exit at open[U+1]).
  - Targets 1:1 / 1:2 / 1:3 on frozen risk R = |entry − stop|; touch-based fills;
    same-candle stop+target resolves STOP-FIRST; gap-through fills at bar open.
  - Fairness F-1: ALL three systems execute on the SAME 1m stream; only the signal
    timeframe differs. Single position per system; duplicate crossovers impossible
    (event-based); regime change never force-closes an open trade.

## Run Verification and Disclosure of a Corrected Rerun

The first execution contained a data-plumbing bug (5m aggregation multiplied
already-millisecond timestamps by 300,000), which silently produced: 0 trades for 5M_ONLY,
100% "UNDEFINED" regime mapping onto 1m bars, and an ADAPTIVE system that blocked all
2,075 signals — i.e., corrupted outputs that could not answer H1–H3. Per protocol the bug
was fixed (one aggregation line + window constant Jul 2→Jul 1) and the IDENTICAL
pre-registered experiment re-executed once. No strategy, threshold, EMA, stop, or target
parameter changed. All numbers below come from the corrected run; consistency checks pass
(trade counts 3,223 = 474+2,080+669; JSON meta matches CSVs; regime distribution matches).

## Primary Comparison Table

| System | Trades | LONG | SHORT | 1:1 WR | 1:2 WR | 1:3 WR | Mean R (1:1) | Mean R (1:2) | Mean R (1:3) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m ONLY | 474 | 238 | 236 | 26.2% | 15.4% | 10.5% | −0.063 | −0.102 | −0.104 |
| 1m ONLY | 2,080 | 1,034 | 1,046 | 27.3% | 18.4% | 13.4% | −0.044 | −0.012 | +0.010 |
| ADAPTIVE | 669 | 335 | 334 | 30.2% | 20.3% | 14.9% | −0.053 | −0.023 | +0.003 |

Exit mix at 1:1 — 5m: 328 STOP / 124 TARGET / 21 REVERSAL / 1 EOD;
1m: 1,424 / 568 / 88; ADAPTIVE: 444 / 202 / 23. Median R = 0.000 everywhere
(median trade neither hits target nor is a full stop — dominated by reversal exits).

## Regime Distribution

| State | % of 5m bars | | Switches total |
|---|---:|---|---:|
| RANGE | 28.65% | | |
| MOMENTUM | 10.73% | | **1,462** (~47/day) |
| TRANSITION | 57.19% | | |
| UNDEFINED (warm-up) | 3.43% | | |

Classifier sanity: not degenerate (no single state dominates completely), BUT the switch
rate contradicts the design intent of persistent regimes — TRANSITION↔RANGE flickers on
short timescales because ER20/AvgMove hover near thresholds. This is a structural weakness
of the frozen rule set, reported not repaired.

## Regime Table (per system × regime; the pooled version would triple-count shared trades)

### 1m ONLY by regime
| Regime | Trades | 1:1 WR | 1:2 WR | 1:3 WR | Mean R (1/2/3) |
|---|---:|---:|---:|---:|---|
| RANGE | 666 | 30.3% | 20.4% | 15.0% | −0.053 / −0.023 / +0.003 |
| MOMENTUM | 156 | 21.8% | 14.1% | 8.3% | −0.015 / −0.014 / −0.044 |
| TRANSITION | 1,189 | 26.7% | 18.0% | 13.3% | −0.037 / +0.002 / +0.029 |

### 5m ONLY by regime
| Regime | Trades | 1:1 WR | 1:2 WR | 1:3 WR | Mean R (1/2/3) |
|---|---:|---:|---:|---:|---|
| RANGE | 236 | 30.9% | 17.4% | 14.0% | −0.006 / −0.080 / −0.034 |
| MOMENTUM | **3** | 0% | 0% | 0% | 0 / 0 / 0 |
| TRANSITION | 224 | 21.9% | 13.4% | 6.7% | −0.127 / −0.139 / −0.201 |

## Range-Regime Comparison (H1)

During classified RANGE: 1m mean R −0.053 vs 5m −0.006 at 1:1 (**5m better**);
at 1:2: 1m −0.023 vs 5m −0.080 (**1m better**); at 1:3: 1m +0.003 vs 5m −0.034
(**1m better**). Win rates nearly identical (30.3% vs 30.9%). → Mixed result: the
observation holds at wider targets only, and nothing is positive enough to matter.

## Momentum-Regime Comparison (H2)

Only **3** of the 5m system's 474 trades were entered during MOMENTUM (and ADAPTIVE took
exactly 3 five-minute entries all month). H2 is empirically **untestable** on this sample:
5m crossovers almost never coincide with the frozen MOMENTUM condition. Notably, the 1m
system's own MOMENTUM-tagged trades (n=156) performed WORSE than its RANGE trades —
opposite to the spirit of the hypothesis.

## Loss Analysis

| System | Loss rate (1:1) | Avg losing path | Median R | Streaks |
|---|---:|---|---:|---|
| 5m ONLY | 69.2% | full −1R stops dominate (328/474) | 0.000 | Not available from generated outputs |
| 1m ONLY | 68.5% | 1,424/2,080 full stops | 0.000 | Not available from generated outputs |
| ADAPTIVE | 66.4% | 444/669 full stops | 0.000 | Not available from generated outputs |

ADAPTIVE reduced the absolute number of losing 1:1 trades (444 vs 1,424 for 1m) purely by
taking fewer trades; loss RATE improved only marginally (−2.1 pts vs 1m-only).

## Causality Audit

Causal, post-bugfix: AvgMove20 uses trailing 20-bar diffs; its threshold is a rolling
288-bar median ENDING at the evaluation bar (a prior draft's full-month percentile WOULD
have leaked the future — replaced before implementation); ER20 uses close[t] vs close[t−20]
over the trailing path; ATR20/ATR100 are Wilder-recursions over past bars. Regime state is
computed on COMPLETED 5m bars and consumed by any 1m decision only after that 5m close,
so no future information enters classification or gating. Entries/exits use confirmation-
then-next-open timing throughout. The initial corrupted run (aggregation timestamp bug)
was mechanical, not informational leakage; corrected run is clean.

## Final Questions

1. Did 1m outperform 5m during RANGE? **Mixed** — no at 1:1, yes at 1:2/1:3 (margins ≈ +0.06/+0.04 R).
2. Did 5m outperform 1m during MOMENTUM? **Untestable** — only 3 overlapping trades.
3. Did ADAPTIVE outperform both? **No** — it beat 5m-only on most metrics but never beat plain 1m-only on Mean R.
4. RANGE share? **28.65%.**
5. MOMENTUM share? **10.73%.**
6. TRANSITION share? **57.19%.**
7. Regime switches? **1,462** (~47/day — excessive flicker).
8. Was ER20 useful? As the sole momentum discriminator it separated states but starved the
   MOMENTUM arm of trades (3 entries) — not demonstrated useful for this purpose.
9. Was AvgMove20 useful? Its causal rolling median produced a non-degenerate activity split;
   no evidence its RANGE pairing specifically selects where 1m beats 5m.
10. Did ATR20/ATR100 add anything? **Nothing measurable** — it gates nothing in the frozen
    rules and was carried as context only (per spec, kept but unused in classification).
11. Did ADAPTIVE reduce losing trades? Fewer losses in absolute count (444 vs 1,424); loss
    RATE only −2.1 pts vs 1m-only.
12–14. Improve 1:1 / 1:2 / 1:3? WR yes at all three (+2.9/+1.9/+1.5 pts vs 1m-only); Mean R
    **no** (−0.009 / −0.011 / −0.007 vs 1m-only).
15. Longer history? Only as a cheap falsification of the WR-vs-expectancy split — see below.

## Final Classification

- **5m ONLY: REJECTED** (expectancy negative at every target; worst TRANSITION behaviour).
- **1m ONLY: REJECTED** as a standalone system (gross-flat at best; deeply negative after
  realistic 10bp friction: net_meanR@1 ≈ −0.19 R-equivalent).
- **ADAPTIVE: INCONCLUSIVE** — genuine win-rate improvement with no expectancy
  improvement; cannot be called promising on one month, cannot be discarded on the
  mechanism alone.

## Limitations

One month, one symbol, one regime mixture; frozen untuned thresholds chosen a priori;
reversal-exit interpretation replaces the literal stop wording; no funding/slippage
modeling beyond the optional 10bp transparency column; MOMENTUM arm statistically empty;
high regime-switch rate means TRANSITION (no-trade) dominated the calendar.

## Recommendation for Next Experiment

Do not tune anything. If this line continues at all, the cheapest decisive test is a
longer-history rerun (≥ 12 months, same frozen rules) answering exactly two questions:
(a) does the RANGE-conditioned 1m edge at 1:2/1:3 persist, and (b) does the MOMENTUM arm
ever populate. If either fails, drop the adaptive concept without complication. Otherwise
the honest blocker remains: no configuration showed positive expectancy worth carrying
into execution research.

---

# 5m ONLY VERDICT

REJECTED — negative expectancy at all targets in all regimes this month.

# 1m ONLY VERDICT

REJECTED — gross-flat-to-negative; economically non-viable after friction despite the
mildest negatives of the three.

# ADAPTIVE VERDICT

INCONCLUSIVE — real win-rate/trade-frequency improvement, no expectancy improvement;
H2 untestable this sample.

# RANGE REGIME VERDICT

NOT CONFIRMED — RANGE did not reliably select conditions where 1m beats 5m (split
decision across targets); classifier flicker undermines its usefulness.

# MOMENTUM REGIME VERDICT

UNTESTED — the frozen definition almost never coincided with 5m crossovers (3 trades).

# MAIN FINDING

The adaptive concept changes WHERE trades happen (fewer, higher win rate) but not WHETHER
they make money: no system achieved positive gross expectancy, so regime selection over
two EMA timeframes rearranged losses rather than removing them.

# MAIN WEAKNESS

The regime model: TRANSITION dominance (57%) plus ~47 switches/day, and a MOMENTUM
definition that excludes virtually all 5m crossovers — the hypothesis's second half was
never actually exercised.

# SHOULD WE TEST LONGER HISTORY?

Only as a low-cost falsification with the SAME frozen rules (12+ months): continue solely
if the RANGE-conditioned 1:2/1:3 1m edge persists AND the MOMENTUM arm populates;
otherwise abandon the adaptive idea without further complication.
