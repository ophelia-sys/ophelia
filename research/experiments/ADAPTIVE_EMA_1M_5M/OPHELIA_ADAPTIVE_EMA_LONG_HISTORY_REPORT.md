# OPHELIA — ADAPTIVE EMA 1M/5M LONG-HISTORY VALIDATION
Frozen-rules replication · XRPUSDT perpetual (Binance USDⓈ-M) · Sep 2024 → Jul 2026 (699 days)
Generated: 2026-08-22 · Rules source: `exp_adaptive_ema_1m_5m.py` — UNCHANGED

## Executive Summary

The exact frozen one-month experiment was replicated on **23 months** (1,006,560 1m bars;
8,928→201,312 5m bars). The result is a clean falsification. The July RANGE advantage for
1m **reversed** on the full sample at every target. The MOMENTUM arm populated (53 five-minute
entries vs 3 before) and pointed the **wrong way** (5m far worse than 1m in MOMENTUM).
ADAPTIVE never beat plain 1m-only expectancy at any target and was negative in 7 of 9
quarters at 1:1. The regime classifier proved to be a persistent structural artifact:
median state duration 10–15 minutes, ~48 switches/day, every month for two years.
Per the pre-registered decision rule: **STOP — the concept is rejected.**

## Data & Replication Integrity

| item | value |
|---|---|
| window | 2024-09-01 → 2026-07-31 UTC |
| bars | 1,006,560 × 1m; 201,312 × 5m (aggregated from same feed) |
| EMA9/20 crossovers | 48,498 (1m); 9,902 (5m) |
| rules | identical module import (`exp_adaptive_ema_1m_5m.py`), zero parameter changes |
| accounting | close-confirm → next-open entry; prior-opposite-cross OPEN static stop; reversal exit next-open; touch fills; STOP-FIRST ties; all systems execute on the same 1m stream |

## Primary Table (frozen targets)

| System | Trades | LONG | SHORT | 1:1 WR | 1:2 WR | 1:3 WR | Mean R 1:1 | Mean R 1:2 | Mean R 1:3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m ONLY | 9,735 | 4,882 | 4,853 | 29.2% | 19.1% | 13.9% | −0.013 | +0.001 | **+0.022** |
| 1m ONLY | 47,646 | 23,806 | 23,840 | 27.5% | 18.6% | 13.4% | −0.042 | −0.006 | +0.010 |
| ADAPTIVE | 15,481 | 7,753 | 7,728 | 29.4% | 20.0% | 14.2% | −0.053 | −0.011 | −0.000 |

Risk: max losing streak / max drawdown (R @1x): 5m 17 / −158.7R · 1m 27 / −2,004R ·
ADAPTIVE 17 / −818.8R. Median R = 0 everywhere (reversal-exit dominated).

## H1 — RANGE Comparison (primary test)

| Metric | 1m in RANGE (n=15,428) | 5m in RANGE (n=4,695) | Difference (1m−5m) |
|---|---:|---:|---:|
| 1:1 WR | 27.9%* | 30.0%* | worse |
| 1:2 WR | 19.4%* | 21.0%* | worse |
| 1:3 WR | 14.2%* | 15.4%* | worse |
| Mean R 1:1 | −0.0523 | **−0.0018** | **−0.051** |
| Mean R 1:2 | −0.0108 | **+0.0226** | −0.033 |
| Mean R 1:3 | +0.0003 | **+0.0452** | −0.045 |

*WR values from system-level tables; per-slice WRs in `OPHELIA_ADAPTIVE_EMA_LONG_HISTORY_RESULTS.json`.

**The July pattern inverted.** With 15k+ paired observations, 5m dominates 1m inside
classified RANGE at every target. The one-month "1m edge at 1:2/1:3" was sampling noise.

## H2 — MOMENTUM Comparison

| Metric | 1m in MOMENTUM (n=3,728) | 5m in MOMENTUM (n=53) | Difference |
|---|---:|---:|---:|
| Mean R 1:1 | −0.0443 | **−0.1488** | +0.105 |
| Mean R 1:2 | −0.0098 | −0.2164 | +0.207 |
| Mean R 1:3 | +0.0143 | −0.2016 | +0.216 |

The branch is now populated (53 entries) and points the **opposite direction**: during
classified MOMENTUM, the 5m system performed dramatically *worse* than 1m. H2 is falsified.

## ADAPTIVE vs Fixed Systems

- vs 1m-only: worse Mean R at every target (−0.053 vs −0.042; −0.011 vs −0.006; −0.000 vs +0.010)
  while trading only 32% as often. Win-rate premium (+1.9 pts at 1:1) does not convert to expectancy.
- vs 5m-only: better at 1:1, worse at 1:2 and 1:3.
- Quarterly stability (adaptive mean R @1:1): negative in 7 of 9 quarters
  (best +? none positive at 1:1; @1:2 positive only 2025Q1/Q3; @1:3 mixed). No persistent
  favorable period exists.

## Regime Distribution & Classifier Health

Distribution is strikingly stable across 23 months — RANGE ≈ 29%, MOMENTUM ≈ 10.5%,
TRANSITION ≈ 60%, in every quarter (e.g., 2024Q3: 26.3/9.8/60.4; 2026Q2 similar). So the
one-month split was NOT an anomaly; it is what this rule set always produces.

But health is poor and constant: **~47.8 switches/day for two straight years**, median
state durations RANGE 15 min / MOMENTUM 10 min / TRANSITION 15 min. The classifier is not
detecting persistent regimes; it is banding short-horizon noise around fixed thresholds.
Measured only, as instructed — not repaired.

## Answers (§17)

1. Does 1m still outperform 5m in RANGE? **No — reversed.**
2. At 1:2? **No** (−0.033 R differential).
3. At 1:3? **No** (−0.045 R differential).
4. Economically meaningful magnitude? No; both sides remain gross-negative-to-marginal,
   deeply negative after friction.
5. Does 5m outperform 1m in MOMENTUM? **No — strongly reversed** (−0.149 vs −0.044 @1:1).
6. MOMENTUM sample sufficient? Yes (53 five-minute entries; conclusion directionally clear).
7. Does ADAPTIVE outperform both? **No.**
8. Advantage across periods? **No** — no quarter shows adaptive expectancy superiority.
9. Classifier stable/useful? Distribution stable, but state persistence is minutes, not
   regimes; **not useful as designed.**
10. Another stage? **No** — pre-registered stop condition triggered.

## Classifications

- LONG-HISTORY 5m ONLY: **INCONCLUSIVE** gross (+0.022 R @1:3 over 9,735 trades is the only
  non-negative figure; after 12 bp friction it is economically negative) → REJECTED for execution purposes.
- LONG-HISTORY 1m ONLY: **REJECTED**.
- LONG-HISTORY ADAPTIVE: **REJECTED** (decision rule §19: RANGE advantage disappeared).
- RANGE hypothesis: **REJECTED**. MOMENTUM hypothesis: **REJECTED**.
- Regime classifier: **REJECTED as a regime detector** (noise-banding artifact).

## Limitations

Single symbol; taker-cost-free primary metric (friction only worsens every verdict);
classifier thresholds frozen by design (no attempt to rescue via tuning, per §12/§19);
walk-forward blocks are descriptive, not significance-tested.

---

# LONG-HISTORY 5m ONLY VERDICT

INCONCLUSIVE gross, REJECTED economic — the least-bad variant (@1:3 +0.022 R gross),
still unviable after costs; nothing here justifies execution research.

# LONG-HISTORY 1m ONLY VERDICT

REJECTED — negative at 1:1/1:2, marginal at 1:3, with the worst drawdown of all (−2,004R).

# LONG-HISTORY ADAPTIVE VERDICT

REJECTED — pre-registered stop condition met: the RANGE advantage disappeared on the
larger sample and ADAPTIVE never improved expectancy over the simple 1m system.

# RANGE HYPOTHESIS VERDICT

REJECTED — 1m-under-5m-in-RANGE inverted sign across 15,428 vs 4,695 paired-regime trades.

# MOMENTUM HYPOTHESIS VERDICT

REJECTED — once populated (53 trades), 5m underperformed 1m in MOMENTUM by ~0.1–0.2 R.

# REGIME CLASSIFIER VERDICT

REJECTED AS DESIGNED — distribution stable but median regime life is 10–15 minutes at
~48 switches/day; it measures noise-banding, not market regimes.

# MAIN FINDING

The July signal was noise. On 23 months of XRPUSDT, timeframe-switching by this regime
classifier cannot produce positive expectancy: every architecture lands within a narrow
band of roughly −0.05 to +0.02 R per trade gross, and the classifier's minute-scale state
flips guarantee it gates nothing meaningful.

# MAIN WEAKNESS

The regime layer: with median state duration below three 5-minute bars, RANGE/MOMENTUM
labels re-randomize faster than any crossover trade can resolve, so the adaptive gate adds
selection bias without informational content.

# SHOULD EMA TIMEFRAME SWITCHING CONTINUE?

**NO.** Pre-registered criteria were tested on 23 months and failed on all three branches.
Stop this line without further complication.
