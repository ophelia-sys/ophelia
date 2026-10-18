# OPHELIA PHASE 14 — AUDIT CLOSEOUT & STATISTICAL CONFORMANCE REPORT

**Document ID**: `OPHELIA-RES-PHASE14-AUDIT-FINAL-001`  
**Execution Timestamp**: `2026-10-18T22:33:01Z`  
**Engine Layer**: [`control_plane/phase14_composite_engine.py`](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/phase14_composite_engine.py)  
**Governing Protocol**: [`docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md`](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_14_COMPOSITE_ALPHA_PROTOCOL.md)  
**Conformance Summary**: [`data/phase14_conformance_summary.json`](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase14_conformance_summary.json)  
**Pre-Registered Hypotheses**: $m = 10$  
**Safety Invariants**: `TRADING_AUTHORITY=False`, `EXECUTION_MODE=SHADOW`, `LIVE_ORDERS_FORBIDDEN=True`  

---

## 1. Executive Summary & Core Mandate Answers

| Mandate Question | Deterministic Empirical Finding | Evidence / Citation |
|---|---|---|
| **1. Did the composite experiment run to completion?** | **YES** | Processed 100% of 2023 (`binance_um_universe_1m_v2.parquet`, 1,576,800 1m bars across BTC, ETH, SOL) and Q1 2024 (`phase12_fresh_universe_1m.parquet`, 527,040 1m bars with Dec 2023 warm-up). Extracted 41,860 events, 334,880 forward trajectory outcomes, and 155,942 stop-room evaluations. |
| **2. Was the later data genuinely independent for this hypothesis family?** | **YES (Strictly Out-of-Time)** | Q1 2024 (`phase12_fresh_universe_1m.parquet`, SHA-256: `91de7196ace28474ef5fbeaa3c004e2df38b4c3658e451bd0d575b5e12060409`) was preserved untouched until candidate definitions and engine logic were frozen. Resampled with December 2023 warm-up to prevent initial-state bias, then filtered strictly for $T \ge \text{2024-01-01 00:00:00 UTC}$. |
| **3. Did any composite produce positive net expectancy after costs?** | **NO** | In the out-of-time Q1 2024 period, every candidate with adequate statistical sample size ($N \ge 30$) produced **negative net expectancy** after baseline 9.1 bps modeled friction (ranging from $-0.98$ bps to $-24.46$ bps). |
| **4. Did any candidate satisfy the pre-registered statistical criteria?** | **NO** | In confirmatory one-sided net-hurdle inference ($H_0: \mu_{\text{net}} \le 0$), **zero** candidates achieved statistical significance on TEST (lowest Net FDR $q = 0.9920 \gg 0.05$). For `COMP_SFP_HTF_TREND`, net hurdle p-value is $p = 0.4330$ ($t_{\text{net}} = 0.23$). `COMP_DUAL_CONFLUENCE` failed the registered minimum sample size hurdle ($N = 16 < 30$). |
| **5. Which candidate, if any, deserves fresh independent confirmation?** | **NONE** | No candidate cleared the double barrier of cost survival and multiple-testing significance. Promoting any tested candidate to production or live trading would violate empirical risk gating. |
| **6. What remains unverified?** | **Execution Realism for Passive Limit Orders** | Maker fee economics (5.0 bps round-trip) require passive liquidity provision. Fill rates, adverse selection, queue position, and cancel-replace dynamics cannot be verified without exchange order-book level 2 tick archives. |

---

## 2. Statistical Methodology & Net-Hurdle Formulation

### 2.1 Formal Hypotheses
For each candidate hypothesis, testing is bifurcated into a **Confirmatory Net Hurdle Test** (evaluating the economic claim of trade profitability) and a **Diagnostic Gross Test** (evaluating unconstrained market drift):

1. **Confirmatory Net Hurdle Test (Primary Economic Claim)**:
   - **Economic Claim**: The signal generates positive expected return exceeding the verified exchange transaction friction $c = 9.1\text{ bps}$ ($0.00091$).
   - **Null Hypothesis**:
     $$H_0: \mu_{\text{net}} \le 0 \iff H_0: \mu_{\text{gross}} \le 9.1\text{ bps}$$
   - **Alternative Hypothesis**:
     $$H_1: \mu_{\text{net}} > 0 \iff H_1: \mu_{\text{gross}} > 9.1\text{ bps}$$
   - **Directionality**: Strictly **one-sided upper tail**.

2. **Diagnostic Gross Test (Pre-Cost Microstructure Drift)**:
   - **Diagnostic Purpose**: Measures whether the conditioning rule isolates non-zero mean directional movement in frictionless space.
   - **Null Hypothesis**:
     $$H_0: \mu_{\text{gross}} = 0$$
   - **Alternative Hypothesis**:
     $$H_1: \mu_{\text{gross}} \ne 0$$
   - **Directionality**: **Two-sided centered**. Explicitly designated as diagnostic; positive gross drift does not prove net tradability.

### 2.2 Resampling & Tail Calculation Scheme
- **Resampling Scheme**: Synchronized cross-symbol time-block bootstrap across all universe symbols (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`). Resampling units are continuous chronological time blocks (primary duration: **6 Hours**; sensitivity durations: **2 Hours** and **24 Hours**).
- **Bootstrap Parameters**: $B = 1,000$ resamples (locked protocol standard; confirmed invariant against $B = 2,000$), random seed $S = 42$.
- **Null-Centering Formulation**:
  Let $y_i = r_{i,\text{gross}} - c$ be the realized net return for event $i$. Observed sample mean is $\bar{y} = \hat{\mu}_{\text{gross}} - c$.
  For each bootstrap replicate $b \in \{1, \dots, B\}$, the resampled mean is $\bar{y}^{*b}$.
  The distribution is shifted to satisfy the null boundary $H_0: \mu_{\text{net}} = 0$:
  $$\tilde{y}^{*b} = \bar{y}^{*b} - \bar{y}$$
  The centered one-sided upper-tail p-value is:
  $$p_{\text{confirmatory}} = \frac{1}{B} \sum_{b=1}^B \mathbb{I}\left(\tilde{y}^{*b} \ge \bar{y}\right)$$
- **Quantile Inversion Verification**:
  Direct empirical evaluation of $P^*(\bar{y}^* \le 0) = \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\bar{y}^{*b} \le 0)$ confirms the fraction of resamples failing the cost hurdle.

### 2.3 Clarification of Two-Sided vs One-Sided Results
- **`COMP_SFP_HTF_TREND`**:
  - Sample size $N = 627$, Gross mean $+10.22$ bps, Net mean $+1.12$ bps, Cluster standard error $\text{SE} \approx 4.80$ bps.
  - Studentized net statistic $t_{\text{net}} = \frac{+1.12}{4.80} = +0.23$.
  - In a two-sided test against zero net return, $P(|Z| \ge 0.23) \approx 0.822$, which was reported as $p = 0.8220$.
  - In the correctly directed one-sided test for positive net edge ($H_1: \mu_{\text{net}} > 0$), the p-value is **$p = 0.4330$**.
  - Under Benjamini-Hochberg multiplicity control across $m=10$, adjusted **$q = 0.9920 \gg 0.05$**. Zero evidence of edge above friction.
- **`COMP_SFP_RVOL_CONFIRM`**:
  - Sample size $N = 900$, Gross mean $+0.85$ bps, Net mean $-8.25$ bps, Cluster standard error $\text{SE} \approx 3.61$ bps.
  - Studentized net statistic $t_{\text{net}} = \frac{-8.25}{3.61} = -2.28$.
  - A two-sided test produces $p = 0.0220$, detecting that $-8.25$ bps is significantly different from zero.
  - **Crucial Inference Correction**: That significance is **significantly NEGATIVE** (value destruction).
  - In the one-sided test for positive alpha ($H_1: \mu_{\text{net}} > 0$), the p-value is **$p = 0.9920$** ($P^*(\bar{y}^* \le 0) = 0.9860$). There is zero positive expectancy.

---

## 3. Registered Eligibility Audit ($N \ge 30$ and $B_{\text{active}} \ge 10$)

Both criteria are strictly enforced on TEST (2023) and OUT_OF_TIME_Q1_2024. Active time clusters are counted across 6-hour synchronized blocks:

| # | Hypothesis | TEST $N$ | TEST Clusters | TEST Eligibility | Q1 2024 $N$ | Q1 2024 Clusters | Q1 2024 Eligibility | Status |
|---|---|---|---|---|---|---|---|---|
| **1** | `BENCH_HTF_ALIGNED_DISPLACEMENT` | 898 | 264 | **PASS** | 1047 | 314 | **PASS** | Fully Evaluated |
| **2** | `BENCH_LIQUIDITY_SWEEP_SFP` | 1337 | 302 | **PASS** | 1627 | 350 | **PASS** | Fully Evaluated |
| **3** | `COMP_SFP_HTF_TREND` | 627 | 238 | **PASS** | 773 | 299 | **PASS** | Fully Evaluated |
| **4** | `COMP_SFP_RVOL_CONFIRM` | 900 | 282 | **PASS** | 1027 | 321 | **PASS** | Fully Evaluated |
| **5** | `COMP_SFP_VOL_EXPANSION` | 1324 | 301 | **PASS** | 1589 | 348 | **PASS** | Fully Evaluated |
| **6** | `COMP_DISPLACEMENT_RVOL` | 640 | 238 | **PASS** | 748 | 281 | **PASS** | Fully Evaluated |
| **7** | `COMP_DISPLACEMENT_VOL_EXPANSION` | 168 | 87 | **PASS** | 182 | 95 | **PASS** | Fully Evaluated |
| **8** | `COMP_SFP_CVD_ABSORPTION` | 534 | 234 | **PASS** | 0 | 0 | **GATED_ABSENT** | Order flow unavailable in Q1 2024 |
| **9** | `COMP_DUAL_CONFLUENCE` | 16 | 15 | **INCONCLUSIVE** | 25 | 23 | **INCONCLUSIVE** | **FAILED $N \ge 30$ MINIMUM** |
| **10** | `COMP_HTF_1H_SWING_SFP` | 1298 | 289 | **PASS** | 1517 | 324 | **PASS** | Fully Evaluated |

- `COMP_DUAL_CONFLUENCE`: Fails the registered $N \ge 30$ minimum in both TEST ($N = 16$) and Q1 2024 ($N = 25$). Formally classified as `INCONCLUSIVE`.
- `COMP_SFP_CVD_ABSORPTION`: In Q1 2024, taker trade volume and CVD columns are absent from `phase12_fresh_universe_1m.parquet`. It is classified as `GATED_ABSENT_IN_CONFIRMATION` rather than fabricated as zero return.

---

## 4. Primary Confirmatory Statistical Results (6h Blocks, $B = 1,000$)

Primary outcome: 60-minute forward directional return. Cost hurdle $c = 9.1\text{ bps}$. Multiple testing: Benjamini-Hochberg FDR applied separately to TEST and Q1 2024.

| # | Hypothesis | TEST Net (9.1 bps) | Confirmatory Net $p$ | Confirmatory Net $q$ | Diagnostic Gross $p$ | Q1 2024 Net (9.1 bps) | Q1 2024 Net $p$ | Q1 2024 Net $q$ | Decision Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **1** | `BENCH_HTF_ALIGNED_DISPLACEMENT` | -3.27 bps | 0.7700 | 0.9920 | 0.1860 | -0.98 bps | 0.5550 | 1.0000 | `NO_EDGE_FOUND` |
| **2** | `BENCH_LIQUIDITY_SWEEP_SFP` | -4.02 bps | 0.8990 | 0.9920 | 0.1100 | -6.15 bps | 0.9760 | 1.0000 | `NO_EDGE_FOUND` |
| **3** | `COMP_SFP_HTF_TREND` | +1.12 bps | 0.4330 | 0.9920 | 0.0330 | -5.51 bps | 0.9020 | 1.0000 | `NO_EDGE_FOUND` |
| **4** | `COMP_SFP_RVOL_CONFIRM` | -8.25 bps | 0.9920 | 0.9920 | 0.8040 | -8.31 bps | 0.9820 | 1.0000 | `NO_EDGE_FOUND` |
| **5** | `COMP_SFP_VOL_EXPANSION` | -3.88 bps | 0.8890 | 0.9920 | 0.1020 | -5.25 bps | 0.9500 | 1.0000 | `NO_EDGE_FOUND` |
| **6** | `COMP_DISPLACEMENT_RVOL` | -3.37 bps | 0.7080 | 0.9920 | 0.3200 | -2.13 bps | 0.5940 | 1.0000 | `NO_EDGE_FOUND` |
| **7** | `COMP_DISPLACEMENT_VOL_EXPANSION` | -9.47 bps | 0.8030 | 0.9920 | 0.9710 | -24.46 bps | 0.9600 | 1.0000 | `NO_EDGE_FOUND` |
| **8** | `COMP_SFP_CVD_ABSORPTION` | -0.84 bps | 0.5710 | 0.9920 | 0.0860 | N/A (gated) | N/A | N/A | `GATED_ABSENT_IN_CONFIRMATION` |
| **9** | `COMP_DUAL_CONFLUENCE` | +11.77 bps | 0.2670 | 0.9920 | 0.2530 | +8.77 bps | 0.3200 | 1.0000 | `INCONCLUSIVE` |
| **10** | `COMP_HTF_1H_SWING_SFP` | -4.55 bps | 0.9090 | 0.9920 | 0.1980 | -4.99 bps | 0.9000 | 1.0000 | `NO_EDGE_FOUND` |

---

## 5. Block-Duration Sensitivity Audit (2h vs 6h vs 24h Blocks)

Evaluating confirmatory one-sided net p-values across time-block durations ($B = 1,000$):

```
                                          TEST One-Sided Net p-values            Q1 2024 One-Sided Net p-values
Hypothesis                              2h          6h          24h             2h          6h          24h
---------------------------------------------------------------------------------------------------------------
BENCH_HTF_ALIGNED_DISPLACEMENT        0.7600      0.7700      0.7320          0.5740      0.5550      0.5180
BENCH_LIQUIDITY_SWEEP_SFP             0.9010      0.8990      0.8630          0.9770      0.9760      0.9630
COMP_SFP_HTF_TREND                    0.4230      0.4330      0.4470          0.8930      0.9020      0.8840
COMP_SFP_RVOL_CONFIRM                 0.9910      0.9920      0.9830          0.9760      0.9820      0.9790
COMP_SFP_VOL_EXPANSION                0.8930      0.8890      0.8460          0.9440      0.9500      0.9230
COMP_DISPLACEMENT_RVOL                0.7250      0.7080      0.7040          0.6090      0.5940      0.5840
COMP_DISPLACEMENT_VOL_EXPANSION       0.7900      0.8030      0.8040          0.9650      0.9600      0.9570
COMP_SFP_CVD_ABSORPTION               0.5720      0.5710      0.5490            N/A         N/A         N/A
COMP_DUAL_CONFLUENCE                  0.2280      0.2670      0.2490          0.3340      0.3200      0.3160
COMP_HTF_1H_SWING_SFP                 0.8880      0.9090      0.8840          0.9080      0.9000      0.8710
```

**Key Finding**:
Across all block durations (2h, 6h, 24h), **zero candidates achieve one-sided net significance ($p_{\text{net}} < 0.05$)**.

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

### Verified Environment & Production Status
- **Local Git Working Tree**: Clean.
- **GitHub Origin**: Pushed to `origin/repair/phase13-audit-closeout`.
- **VPS Research Checkout** (`/home/ubuntu/ophelia-research`):
  - Unit test suite: `pytest tests/test_phase14_composite.py -v`: **5 passed in 2.62s**.
  - Historical discovery tests: `pytest tests/test_phase13_discovery.py -q`: **70 passed, 1 skipped in 6.16s**.
- **VPS Production Checkout** (`/opt/ophelia`):
  - **100% UNTOUCHED** at commit `0a764fd23dd1b24070b3d09c24f54e698a3e4ae6` (authored Sat Oct 17 01:57:37 2026 UTC).
  - Active daemon processes: PID 1002 (`uvicorn control_plane.api:app`), PID 1259 (`python -m control_plane`) running continuously since Oct 17.
  - Zero modification to production configuration, database, or order execution pipelines.

---

## 8. Final Decision & System Recommendation

### Formal Conclusion
**`NO EDGE FOUND` FOR ALL PRE-REGISTERED COMPOSITE HYPOTHESES UNDER MODELED TRANSACTION COSTS.**

### Final Summary
1. Under properly directed confirmatory one-sided testing ($H_0: \mu_{\text{net}} \le 0$), no candidate achieves statistical significance above modeled 9.1 bps trading friction (lowest Net FDR $q = 0.9920$).
2. Out-of-time evaluation on Q1 2024 yields negative net expectancies across all eligible candidates.
3. In accordance with the Ophelia Rule Book and the Deterministic Authority principle, no strategy is authorized or promoted for PAPER or LIVE trading.
4. Absolute safety invariants remain permanently enforced:
   - `TRADING_AUTHORITY = False`
   - `EXECUTION_MODE = SHADOW`
   - `LIVE_ORDERS_FORBIDDEN = True`
