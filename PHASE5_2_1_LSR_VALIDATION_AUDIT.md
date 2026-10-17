# PHASE 5.2.1 LSR VALIDATION AUDIT

> [!WARNING]
> **Classification: INCONCLUSIVE**
> LSR has sufficient evidence to justify further research, but not enough evidence for unconditional production retention. It is marked as **RESEARCH_CANDIDATE** (STATUS = INCONCLUSIVE) and will NOT be integrated into the production probability engine at this time.

## 1. Executive Summary & Multiple Testing
The research has now tested 6 symbols, multiple LSR configurations, multiple folds, multiple years, and multiple economic thresholds. Research multiplicity must be explicitly acknowledged: evaluating multiple assets and regimes increases the likelihood of finding isolated significant results by chance.

While LSR demonstrates average Brier improvement and robustness to missing-data treatment, its effect size is very small, block bootstrap CIs cross zero for 4/6 symbols, DM tests fail significance for SOL/XRP, permutation fails in multiple folds, and no symbol becomes profitable at 12bps. Therefore, the effect does not pass a strict threshold for unconditional production use.

## 2. Statistical Tests (DM & Permutation Stability)
The effect does NOT pass a strict "significant in every fold" criterion. Permutation failures occur in multiple independent walk-forward folds.

| Symbol | DM Stat | DM p-val | Permutation p-vals (Folds 1, 2, 3) |
|---|---|---|---|
| BTCUSDT | 2.192 | 0.0284 | 0.1089, 0.0099, 0.0099 |
| ETHUSDT | 2.700 | 0.0069 | 0.0099, 0.0099, 0.0099 |
| SOLUSDT | 1.575 | 0.1153 | 0.8713, 0.0099, 0.0099 |
| XRPUSDT | 0.282 | 0.7776 | 0.0297, 0.8515, 0.0198 |
| BNBUSDT | 2.171 | 0.0299 | 0.0594, 0.1089, 0.0099 |
| ADAUSDT | 2.588 | 0.0096 | 0.0198, 0.1584, 0.0099 |

**DM Test Interpretation**: 4/6 symbols reject the equal-predictive-accuracy null at alpha=0.05. Given 6 tests, multiple testing correction tempers this significance.

## 3. Confidence Intervals (Block Bootstrap)
Only ETH and ADA have intervals that clearly exclude zero. BTC, SOL, XRP, and BNB have intervals containing zero.

| Symbol | 95% CI ΔBrier | 95% CI ΔGross (bps) |
|---|---|---|
| BTCUSDT | [-0.000691, 0.000030] | [0.34, 1.30] |
| ETHUSDT | [-0.000618, -0.000043] | [0.29, 1.43] |
| SOLUSDT | [-0.000339, 0.000088] | [-0.27, 1.42] |
| XRPUSDT | [-0.000141, 0.000113] | [-0.39, 0.35] |
| BNBUSDT | [-0.000266, 0.000008] | [-0.18, 0.30] |
| ADAUSDT | [-0.000346, -0.000006] | [-0.22, 0.78] |

## 4. Economic Result
LSR currently demonstrates incremental predictive/ranking information, but NOT a standalone profitable trading edge. All six remain negative after 12bps transaction costs.

| Symbol | BASE Net (12bps) | LSR3 Net (12bps) | Δ Net (bps) |
|---|---|---|---|
| BTCUSDT | -11.87 | -11.14 | +0.73 |
| ETHUSDT | -11.86 | -11.13 | +0.73 |
| SOLUSDT | -12.01 | -11.44 | +0.57 |
| XRPUSDT | -12.37 | -12.32 | +0.05 |
| BNBUSDT | -12.00 | -11.93 | +0.07 |
| ADAUSDT | -12.03 | -12.02 | +0.02 |

## 5. Temporal Stability
The effect is not uniformly stable across regimes.
- **BTC**: relatively stable
- **ETH**: relatively stable
- **SOL**: negative/inconsistent
- **XRP**: relatively stable but statistically weak
- **BNB**: regime-dependent
- **ADA**: relatively stable

| Symbol | BASE 2022 | LSR3 2022 | BASE 2023 | LSR3 2023 |
|---|---|---|---|---|
| BTCUSDT | 0.191889 | 0.191741 | 0.167486 | 0.164606 |
| ETHUSDT | 0.196115 | 0.195509 | 0.167063 | 0.164575 |
| SOLUSDT | 0.194949 | 0.195141 | 0.214169 | 0.215380 |
| XRPUSDT | 0.192824 | 0.192737 | 0.149915 | 0.148247 |
| BNBUSDT | 0.195668 | 0.195604 | 0.232140 | 0.233070 |
| ADAUSDT | 0.193640 | 0.193566 | 0.156964 | 0.154536 |

## 6. Cross-Asset Effect Size
| Metric | All Years | 2022 | 2023 |
|---|---|---|---|
| Mean ΔBrier | -0.000187 | -0.000131 | -0.001220 |
| Median ΔBrier | -0.000159 | -0.000080 | -0.002048 |
| Std Dev | 0.000112 | 0.000238 | 0.001661 |
| Min | -0.000332 | -0.000607 | -0.002880 |
| Max | -0.000016 | 0.000192 | 0.001211 |
| Negative Direction (Improvement) | 6/6 | 5/6 | 4/6 |

## 7. Next Research Question
Before deciding whether LSR deserves production status, the next question is:
> *Does LSR provide incremental economic value when combined with the next independent information source?*

The next candidate is CVD / aggressor order flow. Current Phase 5.2.1 results and manifest are now **FROZEN** as a historical research record.
