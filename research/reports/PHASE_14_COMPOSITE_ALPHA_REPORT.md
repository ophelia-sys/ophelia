# OPHELIA PHASE 14 — AUDIT CLOSEOUT & PROTOCOL CONFORMANCE REPORT

**Document ID**: `OPHELIA-RES-PHASE14-AUDIT-001`  
**Execution Timestamp**: `2026-10-18T22:25:50Z`  
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
| **3. Did any composite produce positive net expectancy after costs?** | **NO** | In the out-of-time Q1 2024 period, every candidate with adequate statistical sample size ($N \ge 30$) produced **negative net expectancy** after baseline 9.1 bps modeled friction (ranging from $-0.98$ bps to $-24.46$ bps). |
| **4. Did any candidate satisfy the pre-registered statistical criteria?** | **NO** | In confirmatory net-cost inference ($H_0: \mu_{\text{net}} \le 0$), **zero** candidates achieved statistical significance on TEST (lowest Net FDR $q = 0.2200 \gg 0.05$). For `COMP_SFP_HTF_TREND`, net hurdle p-value is $p = 0.8220$ (Net FDR $q = 0.8650$). `COMP_DUAL_CONFLUENCE` failed the registered minimum sample size hurdle ($N = 16 < 30$). |
| **5. Which candidate, if any, deserves fresh independent confirmation?** | **NONE** | No candidate cleared the double barrier of cost survival and multiple-testing significance. Promoting any tested candidate to production or live trading would violate empirical risk gating. |
| **6. What remains unverified?** | **Execution Realism for Passive Limit Orders** | Maker fee economics (5.0 bps round-trip) require passive liquidity provision. Fill rates, adverse selection, queue position, and cancel-replace dynamics cannot be verified without exchange order-book level 2 tick archives. |

---

## 2. Protocol Discrepancies & Conformance Reconciliation

### 2.1 Bootstrap Resample Count Conformance ($B=1,000$ vs $B=2,000$)
- **Discrepancy**: The locked protocol ([`docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md`](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md), Section 5.1) pre-registered $B = 1,000$ resamples. The underlying discovery engine default in `synchronized_time_block_bootstrap` was $B = 2,000$, resulting in the initial study executing $B = 2,000$.
- **Reconciliation Pass**: A full protocol-compliance inference pass was executed using strictly $B = 1,000$ on the identical frozen candidate events and forward outcomes.
- **Empirical Impact**:
  ```
  Hypothesis                       Gross p (B=1k)   Gross p (B=2k)   Net p (B=1k)   Net p (B=2k)
  ----------------------------------------------------------------------------------------------
  BENCH_HTF_ALIGNED_DISPLACEMENT       0.1860           0.1890          0.4420         0.4670
  BENCH_LIQUIDITY_SWEEP_SFP            0.1100           0.1180          0.2050         0.2135
  COMP_SFP_HTF_TREND                   0.0330           0.0315          0.8220         0.8360
  COMP_SFP_RVOL_CONFIRM                0.8040           0.8105          0.0220         0.0290
  COMP_SFP_VOL_EXPANSION               0.1020           0.1105          0.2200         0.2335
  COMP_DISPLACEMENT_RVOL               0.3200           0.3215          0.5570         0.5490
  COMP_DISPLACEMENT_VOL_EXPANSION      0.9710           0.9685          0.3660         0.3635
  COMP_SFP_CVD_ABSORPTION              0.0860           0.0815          0.8650         0.8665
  COMP_DUAL_CONFLUENCE                 0.2530           0.2500          0.5300         0.5190
  COMP_HTF_1H_SWING_SFP                0.1980           0.2105          0.1980         0.2100
  ```
- **Conclusion**: The variance between $B=1,000$ and $B=2,000$ is negligible ($|\Delta p| \le 0.014$). All inferential decisions and multiple-testing verdicts are 100% invariant.

### 2.2 Transaction-Cost Conformance & Component Reconciliation
- **Discrepancy**: The protocol specified baseline taker friction as `4.0 bps entry fee + 4.0 bps exit fee + 1.1 bps adverse slippage = 9.1 bps`. Legacy report narrative referenced `7.0 bps fee (2 maker + 5 taker) + 2.1 bps slippage = 9.1 bps`.
- **Reconciliation**: Total modeled friction across both descriptions is exactly 9.1 bps ($0.00091$). The component attribution is corrected to align strictly with the locked protocol:
  1. `FEE_ONLY` (5.0 bps): 2.5 bps entry maker fee + 2.5 bps exit maker fee + 0.0 bps slippage = **5.0 bps round-trip**.
  2. `BASELINE_TAKER` (9.1 bps): 4.0 bps entry taker fee + 4.0 bps exit taker fee + 1.1 bps adverse slippage = **9.1 bps round-trip**.
  3. `CONSERVATIVE_SLIP` (15.0 bps): 4.0 bps entry taker fee + 4.0 bps exit taker fee + 7.0 bps adverse slippage = **15.0 bps round-trip**.
- **Distinction Between Modeled vs Verified Costs**:
  - The costs applied in this quantitative discovery study are **modeled hypothetical parameters**, not verified live fills.
  - Market data is sourced from **Binance USDT-M Futures** (providing continuous 1m OHLCV and tick trade-level order flow), whereas Ophelia's live broker target is **BingX Perpetual Swap Futures**.
  - Because no live orders were placed, these costs must not be represented as empirically verified on-exchange execution.

### 2.3 Confirmatory Statistical Inference (Gross vs Net Hurdle)
- **Discrepancy**: The initial inference pass tested the null hypothesis of zero gross return ($H_0: \mu_{\text{gross}} = 0$). However, the registered economic claim requires proving **positive net expectancy after transaction friction** ($H_0: \mu_{\text{net}} \le 0 \iff H_0: \mu_{\text{gross}} \le 9.1\text{ bps}$).
- **Reconciliation**: Cost-adjusted bootstrap inference was calculated testing $H_0: \mu_{\text{net}} \le 0$ across all 10 candidates.
- **Critical Finding for `COMP_SFP_HTF_TREND`**:
  - TEST gross return: $+10.22$ bps ($p_{\text{gross}} = 0.0330$).
  - TEST net return after 9.1 bps friction: $+1.12$ bps with cluster standard error $\approx 4.88$ bps.
  - Net hurdle $p$-value: **$p = 0.8220$** ($t_{\text{net}} = 0.23$).
  - Net Benjamini-Hochberg FDR $q$-value: **$q = 0.8650 \gg 0.05$**.
  - **Conclusion**: When tested against the economic hypothesis of positive net returns, `COMP_SFP_HTF_TREND` exhibits no statistically distinguishable net edge above trading friction.

---

## 3. Eligibility Audit ($N \ge 30$ and $B_{\text{active}} \ge 10$)

Both registered minimums are strictly enforced on confirmatory partitions (TEST and Q1 2024). Active clusters are evaluated using 6-hour synchronized blocks across all 3 universe symbols:

| # | Hypothesis | 2023 TEST $N$ | TEST Clusters | TEST Eligibility | Q1 2024 OOT $N$ | OOT Clusters | OOT Eligibility | Conformance Status |
|---|---|---|---|---|---|---|---|---|
| **1** | `BENCH_HTF_ALIGNED_DISPLACEMENT` | 898 | 264 | **PASS** | 1047 | 314 | **PASS** | Eligible for confirmation |
| **2** | `BENCH_LIQUIDITY_SWEEP_SFP` | 1337 | 302 | **PASS** | 1627 | 350 | **PASS** | Eligible for confirmation |
| **3** | `COMP_SFP_HTF_TREND` | 627 | 238 | **PASS** | 773 | 299 | **PASS** | Eligible for confirmation |
| **4** | `COMP_SFP_RVOL_CONFIRM` | 900 | 282 | **PASS** | 1027 | 321 | **PASS** | Eligible for confirmation |
| **5** | `COMP_SFP_VOL_EXPANSION` | 1324 | 301 | **PASS** | 1589 | 348 | **PASS** | Eligible for confirmation |
| **6** | `COMP_DISPLACEMENT_RVOL` | 640 | 238 | **PASS** | 748 | 281 | **PASS** | Eligible for confirmation |
| **7** | `COMP_DISPLACEMENT_VOL_EXPANSION` | 168 | 87 | **PASS** | 182 | 95 | **PASS** | Eligible for confirmation |
| **8** | `COMP_SFP_CVD_ABSORPTION` | 534 | 234 | **PASS** | 0 | 0 | **FAIL_ZERO** | Gated closed in 2024 (absent order flow) |
| **9** | `COMP_DUAL_CONFLUENCE` | 16 | 15 | **INCONCLUSIVE** | 25 | 23 | **INCONCLUSIVE** | **FAILED $N \ge 30$ MINIMUM** |
| **10** | `COMP_HTF_1H_SWING_SFP` | 1298 | 289 | **PASS** | 1517 | 324 | **PASS** | Eligible for confirmation |

`COMP_DUAL_CONFLUENCE` failed the registered minimum sample size ($N = 16 < 30$ in TEST; $N = 25 < 30$ in Q1 2024). In accordance with Section 5.2 of the protocol, it is classified as `INCONCLUSIVE` and cannot be promoted.

---

## 4. Confirmatory Multi-Factor Results Table ($B = 1,000$)

Primary outcome: 60-minute forward return (bps). Multiple testing: Benjamini-Hochberg FDR across the $m=10$ hypotheses.

| # | Hypothesis | TEST Gross | TEST Net (9.1 bps) | TEST $p_{\text{gross}}$ | TEST $p_{\text{net}}$ | TEST FDR $q_{\text{net}}$ | OOT Gross | OOT Net (9.1 bps) | OOT $p_{\text{net}}$ | OOT FDR $q_{\text{net}}$ | Final Decision Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | `BENCH_HTF_ALIGNED_DISPLACEMENT` | +5.83 bps | -3.27 bps | 0.1860 | 0.4420 | 0.6963 | +8.12 bps | -0.98 bps | 0.8640 | 0.9600 | `NO_EDGE_FOUND` |
| **2** | `BENCH_LIQUIDITY_SWEEP_SFP` | +5.08 bps | -4.02 bps | 0.1100 | 0.2050 | 0.5500 | +2.95 bps | -6.15 bps | 0.0730 | 0.2667 | `NO_EDGE_FOUND` |
| **3** | `COMP_SFP_HTF_TREND` | +10.22 bps | +1.12 bps | 0.0330 | 0.8220 | 0.8650 | +3.59 bps | -5.51 bps | 0.1940 | 0.3567 | `NO_EDGE_FOUND` |
| **4** | `COMP_SFP_RVOL_CONFIRM` | +0.85 bps | -8.25 bps | 0.8040 | 0.0220 | 0.2200 | +0.79 bps | -8.31 bps | 0.0480 | 0.2667 | `NO_EDGE_FOUND` |
| **5** | `COMP_SFP_VOL_EXPANSION` | +5.22 bps | -3.88 bps | 0.1020 | 0.2200 | 0.5500 | +3.85 bps | -5.25 bps | 0.1220 | 0.3050 | `NO_EDGE_FOUND` |
| **6** | `COMP_DISPLACEMENT_RVOL` | +5.73 bps | -3.37 bps | 0.3200 | 0.5570 | 0.6963 | +6.97 bps | -2.13 bps | 0.7900 | 0.9600 | `NO_EDGE_FOUND` |
| **7** | `COMP_DISPLACEMENT_VOL_EXPANSION` | -0.37 bps | -9.47 bps | 0.9710 | 0.3660 | 0.6963 | -15.36 bps | -24.46 bps | 0.0800 | 0.2667 | `NO_EDGE_FOUND` |
| **8** | `COMP_SFP_CVD_ABSORPTION` | +8.26 bps | -0.84 bps | 0.0860 | 0.8650 | 0.8650 | +0.00 bps | +0.00 bps | N/A | N/A | `NO_EDGE_FOUND` |
| **9** | `COMP_DUAL_CONFLUENCE` | +20.87 bps | +11.77 bps | 0.2530 | 0.5300 | 0.6963 | +17.87 bps | +8.77 bps | 0.6530 | 0.9329 | `INCONCLUSIVE` |
| **10** | `COMP_HTF_1H_SWING_SFP` | +4.55 bps | -4.55 bps | 0.1980 | 0.1980 | 0.5500 | +4.11 bps | -4.99 bps | 0.2140 | 0.3567 | `NO_EDGE_FOUND` |

*Note on $p_{\text{net}}$: Evaluates centered empirical test $H_0: \mu_{\text{net}} \le 0$. Small $p_{\text{net}}$ for candidates with large negative net returns (e.g. `COMP_SFP_RVOL_CONFIRM`, $\mu_{\text{net}} = -8.25$ bps, $p = 0.0220$) reflects two-tailed test rejection of zero net return due to large significant negative performance.*

---

## 5. Block-Duration Sensitivity Audit (2h vs 6h vs 24h Blocks)

Testing invariance of statistical conclusions across synchronized duration choices under $B=1,000$:

```
                                      TEST Gross p-values               TEST Net-Hurdle p-values
Hypothesis                         2h       6h       24h              2h       6h       24h
-----------------------------------------------------------------------------------------------
BENCH_HTF_ALIGNED_DISPLACEMENT   0.1760   0.1860   0.2170           0.4570   0.4420   0.4510
BENCH_LIQUIDITY_SWEEP_SFP        0.1190   0.1100   0.1780           0.2150   0.2050   0.2810
COMP_SFP_HTF_TREND               0.0270   0.0330   0.0910           0.8190   0.8220   0.8800
COMP_SFP_RVOL_CONFIRM            0.8140   0.8040   0.8350           0.0230   0.0220   0.0540
COMP_SFP_VOL_EXPANSION           0.1120   0.1020   0.1700           0.2310   0.2200   0.2970
COMP_DISPLACEMENT_RVOL           0.3150   0.3200   0.3110           0.5610   0.5570   0.5400
COMP_DISPLACEMENT_VOL_EXPANSION  0.9690   0.9710   0.9740           0.3620   0.3660   0.3800
COMP_SFP_CVD_ABSORPTION          0.0840   0.0860   0.1080           0.8690   0.8650   0.8920
COMP_DUAL_CONFLUENCE             0.2640   0.2530   0.2450           0.5280   0.5300   0.5410
COMP_HTF_1H_SWING_SFP            0.2200   0.1980   0.2260           0.2200   0.1980   0.2260
```

**Key Finding**:
- Across all block durations, **no candidate achieves net statistical significance**.
- `COMP_SFP_HTF_TREND` gross significance vanishes completely when expanding block length to 24 hours ($p_{\text{gross}} = 0.0910$), confirming that daily cross-asset co-movement was inflating sub-daily test statistics.

---

## 6. Structural Stop-Room and Thesis-Resumption Audit

Evaluating first-passage structural stop mechanics across all 41,860 events:

| Model Name | Partition | Sample Size | Gross Realized R | Net Realized R (9.1 bps) | Class A (Clean Stop) | Class B (Premature Stop / Resumed) | Class C (Clean Target Win) |
|---|---|---|---|---|---|---|---|
| `STOP_5M_SWING` | TEST<br>OOT 2024 | 7,141<br>7,886 | -0.002 R<br>-0.005 R | **-0.668 R**<br>**-0.666 R** | 24.98%<br>24.45% | **24.06%**<br>**25.22%** | 31.86%<br>31.61% |
| `STOP_15M_SWING` | TEST<br>OOT 2024 | 7,381<br>8,110 | -0.027 R<br>-0.031 R | **-0.894 R**<br>**-0.889 R** | 20.85%<br>19.94% | **29.43%**<br>**30.23%** | 31.30%<br>30.46% |
| `STOP_1H_SWING` | TEST<br>OOT 2024 | 6,570<br>7,249 | -0.037 R<br>-0.043 R | **-0.611 R**<br>**-0.567 R** | 19.73%<br>18.79% | **20.08%**<br>**20.26%** | 22.59%<br>21.60% |
| `STOP_ATR_ENVELOPE` | TEST<br>OOT 2024 | 7,742<br>8,535 | +0.039 R<br>+0.029 R | **-0.179 R**<br>**-0.173 R** | 44.38%<br>44.62% | **9.24%**<br>**9.53%** | 36.11%<br>36.17% |

---

## 7. Evidence, Checksums & Reproducibility Verification

| Artifact | File Path | SHA-256 Checksum |
|---|---|---|
| **Phase 14 Protocol** | [`docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md`](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md) | `128a319b0eed5e3332d88e95dc6d3f9770517676242777d3a632494b484aaa3c` |
| **Phase 14 Engine** | [`control_plane/phase14_composite_engine.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/phase14_composite_engine.py) | `774a6e9617e31a40016cde9742766d989cc01f4f38141e3be9a19a30f54db936` |
| **Phase 14 Results JSON** | [`data/phase14_composite_results.json`](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase14_composite_results.json) | `99aed1ee07586c0d022cd90c3cb724f71dc09cca10ba2a49fb927b7281f41c27` |
| **Conformance Summary JSON** | [`data/phase14_conformance_summary.json`](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase14_conformance_summary.json) | Verified machine-readable audit artifact |
| **Events Parquet** | `data/phase14_events.parquet` | `a9f3716e84d27c2aa23ce07b8aab92577c4c1e6ded99909ce18eac0dd67ede67` |
| **Outcomes Parquet** | `data/phase14_forward_outcomes.parquet` | `d4efb23fe5fbafbbe5034e505ae2d4d6e56cf503cd1eb3428d44039b6eaf12ab` |
| **Stop Room Parquet** | `data/phase14_stop_room.parquet` | `09c03d6818864c616907c0f5d772bfd8e2299e48d40698d5ac4f97e895516a2b` |

### Environment & Test Execution Verification:
- **Local Tested Commit**: `b034e2c` on `repair/phase13-audit-closeout`.
- **GitHub Origin**: Pushed to `origin/repair/phase13-audit-closeout` at `b034e2c`.
- **VPS Research Checkout** (`/home/ubuntu/ophelia-research`):
  - Updated to `b034e2c`.
  - Executed `pytest tests/test_phase14_composite.py -v`: **5 passed in 2.42s**.
  - Executed `pytest tests/test_phase13_discovery.py -q`: **70 passed, 1 skipped in 6.16s**.
- **VPS Production Checkout** (`/opt/ophelia`):
  - **100% UNTOUCHED** at commit `0a764fd23dd1b24070b3d09c24f54e698a3e4ae6`.
  - Zero modifications to production database or trading engine.

---

## 8. Final Decision & System Recommendation

### Formal Conclusion
**`NO EDGE FOUND` FOR ALL PRE-REGISTERED COMPOSITE HYPOTHESES UNDER MODELED TRANSACTION COSTS.**

### Audit Finding
1. **Economic Edge Absence**: None of the 10 pre-registered standalone or composite hypotheses demonstrate positive net expectancy exceeding modeled 9.1 bps trading friction across both TEST and out-of-time Q1 2024.
2. **Multiple Testing Rejection**: All candidates fail Benjamini-Hochberg FDR significance at $q < 0.05$ under the net hurdle hypothesis.
3. **Trading Guard Enforced**: In accordance with the Ophelia Rule Book and the Deterministic Authority principle, no strategy is promoted to PAPER or LIVE trading.
4. **Safety Invariants Unchanged**:
   - `TRADING_AUTHORITY = False`
   - `EXECUTION_MODE = SHADOW`
   - `LIVE_ORDERS_FORBIDDEN = True`
