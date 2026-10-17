# OPHELIA - EXCHANGE 10/4 INDEPENDENT VALIDATION REPORT
Phase 2.9B Â· Generated 2026-08-22 Â· Canonical engine UNMODIFIED (spec Â§22)

## 1. Scope and honesty statement
This is INDEPENDENT VALIDATION DATA ONLY: a fresh real-exchange test of whether
Supertrend(10, 4.0) + Session VWAP crossover mathematics behave consistently across two
venues. It is NOT a replacement for the missing historical factor-4 TradingView artifact,
and NOT a long-term robustness dataset (<= 2 months, single symbol, one regime mix).

## 2. Data
See `OPHELIA_EXCHANGE_DATA_PROVENANCE.md`. Summary: Binance delivered the complete
two-complete-month window (Jun 1 - Jul 31, 17,568 candles). BingX's official kline API is
depth-capped (~45 days); June is unavailable, so BingX delivers Jul 8 05:25 - Jul 31 23:55
(6,847 candles). Datasets were NEVER stitched or pooled.

## 3. Required comparison table
| Metric | BINGX | BINANCE | Difference |
|---|---:|---:|---:|
| Candles | 6847 | 17568 | BingX truncated by API depth |
| Missing candles (vs own grid) | 0 | 0 | - |
| Max Close diff | 0.0670 | - | see price parity |
| Mean Close diff (bps) | 1.19 | - | - |
| Max VWAP diff (bps) | 97.9 | - | engine-vs-engine |
| Mean VWAP diff (bps) | 9.76 | - | - |
| Max ST10/4 line diff (bps) | 170.4 | - | - |
| Mean ST10/4 line diff (bps) | 10.66 | - | - |
| LONG signals (full sample) | 23 | 63 | - |
| SHORT signals (full sample) | 31 | 65 | - |
| Signals in overlap window | 54 | 43 | - |
| Exact-matched signals | 15 (27.8% of BingX) | - | - |
| BingX-only (exact tol) | 39 | - | - |
| Binance-only (exact tol, overlap) | - | 28 | - |

Price parity (overlap, n=6847): mean |dOpen|=1.16bp,
|dHigh|=1.25bp, |dLow|=1.11bp,
|dClose|=1.19bp (max close 8.7bp).
Volume ratio BingX/Binance sum = 0.198.
The feeds are clearly NOT identical; typical close divergence is a few basis points.

## 4. Indicator reconstruction (engine-computed on each feed, no TV imports)
| indicator | n_overlap_bars | mean_abs_diff_bps | max_abs_diff_bps | pct_bars_within_1bp |
|---|---|---|---|---|
| ST10_4_active_line | 6838 | 10.659934169768686 | 170.42806553536616 | 2.2813688212927756 |
| session_vwap | 6847 | 9.757206433843184 | 97.94851792844456 | 15.846356068351103 |
| ST10_4_direction | 6847 |  |  | 92.4638527822404 |

- ST(10,4) direction agrees on 92.5% of overlap bars;
  active-line distance differs by ~10.7bp on average
  (max ~170bp) - material relative to 40-80bp stops.
- Session VWAP differs ~9.8bp mean (real volume weighting).

### TradingView diagnostic (NOT "TradingView parity")
On the Jul 8-31 overlap, BingX OHLCV fed through OUR engine reproduces the chart's
Supertrend(10, **3.0**) lines to mean 0.000016 bp
(max 0.0162 bp, n=3562).
This proves (a) our indicator implementation and (b) the BingX data pipeline reproduce
TradingView's published math essentially exactly. The archived TV file contains NO
factor-4 series, therefore "does 10/4 resemble the chart" is unanswerable by construction.

## 5. Cross-venue signal stability
| tolerance | matched | % of BingX(overlap base 54) | % of Binance-in-overlap (43) |
|---|---:|---:|---:|
| exact (same 5m bar) | 15 | 27.8% | 34.9% |
| +/-5m | 23 | 42.6% | 53.5% |
| +/-10m | 25 | 46.3% | 58.1% |
| +/-15m | 27 | 50.0% | 62.8% |

Crossover timing analysis (`OPHELIA_EXCHANGE_SIGNAL_TIMING.csv`): only
27.8% of BingX signals have a same-bar Binance twin; roughly half
are within +/-15 minutes. Venue-only signals are substantial on both sides.

## 6. Strategy results (canonical engine; touch stops; fee 5bp/side; SLIP0 primary path)

Headline (primary FIXED_R_150):

| Source | Trades | Gross BPSTrade | Net BPSTrade | WinRate | PF | MaxDD net bp | MaxLossStreak |
|---|---:|---:|---:|---:|---:|---:|---:|
| BINGX | ALL | 34 | -6.33 | -16.33 | 38.2% | 0.70 | -744.2 | 5 |
| BINANCE | ALL | 83 | 17.56 | 7.56 | 48.2% | 1.09 | -810.0 | 3 |

Fair same-window comparison (Jul 8 onward, primary path):
- BINGX: 34 trades, net -16.33 bp/trade, PF 0.703
- BINANCE: 27 trades, +13.41 bp/trade, PF 1.249

Per-direction x policy (resolved trades):
| Source | Direction | Policy | Trades | HitRate | NetBPSTrade | MeanR |
|---|---|---|---:|---:|---:|---:|
| BINGX | LONG | FIXED_R_100 | 17 | 47.1% | -28.58 | -0.059 |
| BINGX | LONG | FIXED_R_150 | 17 | 41.2% | -21.46 | +0.029 |
| BINGX | LONG | FIXED_R_200 | 17 | 41.2% | -9.26 | +0.235 |
| BINGX | LONG | FIXED_R_300 | 17 | 23.5% | -18.80 | -0.059 |
| BINGX | LONG | FIXED_R_500 | 17 | 11.8% | -44.96 | -0.294 |
| BINGX | SHORT | FIXED_R_100 | 17 | 41.2% | -16.50 | -0.176 |
| BINGX | SHORT | FIXED_R_150 | 17 | 35.3% | -11.20 | -0.118 |
| BINGX | SHORT | FIXED_R_200 | 17 | 29.4% | -13.82 | -0.118 |
| BINGX | SHORT | FIXED_R_300 | 16 | 18.8% | -20.69 | -0.250 |
| BINGX | SHORT | FIXED_R_500 | 15 | 6.7% | -55.81 | -0.600 |
| BINANCE | LONG | FIXED_R_100 | 44 | 47.7% | -27.68 | -0.045 |
| BINANCE | LONG | FIXED_R_150 | 44 | 38.6% | -25.23 | -0.034 |
| BINANCE | LONG | FIXED_R_200 | 44 | 36.4% | -7.71 | +0.091 |
| BINANCE | LONG | FIXED_R_300 | 44 | 27.3% | -1.92 | +0.091 |
| BINANCE | LONG | FIXED_R_500 | 44 | 20.5% | +6.86 | +0.227 |
| BINANCE | SHORT | FIXED_R_100 | 39 | 61.5% | +12.78 | +0.231 |
| BINANCE | SHORT | FIXED_R_150 | 39 | 59.0% | +44.55 | +0.474 |
| BINANCE | SHORT | FIXED_R_200 | 39 | 48.7% | +50.63 | +0.462 |
| BINANCE | SHORT | FIXED_R_300 | 37 | 27.0% | -2.15 | +0.081 |
| BINANCE | SHORT | FIXED_R_500 | 37 | 18.9% | +17.16 | +0.135 |

MFE tails: share of primary-path trades whose MFE reached 7R / 9R / 10R =
**0% / 0% / 0%** (BingX) and
**0% / 0% / 0%** (Binance):
no monster tails exist anywhere in this window under honest accounting.

## 7. Stop/target geometry by venue
| Stat | BINGX risk% | BINANCE risk% |
|---|---:|---:|
| mean | 0.770 | 1.371 |
| median | 0.689 | 1.258 |
| p25 | 0.505 | 0.887 |
| p75 | 0.986 | 1.601 |
| max | 1.559 | 3.173 |

Execution geometry is materially different across venues (Binance risks ~1.37% average
vs BingX ~0.77%): identical formulas do NOT produce identical trade geometry.

## 8. Findings
1. OX CAN reproduce Supertrend 10/x + session VWAP from raw BingX data (proven to
   chart-level precision on factor 3.0) - YES for factor 10/4 mechanics (same code path).
2. Same from Binance independently - YES.
3. Both exchanges generate SIMILAR BUT NOT MATCHING crossovers: direction agrees 92.5%
   of bars, yet exact-signal agreement is ~28% of BingX signals.
4. Signal timestamps are NOT sufficiently stable for venue-agnostic research claims.
5. Signal generation is NOT robust to venue differences: the same frozen rules produce
   POSITIVE net expectancy on Binance (+7.6 bp/trade full sample; +13.4 in overlap) and
   NEGATIVE on BingX (-16.3 bp/trade) - the venue actually intended for execution.

## 9. VERDICTS

# DATA QUALITY VERDICT
PASS WITH LIMITATIONS - both feeds clean internally (zero/near-zero gaps, valid OHLC);
limitation: BingX official API cannot supply June 2026 (45-day depth cap), so the primary
source covers only ~24 days of the mandated two months. Binance covers both months fully.

# BINGX 10/4 INDICATOR VERDICT
PASS - reconstruction verified against TradingView-published lines at chart precision
(via factor-3.0 identity) and internally consistent at factor 4.0.

# BINANCE 10/4 INDICATOR VERDICT
PASS - independent reconstruction clean over 17,568 candles.

# BINGX vs BINANCE SIGNAL STABILITY
WEAK - 28% exact / ~50% within +/-15m; both venues produce substantial venue-only signals.

# VWAP RECONSTRUCTION VERDICT
PASS - real-volume session VWAP implemented causally on both venues; cross-venue VWAP
diverges ~9.8bp mean purely from venue prices/volumes.

# SUPERTREND 10/4 VERDICT
IMPLEMENTATION VERIFIED; EDGE VENUE-DEPENDENT AND UNPROVEN. The mathematics are exactly
reproducible on both feeds; the trading behavior is not transferable between them.

# GROSS STRATEGY RESULTS
Gross/net per policy are tabulated in section 6 and
`OPHELIA_EXCHANGE_10_4_RESULTS.json`. Best net outcomes: Binance FIXED_R_200 +17.7bp/trade
(83 trades); BingX best is NEGATIVE (-13.5bp, FIXED_R_200). No policy is net-positive on
both venues simultaneously.

# DOES THIS RESOLVE THE MISSING 121-TRADE FACTOR-4 DATA?
**NO.**
This experiment establishes an independent, honestly-accounted 10/4 sample on fresh
exchange data - but the Phase 2.9 acceptance anchor is defined against the HISTORICAL
factor-4 TradingView baseline (121/58/63). That specific artifact still does not exist in
any archive. Exactly what is still required, either:
1. the ORIGINAL factor-4.0 TradingView export (the chart export that produced the
   121-trade baseline), ingested as DS-A.v2 and re-run through the unchanged acceptance
   procedure; or
2. an explicit user-approved amendment of spec decision D2 re-anchoring acceptance onto
   an engine-computable definition (e.g., the 183-signal factor-3.0 set already
   reproduced exactly, or a fresh anchor defined on these validated exchange feeds).

## Sample-purpose reminder (spec Â§14)
Two months, one symbol, one regime mix: nothing here may be quoted as long-term
robustness or as a strategy promotion/demotion.
