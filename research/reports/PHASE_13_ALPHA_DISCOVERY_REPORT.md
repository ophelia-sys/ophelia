# PHASE 13 QUANTITATIVE ALPHA DISCOVERY REPORT — 2023 CANONICAL UNIVERSE

## Executive Summary & Definitive Research Conclusion

**Definitive Conclusion**: `NO EDGE FOUND`

Across the 2023 historical universe (BTCUSDT, ETHUSDT, SOLUSDT; 1,576,800 1-minute bars; 170,450 candidate events; 1,363,600 forward outcomes; 632,908 stop evaluations), after correcting all audit defects (resampling grid integrity, Wilder ATR warm-up, 4H EMA gap resets, causal representative-turnover VWAP, causal HTF indexing, and strict synchronized time-block inference):

1. **Zero Statistically Supported Alpha Signals**: Not a single one of the 10 pre-registered candidate signal families demonstrated a statistically significant directional edge after Benjamini–Hochberg False Discovery Rate (FDR) control at $q < 0.05$ on the confirmatory held-out TEST partition (October 16, 2023 – December 31, 2023 UTC).
2. **Economic Friction Exceeds Gross Expectancy**: The two signals with positive nominal gross returns on TEST (`HTF_ALIGNED_DISPLACEMENT` at +5.83 bps, $p = 0.189$; `LIQUIDITY_SWEEP_SFP` at +5.08 bps, $p = 0.118$) fail to clear the baseline transaction friction model (9.1 bps round-trip taker fees + adverse slippage). Net expectancy is negative (-3.27 bps and -4.02 bps, respectively).
3. **Stop-Room Erosion**: All four structural and ATR stop models on the held-out TEST split produced negative average net R (-0.25 R to -0.40 R) due to stop-distance friction scaling, premature stop-out rates (Class A: 18.7% - 45.5%), and low clean-trend continuation (Class C: 15.2% - 35.8%).

---

## 1. Experimental Design & Pre-Registered Protocol Boundary

- **Dataset**: `data/processed/binance_um_universe_1m_v2.parquet`
  - SHA-256: `d2e839edecfae88b798993cff9545fa626071efcb722f266fbe15e0bea3e20b5`
  - Instruments: `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (Binance USDT-M Futures)
  - Period: 2023-01-01 00:00:00 UTC to 2023-12-31 23:59:00 UTC (365 days, 525,600 minutes/symbol, zero missing timestamps)
- **Chronological Partitions & Embargo**:
  - `TRAIN` (Exploration): 2023-01-01 00:00:00 to 2023-07-31 23:59:00 UTC (7 months)
  - `EMBARGO_1`: 2023-08-01 00:00:00 to 2023-08-01 23:59:00 UTC (24 hours purge)
  - `VALIDATION` (Selection): 2023-08-02 00:00:00 to 2023-10-14 23:59:00 UTC (2.5 months)
  - `EMBARGO_2`: 2023-10-15 00:00:00 to 2023-10-15 23:59:00 UTC (24 hours purge)
  - `TEST` (Confirmatory): 2023-10-16 00:00:00 to 2023-12-31 23:59:00 UTC (2.5 months)
- **Transaction Cost Model**:
  - Baseline Friction: 9.1 bps (0.091%) round-trip (4.0 bps entry taker fee + 4.0 bps exit fee + 1.1 bps slippage / conservative model up to 15 bps).

---

## 2. Complete Candidate Signal Family Results (Confirmatory TEST Partition)

Primary evaluation horizon: 60-minute forward directional return.
Dependence-aware inference: Synchronized 6-hour time-block bootstrap across all symbols simultaneously (1,000 resamples), with block sensitivity tested at 2 hours and 24 hours.
Multiple testing control: Benjamini–Hochberg False Discovery Rate across the 10 candidate hypotheses.

| Hypothesis / Event Class | $N_{\text{total}}$ | $N_{\text{test}}$ | Active 6h Clusters | TEST Win Rate | TEST Mean Return (Gross) | Net Return (9.1 bps) | 95% Bootstrap CI (6h) | Raw Bootstrap $p$-value | FDR $q$-value | Confirmatory Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CVD_ACCELERATION** | 20,992 | 4,355 | 256 | 46.11% | -0.0146% (-1.46 bps) | -10.56 bps | [-0.0803%, +0.0520%] | 0.6650 | 0.7389 | NO EDGE |
| **HTF_ALIGNED_DISPLACEMENT** | 4,469 | 898 | 264 | 48.00% | +0.0583% (+5.83 bps) | -3.27 bps | [-0.0270%, +0.1434%] | 0.1890 | 0.4825 | NO EDGE |
| **LIQUIDITY_SWEEP_SFP** | 5,395 | 1,337 | 302 | 55.05% | +0.0508% (+5.08 bps) | -4.02 bps | [-0.0115%, +0.1149%] | 0.1180 | 0.4825 | NO EDGE |
| **MOMENTUM_DISPLACEMENT** | 9,998 | 1,821 | 304 | 44.92% | -0.0119% (-1.19 bps) | -10.29 bps | [-0.0616%, +0.0384%] | 0.6475 | 0.7389 | NO EDGE |
| **ORDER_FLOW_VWAP_CONFLUENCE**| 2,058 | 196 | 125 | 43.37% | -0.0636% (-6.36 bps) | -15.46 bps | [-0.2045%, +0.0773%] | 0.3770 | 0.6283 | NO EDGE |
| **RANGE_EXPANSION** | 1,351 | 146 | 108 | 47.95% | -0.0164% (-1.64 bps) | -10.74 bps | [-0.1746%, +0.1419%] | 0.4640 | 0.6629 | NO EDGE |
| **RVOL_EXPANSION** | 24,198 | 5,648 | 304 | 45.89% | -0.0188% (-1.88 bps) | -10.98 bps | [-0.0471%, +0.0095%] | 0.1930 | 0.4825 | NO EDGE |
| **VALUE_AREA_BOUNDARY** | 24,534 | 5,042 | 296 | 49.39% | -0.0248% (-2.48 bps) | -11.58 bps | [-0.0564%, +0.0067%] | 0.1230 | 0.4825 | NO EDGE |
| **VWAP_DEVIATION** | 54,411 | 12,396 | 304 | 55.12% | +0.0005% (+0.05 bps) | -9.05 bps | [-0.0469%, +0.0479%] | 0.9845 | 0.9845 | NO EDGE |
| **VWAP_RECLAIM** | 23,044 | 4,357 | 288 | 48.45% | +0.0068% (+0.68 bps) | -8.42 bps | [-0.0385%, +0.0520%] | 0.3080 | 0.6160 | NO EDGE |

---

## 3. Block-Length Sensitivity Analysis (Findings F2, F3)

To confirm that inference conclusions are robust to time-dependence assumptions, all candidates were evaluated across three distinct synchronized time-block durations:
- **2 Hours**: High cluster granularity (~450–670 active blocks)
- **6 Hours**: Primary configuration capturing multi-hour autocorrelations (~250–304 active blocks)
- **24 Hours**: Full UTC session blocks capturing intraday day-of-week shocks (~77 active blocks)

### Detailed Sensitivity for Promising Nominal Candidates:

1. **`LIQUIDITY_SWEEP_SFP`**:
   - 2h Block: 95% CI [-0.0106%, +0.1146%], $p = 0.1210$ (650 clusters)
   - 6h Block: 95% CI [-0.0115%, +0.1149%], $p = 0.1180$ (302 clusters)
   - 24h Block: 95% CI [-0.0262%, +0.1265%], $p = 0.1835$ (77 clusters)
   - **Conclusion**: Confidence interval encompasses zero under all block durations; fails significance at $\alpha = 0.05$ across all scales.

2. **`HTF_ALIGNED_DISPLACEMENT`**:
   - 2h Block: 95% CI [-0.0257%, +0.1389%], $p = 0.1855$ (456 clusters)
   - 6h Block: 95% CI [-0.0270%, +0.1434%], $p = 0.1890$ (264 clusters)
   - 24h Block: 95% CI [-0.0342%, +0.1523%], $p = 0.2280$ (77 clusters)
   - **Conclusion**: Zero is well within the 95% interval across all horizons.

---

## 4. Confirmatory Stop-Room Performance (TEST Partition)

Total TEST evaluations: 133,031 across 4 models (Findings C1-C4, F5).

| Stop Model | Sample Size | Median SL % | Mean Gross R | Mean Net R (Fee+Slip) | Class A (Stop-out) | Class B (Premature Stop) | Class C (Clean Winner) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **STOP_5M_SWING** | 32,276 | 0.44% | +0.0090 R | **-0.4041 R** | 27.66% | 12.30% | 25.63% |
| **STOP_15M_SWING** | 33,426 | 0.59% | +0.0046 R | **-0.3865 R** | 24.76% | 11.68% | 23.01% |
| **STOP_1H_SWING** | 31,133 | 1.15% | -0.0031 R | **-0.2548 R** | 18.67% | 7.21% | 15.18% |
| **STOP_ATR_ENVELOPE**| 36,196 | 0.41% | +0.0032 R | **-0.2838 R** | 45.50% | 9.99% | 35.81% |

### Stop Room Insights:
1. **Gross R is Negligible**: Gross R before friction is essentially zero across all models (+0.003 to +0.009 R).
2. **Friction Degradation**: When real crypto perpetual fees (0.04% taker) and slippage (0.02% per leg) are applied to tight structural stops (median SL distance 0.41% - 0.59%), friction consumes **38% to 40% of the entire risk unit R**.
3. **Class B Resumption**: 11.7% to 12.3% of 5m/15m swing stops suffer Class B resumption (the trade hits SL, then promptly reaches TP within the 120-minute forward window without further adverse excursion).

---

## 5. Candidate Ranking & Next Research Steps

Since all 10 candidates failed the confirmatory criteria on TEST (p > 0.05, FDR q > 0.48, net negative after 9.1 bps friction), **no candidate qualifies for out-of-time production promotion**.

If further research is commissioned on the separate out-of-time dataset (`data/processed/phase12_fresh_universe_1m.parquet`, Q1 2024), the only candidates demonstrating exploratory promise for multi-feature composite modeling are:
1. `LIQUIDITY_SWEEP_SFP` (highest win rate at 55.05%, lowest raw p-value 0.118).
2. `HTF_ALIGNED_DISPLACEMENT` (highest gross return at +5.83 bps).

Neither candidate can be traded standalone with structural stops under current taker fee assumptions.
