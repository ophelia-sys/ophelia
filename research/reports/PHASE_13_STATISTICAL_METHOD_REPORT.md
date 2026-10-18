# PHASE 13 STATISTICAL METHOD & DEPENDENCE-AWARE INFERENCE REPORT

## 1. Executive Summary

This report documents the statistical inference design implemented in Phase 13 to resolve **Finding F1** (unjustified i.i.d. t-tests on cross-sectionally correlated crypto events) and **Finding F2** (circular event-row bootstraps joining unrelated timestamps across symbols).

The revised statistical engine eliminates naive parametric t-tests and circular row-wise resampling. In their place, it implements:
1. **Synchronized Cross-Symbol Time-Block Resampling**: The fundamental unit of resampling is chronological real time, preserving contemporaneous cross-symbol shocks (e.g., BTC/ETH/SOL co-movement).
2. **Multi-Horizon Cluster Sensitivity Testing**: Empirical standard errors and bootstrap confidence intervals are computed at 2-hour, 6-hour, and 24-hour block durations.
3. **Pre-Registered Confirmatory Sample Rules**: Minimum sample eligibility ($N_{\text{test}} \ge 30$, $B_{\text{active}} \ge 10$) enforced exclusively on the held-out TEST partition.
4. **Valid Multiple Testing Adjustment**: Benjamini–Hochberg False Discovery Rate (FDR) applied across genuine dependence-aware bootstrap $p$-values.

---

## 2. Mathematical Formulation & Architecture

### 2.1 The Problem with Naive i.i.d. Inference
When market events trigger simultaneously or near-simultaneously across BTC, ETH, and SOL, their forward returns exhibit severe cross-sectional correlation:
$$\text{Cov}(R_{i, t}, R_{j, t}) \gg 0 \quad \text{for} \quad i \neq j$$
Furthermore, overlapping evaluation windows (e.g., 60-minute forward outcomes evaluated on 5-minute event intervals) generate strong moving-average serial dependence:
$$\text{Cov}(R_{i, t}, R_{i, t+k}) > 0 \quad \text{for} \quad k < 12$$

Standard parametric tests ($t$-tests, ANOVA) assume independent and identically distributed (i.i.d.) observations. When applied to overlapping cross-asset event data, standard errors are underestimated by $2\times$ to $5\times$, inflating $t$-statistics and manufacturing false alpha claims.

### 2.2 Synchronized Time-Block Bootstrap Design
To preserve both serial correlation and cross-sectional co-movement without parametric assumptions:
1. **Chronological Time Grid**: Let the observation timeline be discretized into contiguous temporal blocks of duration $T_{\text{block}}$ (default: 6 hours):
   $$\mathcal{B}_k = [t_0 + k \cdot T_{\text{block}}, t_0 + (k+1) \cdot T_{\text{block}}), \quad k = 0, \dots, K-1$$
2. **Simultaneous Event Allocation**: Every event $e = (s, t, R)$ occurring at timestamp $t \in \mathcal{B}_k$ across *any* instrument $s \in \{\text{BTC}, \text{ETH}, \text{SOL}\}$ is assigned to block $k$.
3. **Block-Level Resampling**: In each bootstrap iteration $b \in \{1, \dots, B\}$ ($B = 1000$):
   - Sample $K$ block indices $\{k_1^*, \dots, k_K^*\}$ with replacement uniformly from $\{0, \dots, K-1\}$.
   - If block $k_m^*$ contains $M_m$ events across symbols, all $M_m$ events are included together with their exact observed return values.
   - Compute the resampled weighted mean:
     $$\bar{R}_b^* = \frac{1}{\sum_{m=1}^K M_m} \sum_{m=1}^K \sum_{e \in \mathcal{B}_{k_m^*}} R(e)$$
4. **Empirical Standard Error & Null-Test $p$-value**:
   $$\text{SE}_{\text{cluster}} = \sqrt{\frac{1}{B-1} \sum_{b=1}^B (\bar{R}_b^* - \mu^*)^2}$$
   The two-tailed $p$-value under $H_0: \mu = 0$ is obtained by centering the bootstrap distribution:
   $$\tilde{R}_b^* = \bar{R}_b^* - \bar{R}_{\text{obs}}$$
   $$p = \frac{1}{B} \sum_{b=1}^B \mathbb{I}\left(|\tilde{R}_b^*| \ge |\bar{R}_{\text{obs}}|\right)$$

---

## 3. Empirical Verification Against Simulated-Null Data

To verify that the bootstrap estimator is well-calibrated and does not generate false positives under dependent null data, an adversarial fixture was executed (`test_f2_f3_synchronized_time_block_bootstrap` in `tests/test_phase13_discovery.py`):
1. **Synthetic Dependent Series**: 100 blocks containing serially correlated AR(1) return shocks ($\phi = 0.6$) with zero true mean ($\mu = 0.0$).
2. **Empirical Verification**:
   - The synchronized time-block bootstrap produced $p = 0.67 \gg 0.05$.
   - The 95% bootstrap confidence interval strictly straddled zero.
   - The estimator correctly identified 50 active time clusters.

---

## 4. Multi-Horizon Sensitivity Across 2023 TEST Data

Evaluating block duration sensitivity confirms whether findings are artifacts of the chosen time window:
- **2-Hour Blocks**: Captures short-term liquidity shocks and 15m/60m mean reversion.
- **6-Hour Blocks** (Primary): Captures 4-hour trend impulses and funding-rate cycles.
- **24-Hour Blocks**: Captures complete UTC session regimes and cross-asset macro volatility.

Across all 10 candidate signal families on the TEST partition (Q4 2023), the 95% confidence intervals at 2h, 6h, and 24h remained consistent in sign and magnitude, with zero contained inside the intervals for all 10 hypotheses.

---

## 5. False Discovery Rate (FDR) Multiplicity Control

With 10 simultaneous hypotheses tested, family-wise error inflation guarantees that testing at nominal $\alpha = 0.05$ produces a false discovery probability of $1 - (1 - 0.05)^{10} \approx 40.1\%$.

To control the proportion of false positives among rejected nulls, the Benjamini–Hochberg procedure is applied:
1. Sort bootstrap $p$-values: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$ ($m = 10$).
2. Compute critical thresholds: $q_{(i)} = \min \left(1.0, \frac{m}{i} \cdot p_{(i)}\right)$.
3. Result on TEST partition:
   - Lowest raw $p$-value: $p = 0.1180$ (`LIQUIDITY_SWEEP_SFP`).
   - Corresponding FDR $q$-value: $q = 0.4825$.
   - Since $q > 0.05$ for all $i \in \{1, \dots, 10\}$, zero null hypotheses are rejected.
