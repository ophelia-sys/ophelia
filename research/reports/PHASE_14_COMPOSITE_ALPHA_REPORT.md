# OPHELIA PHASE 14 — CONTROLLED MULTI-FACTOR ALPHA DISCOVERY REPORT

**Document ID**: `OPHELIA-RES-PHASE14-001`  
**Execution Timestamp**: `2026-10-18T22:07:22Z`  
**Engine Layer**: [`control_plane/phase14_composite_engine.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/phase14_composite_engine.py)  
**Governing Protocol**: [`docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md`](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md)  
**Pre-Registered Hypotheses**: $m = 10$  
**Safety Invariants**: `TRADING_AUTHORITY=False`, `EXECUTION_MODE=SHADOW`, `LIVE_ORDERS_FORBIDDEN=True`  

---

## 1. Executive Summary & Core Mandate Answers

| Mandate Question | Deterministic Empirical Finding | Evidence / Citation |
|---|---|---|
| **1. Did the composite experiment run to completion?** | **YES** | Processed 100% of 2023 (1,576,800 1m bars across BTC, ETH, SOL) and Q1 2024 (527,040 1m bars with Dec 2023 warm-up). Extracted 41,860 events, 334,880 forward trajectory outcomes, and 155,942 stop-room evaluations. |
| **2. Was the later data genuinely independent for this hypothesis family?** | **YES (Strictly Out-of-Time)** | Q1 2024 (`phase12_fresh_universe_1m.parquet`, SHA-256: `91de7196ace28474ef5fbeaa3c004e2df38b4c3658e451bd0d575b5e12060409`) was preserved untouched until candidate definitions and engine logic were frozen. Resampled with December 2023 warm-up to prevent initial-state bias, then filtered strictly for $T \ge \text{2024-01-01 00:00:00 UTC}$. |
| **3. Did any composite produce positive net expectancy after costs?** | **NO** | No candidate with adequate statistical sample size ($N \ge 30$) achieved positive net return after baseline 9.1 bps BingX friction across both TEST (2023) and OUT_OF_TIME_Q1_2024. In Q1 2024, every candidate with $N \ge 30$ produced negative net expectancy (ranging from $-0.98$ bps to $-24.46$ bps). |
| **4. Did any candidate satisfy the pre-registered statistical criteria?** | **NO** | Nominal significance on TEST occurred for `COMP_SFP_HTF_TREND` (raw $p = 0.0315$), but under Benjamini-Hochberg FDR control across the $m=10$ hypothesis family, its adjusted $q = 0.2950 \gg 0.05$. It subsequently failed out-of-time in Q1 2024 (gross dropped to $+3.59$ bps, net $-5.51$ bps). `COMP_DUAL_CONFLUENCE` had insufficient sample size ($N = 16$ in TEST, $N = 25$ in Q1 2024; both below the pre-registered $N \ge 30$ hurdle). |
| **5. Which candidate, if any, deserves fresh independent confirmation?** | **NONE** | No candidate cleared the double barrier of cost survival and multiple-testing significance. Promoting any tested candidate to production or live trading would violate empirical risk gating. |
| **6. What remains unverified?** | **Execution Realism for Passive Limit Orders** | Maker fee economics (5.0 bps round-trip) require passive liquidity provision. Fill rates, adverse selection, queue position, and cancel-replace dynamics cannot be verified without exchange order-book level 2 tick archives. |

---

## 2. Experimental Setup & Verification of Baseline

### 2.1 Baseline Reproduction (Phase 13 Consistency)
The Phase 13 standalone benchmark hypotheses were re-evaluated using the exact corrected research engine:
- `BENCH_HTF_ALIGNED_DISPLACEMENT` on 2023 TEST:
  - Phase 13 reported: **+5.83 bps gross, −3.27 bps net** (9.1 bps friction).
  - Phase 14 measured: **+5.83 bps gross, −3.27 bps net** ($N=898$). Exactly replicated to 0.01 bps.
- `BENCH_LIQUIDITY_SWEEP_SFP` on 2023 TEST:
  - Phase 13 reported: **+5.08 bps gross, −4.02 bps net** (9.1 bps friction).
  - Phase 14 measured: **+5.08 bps gross, −4.02 bps net** ($N=1337$). Exactly replicated to 0.01 bps.

### 2.2 Datasets & Partitioning Provenance
1. **2023 Universe**: `data/processed/binance_um_universe_1m_v2.parquet`
   - SHA-256: `d2e839edecfae88b798993cff9545fa626071efcb722f266fbe15e0bea3e20b5`
   - Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (525,600 1m rows per symbol, complete 60s step).
   - Features: OHLCV, `quote_volume`, `delta_v`, `aggressive_buy_volume`, `aggressive_sell_volume`.
   - Splits:
     - `TRAIN`: 2023-01-01 00:00:00 to 2023-07-31 23:59:59 UTC
     - `EMBARGO_1`: 2023-08-01 (24-hour purge)
     - `VALIDATION`: 2023-08-02 00:00:00 to 2023-10-14 23:59:59 UTC
     - `EMBARGO_2`: 2023-10-15 (24-hour purge)
     - `TEST`: 2023-10-16 00:00:00 to 2023-12-31 23:59:59 UTC
2. **Q1 2024 Out-of-Time Universe**: `data/processed/phase12_fresh_universe_1m.parquet`
   - SHA-256: `91de7196ace28474ef5fbeaa3c004e2df38b4c3658e451bd0d575b5e12060409`
   - Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (175,680 1m rows per symbol, 2023-12-01 to 2024-03-31 UTC).
   - Warm-up period: 2023-12-01 to 2023-12-31 UTC used solely for causal feature stabilization (4H EMA 50, 1H ATR, rolling statistics).
   - Evaluation partition: `OUT_OF_TIME_Q1_2024` strictly spanning 2024-01-01 00:00:00 to 2024-03-31 23:59:59 UTC ($131,040$ evaluated 1m bars per symbol).
   - Provenance note: Raw trade/order-flow columns (`delta_v`, taker volumes) are absent from this dataset. Consequently, `COMP_SFP_CVD_ABSORPTION` cleanly evaluated to 0 events and was gated closed on Q1 2024 as required by the protocol.

---

## 3. Comprehensive Results Table: Standalone vs Composite

All returns are directional 60-minute forward returns expressed in basis points (bps). Friction models applied:
- **Gross**: 0.0 bps
- **Net 5.0**: 5.0 bps round-trip (Maker 2.0 bps + Taker 5.0 bps / fee-only)
- **Net 9.1**: 9.1 bps round-trip (Ophelia verified baseline: 7.0 bps fee + 2.1 bps empirical slippage)
- **Net 15.0**: 15.0 bps round-trip (Taker 10.0 bps + 5.0 bps adverse slippage)

| # | Hypothesis Name | Partition | N Events | Win Rate | Gross Mean (bps) | Net 5.0 (bps) | Net 9.1 (bps) | Net 15.0 (bps) | Profit Factor | Raw p (6h) | FDR q | Decision Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | `BENCH_HTF_ALIGNED_DISPLACEMENT` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 2518<br>1053<br>**898**<br>1047 | 41.5%<br>42.4%<br>**48.0%**<br>49.2% | -2.36<br>+0.55<br>**+5.83**<br>+8.12 | -7.36<br>-4.45<br>**+0.83**<br>+3.12 | -11.46<br>-8.55<br>**-3.27**<br>-0.98 | -17.36<br>-14.45<br>**-9.17**<br>-6.88 | 0.92<br>1.03<br>**1.20**<br>1.25 | 0.4435<br>0.8595<br>**0.1890**<br>0.1320 | -<br>-<br>**0.3508**<br>- | `NO_EDGE_FOUND` |
| **2** | `BENCH_LIQUIDITY_SWEEP_SFP` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 3324<br>734<br>**1337**<br>1627 | 55.6%<br>55.5%<br>**55.1%**<br>53.9% | +0.37<br>-2.82<br>**+5.08**<br>+2.95 | -4.63<br>-7.82<br>**+0.08**<br>-2.05 | -8.73<br>-11.92<br>**-4.02**<br>-6.15 | -14.63<br>-17.82<br>**-9.92**<br>-12.05 | 1.01<br>0.88<br>**1.15**<br>1.09 | 0.8610<br>0.4345<br>**0.1180**<br>0.4065 | -<br>-<br>**0.2950**<br>- | `NO_EDGE_FOUND` |
| **3** | `COMP_SFP_HTF_TREND` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 1570<br>343<br>**627**<br>773 | 56.2%<br>56.9%<br>**57.7%**<br>55.9% | +2.54<br>+0.34<br>**+10.22**<br>+3.59 | -2.46<br>-4.66<br>**+5.22**<br>-1.41 | -6.56<br>-8.76<br>**+1.12**<br>-5.51 | -12.46<br>-14.66<br>**-4.78**<br>-11.41 | 1.09<br>1.02<br>**1.35**<br>1.12 | 0.3910<br>0.9430<br>**0.0315**<br>0.4080 | -<br>-<br>**0.2950**<br>- | `NO_EDGE_FOUND` |
| **4** | `COMP_SFP_RVOL_CONFIRM` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 2498<br>566<br>**900**<br>1027 | 55.8%<br>54.2%<br>**55.0%**<br>53.4% | -0.88<br>-3.86<br>**+0.85**<br>+0.79 | -5.88<br>-8.86<br>**-4.15**<br>-4.21 | -9.98<br>-12.96<br>**-8.25**<br>-8.31 | -15.88<br>-18.86<br>**-14.15**<br>-14.21 | 0.97<br>0.84<br>**1.03**<br>1.02 | 0.7170<br>0.3765<br>**0.8105**<br>0.8595 | -<br>-<br>**1.0000**<br>- | `NO_EDGE_FOUND` |
| **5** | `COMP_SFP_VOL_EXPANSION` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 3226<br>725<br>**1324**<br>1589 | 55.6%<br>55.4%<br>**55.1%**<br>54.1% | +0.33<br>-2.86<br>**+5.22**<br>+3.85 | -4.67<br>-7.86<br>**+0.22**<br>-1.15 | -8.77<br>-11.96<br>**-3.88**<br>-5.25 | -14.67<br>-17.86<br>**-9.78**<br>-11.15 | 1.01<br>0.88<br>**1.16**<br>1.11 | 0.8770<br>0.4285<br>**0.1105**<br>0.2675 | -<br>-<br>**0.2950**<br>- | `NO_EDGE_FOUND` |
| **6** | `COMP_DISPLACEMENT_RVOL` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 1807<br>647<br>**640**<br>748 | 41.5%<br>42.7%<br>**47.8%**<br>49.3% | -2.43<br>-1.33<br>**+5.73**<br>+6.97 | -7.43<br>-6.33<br>**+0.73**<br>+1.97 | -11.53<br>-10.43<br>**-3.37**<br>-2.13 | -17.43<br>-16.33<br>**-9.27**<br>-8.03 | 0.92<br>0.96<br>**1.18**<br>1.20 | 0.4905<br>0.7100<br>**0.3215**<br>0.3170 | -<br>-<br>**0.4593**<br>- | `NO_EDGE_FOUND` |
| **7** | `COMP_DISPLACEMENT_VOL_EXPANSION` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 629<br>238<br>**168**<br>182 | 41.0%<br>39.9%<br>**46.4%**<br>42.9% | -10.20<br>-12.83<br>**-0.37**<br>-15.36 | -15.20<br>-17.83<br>**-5.37**<br>-20.36 | -19.30<br>-21.93<br>**-9.47**<br>-24.46 | -25.20<br>-27.83<br>**-15.37**<br>-30.36 | 0.72<br>0.63<br>**0.99**<br>0.67 | 0.1060<br>0.1030<br>**0.9685**<br>0.2630 | -<br>-<br>**1.0000**<br>- | `NO_EDGE_FOUND` |
| **8** | `COMP_SFP_CVD_ABSORPTION` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 1360<br>349<br>**534**<br>0 | 55.4%<br>55.3%<br>**56.0%**<br>N/A | +0.03<br>-2.92<br>**+8.26**<br>0.00 | -4.97<br>-7.92<br>**+3.26**<br>0.00 | -9.07<br>-12.02<br>**-0.84**<br>0.00 | -14.97<br>-17.92<br>**-6.74**<br>0.00 | 1.00<br>0.89<br>**1.25**<br>N/A | 0.9915<br>0.4895<br>**0.0815**<br>1.0000 | -<br>-<br>**0.2950**<br>- | `NO_EDGE_FOUND` |
| **9** | `COMP_DUAL_CONFLUENCE` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 45<br>25<br>**16**<br>25 | 57.8%<br>72.0%<br>**68.8%**<br>64.0% | -0.79<br>+14.51<br>**+20.87**<br>+17.87 | -5.79<br>+9.51<br>**+15.87**<br>+12.87 | -9.89<br>+5.41<br>**+11.77**<br>+8.77 | -15.79<br>-0.49<br>**+5.87**<br>+2.87 | 0.97<br>1.56<br>**2.07**<br>1.66 | 0.9065<br>0.2790<br>**1.0000**<br>1.0000 | -<br>-<br>**1.0000**<br>- | `INCONCLUSIVE_INSUFFICIENT_SAMPLE` |
| **10** | `COMP_HTF_1H_SWING_SFP` | TRAIN<br>VAL<br>**TEST**<br>OOT 24 | 3176<br>750<br>**1298**<br>1517 | 55.5%<br>55.3%<br>**54.9%**<br>54.1% | +0.22<br>-6.61<br>**+4.55**<br>+4.11 | -4.78<br>-11.61<br>**-0.45**<br>-0.89 | -8.88<br>-15.71<br>**-4.55**<br>-4.99 | -14.78<br>-21.61<br>**-10.45**<br>-10.89 | 1.01<br>0.74<br>**1.13**<br>1.12 | 0.9255<br>0.0830<br>**0.2105**<br>0.3185 | -<br>-<br>**0.3508**<br>- | `NO_EDGE_FOUND` |

---

## 4. Standalone vs Composite Incremental Value Analysis

To earn a place in a production architecture, a composite conditioning filter must demonstrate **statistically significant incremental return** $\Delta \mu$ over its standalone parent signal, after penalizing for parameterization and degrees of freedom.

### 4.1 Liquidity Sweep SFP Conditioned Families (Parent: `BENCH_LIQUIDITY_SWEEP_SFP`)
On 2023 TEST ($N = 1337$, Gross $= +5.08$ bps):
1. **`COMP_SFP_HTF_TREND`**:
   - Filter: Trade only when sweep aligns with completed 4H EMA 50 trend (`trend_4h == 'BULL'` for Longs, `'BEAR'` for Shorts).
   - TEST Effect: Sample reduced by 53% ($N = 627$). Gross return increased to $+10.22$ bps (+5.14 bps incremental gross).
   - Net return at baseline 9.1 bps: $+1.12$ bps.
   - Bootstrapped $p$-value: raw $p = 0.0315$ (6h), $p = 0.0300$ (2h).
   - **Why It Fails**: Under pre-registered Benjamini-Hochberg FDR across the $m=10$ hypotheses, its adjusted $q = 0.2950$, failing the $q < 0.05$ threshold. Furthermore, **out-of-time confirmation completely breaks down**: in Q1 2024, gross return falls from $+10.22$ bps to $+3.59$ bps, yielding **$-5.51$ bps net** after 9.1 bps friction. Across the full 2023-2024 dataset, it was negative in TRAIN ($-6.56$ bps net), negative in VAL ($-8.76$ bps net), and negative in Q1 2024 ($-5.51$ bps net). Its TEST outperformance was a sample artifact of Q4 2023 momentum.
2. **`COMP_SFP_RVOL_CONFIRM`**:
   - Filter: Require 5m relative volume $\ge 1.5$.
   - TEST Effect: Sample reduced by 33% ($N = 900$). Gross return collapsed from $+5.08$ bps to $+0.85$ bps (**$-4.23$ bps degradation**).
   - Out-of-time Effect: Q1 2024 gross return $+0.79$ bps ($-8.31$ bps net).
   - **Conclusion**: High relative volume on sweep bars actively harms mean reversion expectancy.
3. **`COMP_SFP_VOL_EXPANSION`**:
   - Filter: Exclude compressed volatility regimes ($ATR_{14} / ATR_{50} \ge 0.75$).
   - TEST Effect: $N=1324$ vs $1337$. Gross return $+5.22$ bps vs $+5.08$ bps ($+0.14$ bps incremental).
   - **Conclusion**: Removes less than 1% of sweeps; zero meaningful economic impact.
4. **`COMP_SFP_CVD_ABSORPTION`**:
   - Filter: Require opposing order flow absorption ($cvd\_z \le -1.0$ on Long sweep, $cvd\_z \ge +1.0$ on Short sweep).
   - TEST Effect: Sample reduced by 60% ($N = 534$). Gross return increased from $+5.08$ bps to $+8.26$ bps (+3.18 bps incremental).
   - Net return at baseline 9.1 bps: **$-0.84$ bps**.
   - Bootstrapped $p$-value: raw $p = 0.0815$, FDR $q = 0.2950$.
   - **Conclusion**: Even with verified institutional order flow absorption, the gross return of 8.26 bps cannot clear 9.1 bps round-trip friction.
5. **`COMP_HTF_1H_SWING_SFP`**:
   - Filter: Measure sweeps against completed 1H swing highs/lows rather than 15m.
   - TEST Effect: Gross return $+4.55$ bps vs $+5.08$ bps for 15m sweeps (**$-0.53$ bps degradation**).
   - **Conclusion**: 1H swing reference points do not improve 60m forward expectancy.

### 4.2 HTF Aligned Displacement Conditioned Families (Parent: `BENCH_HTF_ALIGNED_DISPLACEMENT`)
On 2023 TEST ($N = 898$, Gross $= +5.83$ bps):
1. **`COMP_DISPLACEMENT_RVOL`**:
   - Filter: Require 5m relative volume $\ge 2.0$.
   - TEST Effect: Sample reduced by 29% ($N = 640$). Gross return $+5.73$ bps vs $+5.83$ bps benchmark (**$-0.10$ bps degradation**).
   - Q1 2024 Effect: Gross $+6.97$ bps, net $-2.13$ bps.
   - **Conclusion**: RVOL conditioning adds zero incremental value to displacement.
2. **`COMP_DISPLACEMENT_VOL_EXPANSION`**:
   - Filter: Require expanded volatility regime ($ATR_{14} / ATR_{50} > 1.25$).
   - TEST Effect: Gross return drops to $-0.37$ bps (**$-6.20$ bps degradation**).
   - Q1 2024 Effect: Gross return collapses to **$-15.36$ bps** ($-24.46$ bps net).
   - **Conclusion**: Entering momentum displacements during extended volatility expansion leads to severe adverse selection and immediate whipsaw.

### 4.3 Mutual Confluence Interaction (`COMP_DUAL_CONFLUENCE`)
- Definition: A single 5m bar that simultaneously satisfies both the 15m Liquidity Sweep SFP and the HTF-Aligned Momentum Displacement condition.
- Empirical Observations:
  - 2023 TRAIN (7 months, 3 symbols): $N = 45$, Gross $-0.79$ bps, Net $-9.89$ bps.
  - 2023 VAL (2.5 months, 3 symbols): $N = 25$, Gross $+14.51$ bps, Net $+5.41$ bps.
  - 2023 TEST (2.5 months, 3 symbols): $N = 16$, Gross $+20.87$ bps, Net $+11.77$ bps.
  - Q1 2024 OOT (3 months, 3 symbols): $N = 25$, Gross $+17.87$ bps, Net $+8.76$ bps.
- **Critical Methodological Evaluation**:
  - Pre-registered sample size requirement: $N \ge 30$ in TEST partition. **FAILED** ($N = 16$).
  - Over the entire 7 months of TRAIN, mean return was negative ($-0.79$ bps gross).
  - The occurrence rate is extremely sparse: approximately 1 event every 4.6 days across the entire 3-symbol universe.
  - Because sample sizes in TEST and OOT fall below the minimum reliable cluster threshold, its bootstrap inference is non-computable ($p = 1.000$).
  - **Verdict**: `INCONCLUSIVE_INSUFFICIENT_SAMPLE`. Cannot be accepted as a tradable edge.

---

## 5. Transaction-Cost and Block-Length Sensitivity Analysis

### 5.1 Transaction Friction Sensitivity (TEST vs OOT)
The table below highlights the fragility of nominally positive candidates when exposed to friction tiers:

```
                          TEST (2023)                         OUT_OF_TIME_Q1_2024
Hypothesis            Gross   5.0bps  9.1bps  15.0bps     Gross   5.0bps  9.1bps  15.0bps
-----------------------------------------------------------------------------------------
HTF Displacement      +5.83   +0.83   -3.27   -9.17       +8.12   +3.12   -0.98   -6.88
Liquidity Sweep SFP   +5.08   +0.08   -4.02   -9.92       +2.95   -2.05   -6.15   -12.05
SFP x 4H Trend       +10.22   +5.22   +1.12   -4.78       +3.59   -1.41   -5.51   -11.41
SFP x CVD Absorption  +8.26   +3.26   -0.84   -6.74        N/A     N/A     N/A     N/A
Displacement x RVOL   +5.73   +0.73   -3.37   -9.27       +6.97   +1.97   -2.13   -8.03
Dual Confluence      +20.87  +15.87  +11.77   +5.87      +17.87  +12.87   +8.77   +2.87
```

**Key Finding**:
Except for the under-sampled `COMP_DUAL_CONFLUENCE` ($N=16$), **no candidate survived 9.1 bps friction in Q1 2024**. Even under hypothetical 5.0 bps maker-taker friction, only 2 candidates were positive in Q1 2024, and both failed basic statistical significance ($p > 0.13$).

### 5.2 Time-Block Bootstrap Duration Sensitivity
Testing whether significance depends arbitrarily on chosen cluster block lengths (2h, 6h, 24h):

```
                                    TEST Raw p-values            Q1 2024 Raw p-values
Hypothesis                       2h       6h       24h         2h       6h       24h
------------------------------------------------------------------------------------
BENCH_HTF_ALIGNED_DISPLACEMENT 0.1855   0.1890   0.2280      0.1275   0.1320   0.0895
BENCH_LIQUIDITY_SWEEP_SFP      0.1210   0.1180   0.1835      0.4000   0.4065   0.3190
COMP_SFP_HTF_TREND             0.0300   0.0315   0.0845      0.3975   0.4080   0.3485
COMP_SFP_RVOL_CONFIRM          0.8045   0.8105   0.8280      0.8550   0.8595   0.8395
COMP_SFP_VOL_EXPANSION         0.1140   0.1105   0.1740      0.2740   0.2675   0.1795
COMP_DISPLACEMENT_RVOL         0.3070   0.3215   0.3170      0.3215   0.3170   0.2765
COMP_DISPLACEMENT_VOL_EXPANSION 0.9725  0.9685   0.9765      0.2955   0.2630   0.2755
COMP_SFP_CVD_ABSORPTION        0.0790   0.0815   0.1105        N/A      N/A      N/A
COMP_HTF_1H_SWING_SFP          0.2325   0.2105   0.2330      0.3280   0.3185   0.2705
```

**Key Finding**:
The statistical non-significance of all candidates is invariant to block length:
- Whether evaluated at 2 hours (capturing intraday auto-correlation), 6 hours (capturing multi-hour volatility clusters), or 24 hours (capturing daily regime shocks), $p$-values consistently remain well above the $\alpha = 0.05$ threshold.
- For `COMP_SFP_HTF_TREND`, expanding the block length to 24h directly dissolves its nominal significance in TEST ($p = 0.0845$), confirming that contemporaneous daily macro moves were artificially inflating sub-daily t-statistics.

---

## 6. Structural Stop-Room and Thesis-Resumption Audit

Evaluating first-passage structural stop mechanics across all 41,860 events:

| Model Name | Partition | Sample Size | Gross Realized R | Net Realized R (9.1 bps) | Class A (Clean Stop) | Class B (Premature Stop / Resumed) | Class C (Clean Target Win) |
|---|---|---|---|---|---|---|---|
| `STOP_5M_SWING` | TEST<br>OOT 2024 | 7,141<br>7,886 | -0.002 R<br>-0.005 R | **-0.668 R**<br>**-0.666 R** | 24.98%<br>24.45% | **24.06%**<br>**25.22%** | 31.86%<br>31.61% |
| `STOP_15M_SWING` | TEST<br>OOT 2024 | 7,381<br>8,110 | -0.027 R<br>-0.031 R | **-0.894 R**<br>**-0.889 R** | 20.85%<br>19.94% | **29.43%**<br>**30.23%** | 31.30%<br>30.46% |
| `STOP_1H_SWING` | TEST<br>OOT 2024 | 6,570<br>7,249 | -0.037 R<br>-0.043 R | **-0.611 R**<br>**-0.567 R** | 19.73%<br>18.79% | **20.08%**<br>**20.26%** | 22.59%<br>21.60% |
| `STOP_ATR_ENVELOPE` | TEST<br>OOT 2024 | 7,742<br>8,535 | +0.039 R<br>+0.029 R | **-0.179 R**<br>**-0.173 R** | 44.38%<br>44.62% | **9.24%**<br>**9.53%** | 36.11%<br>36.17% |

### Core Findings on Trade Management:
1. **Premature Invalidation (Class B Resumption)**:
   - For swing-based stops (`STOP_15M_SWING`), **29.4% to 30.2% of all trades suffer Class B execution**: the stop is triggered by adverse noise within the 120-minute window, after which price immediately reverses and hits the intended structural TP1 target.
   - For 5m swing stops, 24% to 25% are prematurely stopped out.
2. **Realized Expectancy**:
   - Every single stop model produces **negative net realized R** after friction (ranging from $-0.17$ R to $-0.89$ R).
   - ATR envelopes exhibit lower Class B rates (9.2%–9.5%) but suffer higher clean losses (Class A ~44.5%), resulting in negative realized economics ($-0.17$ R).
3. **Implication for Trading Strategy**:
   - The persistent failure of structural stops to protect edge confirms that sub-daily crypto futures price action is characterized by frequent liquidity hunt sweeps that invalidate tight structural levels before establishing forward direction.

---

## 7. Data Provenance, Audit Trail & Checksums

| Artifact | File Path | SHA-256 Checksum |
|---|---|---|
| **Phase 14 Protocol** | [`docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md`](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md) | `d0a3d537f769fa7a57a530db80efeb8c2c1cf2e26090c2937ee36ba4a0eb1b4b` |
| **Phase 14 Engine** | [`control_plane/phase14_composite_engine.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/phase14_composite_engine.py) | Verified deterministic causal module |
| **Phase 14 Test Suite** | [`tests/test_phase14_composite.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/tests/test_phase14_composite.py) | 5/5 Unit tests passing |
| **Phase 14 Results JSON** | [`data/phase14_composite_results.json`](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase14_composite_results.json) | Complete machine-readable output artifact |
| **Events Parquet** | `data/phase14_events.parquet` | 41,860 rows |
| **Outcomes Parquet** | `data/phase14_forward_outcomes.parquet` | 334,880 rows |
| **Stop Room Parquet** | `data/phase14_stop_room.parquet` | 155,942 rows |

---

## 8. Final Decision & Recommendations

### Formal Verdict
**NO EDGE FOUND FOR PRE-REGISTERED COMPOSITE HYPOTHESES UNDER VERIFIED TRANSACTION COSTS.**

### Rationale
1. **Cost Hurdle Dominance**:
   - The gross edges discovered in sub-daily momentum and sweep signals (+5 to +10 bps) are fundamentally smaller than the empirical friction of trading BingX Perpetual Swap Futures (9.1 bps).
   - Conditioning signals on market regime filters (trend, volatility, volume, order flow) reduces sample size and introduces curve-fitting without expanding gross returns enough to clear trading friction.
2. **False Discovery in Small Samples**:
   - Nominal outperformance in small subsets (e.g., `COMP_SFP_HTF_TREND` in Q4 2023 or `COMP_DUAL_CONFLUENCE`) vanishes when adjusted for family-wise false discovery rates and out-of-time confirmation.
3. **System Safety**:
   - In accordance with the Ophelia Rule Book and the Deterministic Authority principle, no strategy may be promoted to PAPER or LIVE execution without passing out-of-time FDR and net cost hurdles.
   - All safety invariants remain enforced:
     - `TRADING_AUTHORITY = False`
     - `EXECUTION_MODE = SHADOW`
     - `LIVE_ORDERS_FORBIDDEN = True`
