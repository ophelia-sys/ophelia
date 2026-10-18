# OPHELIA PHASE 13 — PRE-REGISTERED QUANTITATIVE ALPHA DISCOVERY PROTOCOL

**Protocol Status**: LOCKED & PRE-REGISTERED  
**Date**: October 18, 2026  
**Repository**: `ophelia-sys/ophelia`  
**Execution Environment**: Local Deterministic Research Engine (`control_plane/phase13_discovery_engine.py`)  
**Safety Status**: `TRADING_AUTHORITY=False`, `EXECUTION_MODE=SHADOW`, `LIVE_ORDERS_FORBIDDEN=True`  

---

## 1. RESEARCH OBJECTIVE & BOUNDARY

To conduct an objective, causal, dependence-aware quantitative alpha discovery study evaluating Ophelia's ten existing signal families across 2023 Binance USD-M Perpetual Futures 1-minute historical data after full transaction cost deduction.

### 1.1 Data Boundary
- **Primary Research Universe**: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`
- **Source File**: `data/processed/binance_um_universe_1m_v2.parquet`
- **File Checksum (SHA-256)**: `d2e839edecfae88b798993cff9545fa626071efcb722f266fbe15e0bea3e20b5`
- **Evaluation Period**: 2023-01-01 00:00:00 UTC to 2023-12-31 23:59:00 UTC (365 calendar days = 525,600 1-minute intervals per symbol).
- **Out-of-Time Reserve**: `data/processed/phase12_fresh_universe_1m.parquet` (2023-12-01 to 2024-03-31, 122 calendar days) reserved exclusively for fresh validation of qualified candidates.

---

## 2. CHRONOLOGICAL PARTITIONS & EMBARGO

To prevent lookahead and temporal information leakage across splits:
- **TRAIN (Exploration & Calibration)**: 2023-01-01 00:00:00 UTC to 2023-06-30 23:59:00 UTC (181 days, ~50%).
- **EMBARGO 1**: 2023-07-01 00:00:00 UTC to 2023-07-07 23:59:00 UTC (7 days, 10,080 minutes discarded to purge path overlap).
- **VALIDATION (Candidate Selection)**: 2023-07-08 00:00:00 UTC to 2023-09-30 23:59:00 UTC (85 days, ~23%).
- **EMBARGO 2**: 2023-10-01 00:00:00 UTC to 2023-10-07 23:59:00 UTC (7 days, 10,080 minutes discarded).
- **TEST (Strictly Locked Confirmatory)**: 2023-10-08 00:00:00 UTC to 2023-12-31 23:59:00 UTC (85 days, ~23%).

---

## 3. SIGNAL FAMILIES (THE HYPOTHESIS FAMILY)

The pre-registered hypothesis family comprises Ophelia's ten existing signal classes evaluated at the primary 60-minute forward horizon:
1. `MOMENTUM_DISPLACEMENT` (LONG / SHORT)
2. `RVOL_EXPANSION` (LONG / SHORT)
3. `VOLATILITY_COMPRESSION` (LONG / SHORT)
4. `VOLATILITY_EXPANSION` (LONG / SHORT)
5. `VWAP_RECLAIM` (LONG / SHORT)
6. `LIQUIDITY_SWEEP_SFP` (LONG / SHORT)
7. `VALUE_AREA_BOUNDARY` (LONG / SHORT)
8. `RANGE_EXPANSION` (LONG / SHORT)
9. `HTF_ALIGNED_DISPLACEMENT` (LONG / SHORT)
10. `ORDER_FLOW_VWAP_CONFLUENCE` (LONG / SHORT)

Family size $M = 10$. Multiple testing correction is strictly applied across all evaluated candidate hypotheses.

---

## 4. CAUSALITY, PROVENANCE & DATA INTEGRITY RULES

1. **Exact Regular Grid**: Resampling strictly verifies integer minute intervals. Incomplete buckets are dropped; no gap-filling or candle interpolation.
2. **CVD Missing-Flow Precedence**: `MISSING_FLOW > INSUFFICIENT_HISTORY > ZERO_VARIANCE > AVAILABLE`. Order-flow features emit events only when status is strictly `AVAILABLE`.
3. **Session VWAP Turnover Provenance**: Session VWAP uses cumulative `quote_volume / volume` when valid turnover exists, otherwise representative turnover. Incomplete sessions are invalidated until next 00:00 UTC. Dispersion uses weighted Welford accumulation on between-bar representative transaction prices.
4. **HTF Alignment**: Higher-timeframe candles are merged strictly on decision timestamp $T_{\text{decision}} \ge T_{\text{completion}}$.
5. **No Synthetic Stop Substitutions**: Structural swing stops (`STOP_5M_SWING`, `STOP_15M_SWING`, `STOP_1H_SWING`) strictly require valid swing prices. Missing swings are excluded from evaluation diagnostics.
6. **Geometry Validation**: Stops on the wrong side of entry or with sub-minimum distance ($\Delta_{\text{stop}} < 10^{-4}$) are excluded without price clamping or ATR substitution.

---

## 5. TRANSACTION FRICTION & STOP-ROOM MODELS

### 5.1 Friction in R Scaling Law
Friction in R units scales inversely with percentage stop distance:
$$\text{Friction}_R = \frac{\text{Friction Rate}}{\text{Stop Distance } \%}$$
$$\text{Net } R = \text{Gross } R - \text{Friction}_R$$

### 5.2 Friction Scenarios
- **Zero Friction**: 0.0 bps (Theoretical baseline).
- **Fee Only**: 5.0 bps (0.05% round-trip: maker/taker blend).
- **Modeled Baseline**: 9.1 bps (0.091% round-trip: 2.5 bps entry maker + 5.0 bps exit taker + 1.6 bps adverse slippage).
- **Conservative Friction**: 15.0 bps (0.15% round-trip: stressed taker + slippage).

---

## 6. STATISTICAL DESIGN & CONFIRMATORY INFERENCE

1. **TEST Split Isolation**: Confirmatory inference is evaluated exclusively on the TEST split. TRAIN and VALIDATION splits are reported separately for exploratory description.
2. **Sample Size Eligibility**:
   - Minimum TEST event count: $N_{\text{test}} \ge 30$.
   - Minimum active time clusters: $B_{\text{test}} \ge 10$ distinct 6-hour blocks.
   - Hypotheses failing eligibility are classified as `INCONCLUSIVE_INSUFFICIENT_TEST_SAMPLE`.
3. **Synchronized Time-Block Bootstrap**:
   - Preserves contemporaneous cross-symbol correlation and serial dependence by resampling chronological time blocks simultaneously across all symbols.
   - Primary block duration: 6 hours (matching 60m trade horizon + 120m path monitoring).
   - Sensitivity evaluation: 2-hour and 24-hour block durations.
   - Resampling iterations: $B = 2,000$.
   - Confidence Interval: Two-sided empirical 95% bootstrap CI.
   - Empirical p-value: Centered under $H_0: \mu = 0$.
4. **Multiple Testing Control**: Benjamini-Hochberg False Discovery Rate (FDR) applied strictly to the family of evaluated TEST p-values at target $\alpha = 0.05$.

---

## 7. OBJECTIVE DECISION CRITERIA & CONCLUSION LABELS

Every signal candidate will receive exactly one conclusion label:

- **`STATISTICALLY SUPPORTED CANDIDATE UNDER MODELED COSTS`**:
  - Net Expectancy > 0 under 9.1 bps friction baseline.
  - Confirmatory TEST sample meets sample eligibility ($N_{\text{test}} \ge 30, B_{\text{test}} \ge 10$).
  - Dependence-aware 95% CI strictly excludes zero ($\text{CI}_{\text{low}} > 0$).
  - Benjamini-Hochberg FDR $q < 0.05$.
  - Stable positive expectancy across 2h, 6h, and 24h block sensitivity.
- **`EXPLORATORY CANDIDATE — NOT CONFIRMED`**:
  - Positive net return in TRAIN or VALIDATION, but fails to maintain statistically significant positive net expectancy on held-out TEST after multiple testing adjustment.
- **`NO EDGE FOUND`**:
  - Flat or negative net return across all splits under modeled friction, or gross return insufficient to overcome transaction costs.
- **`INCONCLUSIVE`**:
  - Sample size insufficient for reliable inference ($N_{\text{test}} < 30$), or conflicting results under block sensitivity.
