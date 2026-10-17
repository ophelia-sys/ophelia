# OPHELIA — PHASE 10.1 RETEST-STATE TIMESFM VALIDATION + 5M FORECAST ARCHITECTURE REPORT
**Correction of Phase 10 Empirical Methodology & Forensic Trading Utility Evaluation**

- **Status**: EMPIRICALLY AUDITED / INCONCLUSIVE (TRADING UTILITY NOT ESTABLISHED)
- **Primary Architecture**: `TIMESFM_PRIMARY_5M` (12 x 5m steps: +15m, +30m, +45m, +60m)
- **Research Architecture**: `TIMESFM_1M_RESEARCH` (60 x 1m steps)
- **Candidate Generator**: Causal Retest State Machine (`IDLE -> WAITING_FOR_RETEST -> RETEST_ZONE_TOUCHED -> CONFIRMING_REJECTION -> ENTRY_READY`)
- **Compatibility Classification**: Multi-Metric Geometry (`SUPPORTIVE`, `MIXED`, `UNSUPPORTIVE`, `NOT_AVAILABLE`)
- **Calibration Status**: `NOT CALIBRATED` (Dispersion: `DISPERSION_BUCKET_UNCALIBRATED`)
- **Trading Authority**: `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`
- **Audit Date**: 2026-10-02

---

## 1. Executive Summary & Audit of Methodological Problems

Phase 10 established vital infrastructure: Binance USD-M kline/trades ingestion, canonical multi-venue symbol resolution, cross-venue basis tracking, candidate outcome tracking, and Android UI cards. However, Phase 10's empirical conclusions were **methodologically flawed** and are rejected as trading validation.

### Explicit Audit of Phase 10 Methodological Defects
1. **Breakout-High Bias**: Phase 10 candidate detection used raw breakout bar closes (`cur_px > max_h`), triggering at the peak of short-term expansion before pullbacks, rather than confirmed retests.
2. **Binary Rule Collapse**: The compatibility requirement $q_{50} \ge entry$ (for LONG) rejected all 203 candidates because mean-reverting forecasts after local expansion naturally project pullbacks ($q_{50} < entry$).
3. **Empty Treatment Group**: Zero compatible candidates meant there was no treated population. Measuring incremental improvement in trading outcomes was mathematically impossible.
4. **Invalid Causal Attribution**: Stating that "100% of negative drift was eliminated" or that "6.78R was preserved" was invalid. An empty treatment group cannot establish capital preservation or strategy alpha.
5. **Timeframe Misalignment**: The Phase 10 implementation used a 1m context / 60-step horizon instead of the primary 5m / 12-step architecture.
6. **Uncalibrated Dispersion**: Labels of $<2\%$ (TIGHT), $2\text{--}5\%$ (MODERATE), and $>5\%$ (WIDE) were heuristic retail assumptions without empirical calibration.
7. **Sorted Quantiles $\ne$ Calibrated Quantiles**: Monotonically sorting raw quantiles prevents crossing but does not constitute quantile calibration.
8. **Sample Boundary**: 4 days of historical data is a screening sample, not robust trading validation.
9. **Basis Metric Conflation**: 99th percentile basis ($p_{99}$) was inconsistently labeled as "max basis" in prior summaries.

---

## 2. Experimental Families & Architecture Comparison

Phase 10.1 separates experimental families into distinct regimes:

| Feature / Dimension | `PHASE10_BREAKOUT_SCREENING_V1` (Legacy) | `PHASE10_RETEST_ENTRY_READY_V1` (Primary 5m) | `PHASE10_TIMESFM_1M_RESEARCH_V1` (Research 1m) |
| :--- | :--- | :--- | :--- |
| **Trigger Point** | Breakout Candle Close (`cur_px > max_h`) | Confirmed `ENTRY_READY` post-retest rejection | Confirmed `ENTRY_READY` post-retest rejection |
| **Forecast Resolution**| 1m (60 steps) | **5m (12 steps)** | 1m (60 steps) |
| **Path Horizons** | +15m, +30m, +45m, +60m | **+15m, +30m, +45m, +60m** | +15m, +30m, +45m, +60m |
| **Causality Enforcement**| $ts \le T$ | **Closed 5m bar completion: $ts + 300\text{k} \le T$** | Closed 1m bar completion: $ts + 60\text{k} \le T$ |
| **Quantile Handling** | Monotonically Sorted (Heuristic) | **Raw Persisted + Crossing Detection + Monotonic Sort** | Raw Persisted + Crossing Detection + Monotonic Sort |
| **Compatibility Rule**| Binary: $q_{50} \ge entry$ | **Multi-Metric Geometry (Slope, Returns, Medians)** | Multi-Metric Geometry (Slope, Returns, Medians) |
| **Treatment Cohorts**| 0 Compatible (Empty) | **13 Compatible, 13 Incompatible, 79 Neutral** | 14 Compatible, 25 Incompatible, 66 Neutral |

---

## 3. Retest State Machine & Candidate Generation

Candidates are generated strictly causally through `CausalRetestEngine` (`control_plane/retest_candidate_generator.py`):

```
IDLE
  ↓ (Displacement >= 1.5 ATR + Volume Expansion + Swing Break)
WAITING_FOR_RETEST
  ↓ (Candle low penetrates zone_high without closing below zone_low - 0.5 ATR)
RETEST_ZONE_TOUCHED
  ↓ (Rejection candle closes in trade direction above zone_low)
CONFIRMING_REJECTION
  ↓ (Taker Volume CVD positive + RVOL >= 1.0)
ENTRY_READY  ───► [FREEZE CONTEXT & GENERATE TIMESFM 5M FORECAST]
```

### Candidate Geometry Invariants
- **LONG**: $SL < Entry < TP_1 < TP_2$; $Risk = Entry - SL > 0$; Reward $TP_1 - Entry \ge Risk$ ($R:R \ge 1.0$).
- **SHORT**: $SL > Entry > TP_1 > TP_2$; $Risk = SL - Entry > 0$; Reward $Entry - TP_1 \ge Risk$ ($R:R \ge 1.0$).
- Normalized realized R:
  $$\text{Normalized } R = \frac{\text{Directional PnL}}{\text{Normalized Risk Amount}}$$

---

## 4. Empirical Candidate Outcomes: Database Audit

All statistics below are computed directly from the SQLite database (`control_data/market_1m.db`) across continuous Binance USD-M Futures data for BTCUSDT, ETHUSDT, and SOLUSDT:

### 4.1 Primary Experiment: `PHASE10_RETEST_ENTRY_READY_V1` (5m Architecture)

| Asset | Cohort | Candidate Count | Win Rate (TP1) | Profit Factor | Net R | Mean MFE | Mean MAE | Treatment Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BTCUSDT** | Base Strategy | 37 | 16.22% | 0.82 | -3.13 | $241.65 | -$254.91 | EVALUATED |
| | Compatible | 2 | 0.00% | 0.00 | -2.00 | $78.75 | -$529.75 | EVALUATED |
| | Incompatible | 2 | 0.00% | 0.87 | -0.13 | $785.80 | -$197.95 | EVALUATED |
| | Neutral | 33 | 18.18% | 0.93 | -1.00 | $218.54 | -$241.71 | EVALUATED |
| **ETHUSDT** | Base Strategy | 35 | 22.86% | 1.93 | +12.45 | $11.11 | -$9.56 | EVALUATED |
| | Compatible | 8 | 12.50% | 0.79 | -1.24 | $7.96 | -$14.33 | EVALUATED |
| | Incompatible | 4 | 25.00% | 9.32 | +1.58 | $16.03 | -$6.25 | EVALUATED |
| | Neutral | 23 | 26.09% | 2.69 | +12.11 | $11.35 | -$8.47 | EVALUATED |
| **SOLUSDT** | Base Strategy | 33 | 12.12% | 1.17 | +1.93 | $0.60 | -$0.54 | EVALUATED |
| | Compatible | 3 | 0.00% | 1.06 | +0.06 | $0.58 | -$0.80 | EVALUATED |
| | Incompatible | 7 | 0.00% | 6.03 | +1.96 | $0.89 | -$0.55 | EVALUATED |
| | Neutral | 23 | 17.39% | 0.99 | -0.09 | $0.52 | -$0.51 | EVALUATED |
| **AGGREGATE** | **Base Strategy** | **105** | **17.14%** | **1.27** | **+11.25** | **$89.05** | **-$93.18** | **EVALUATED** |
| | **TimesFM Compatible** | **13** | **7.69%** | **0.65** | **-3.18** | **$17.15** | **-$90.51** | **EVALUATED** |
| | **TimesFM Incompatible** | **13** | **7.69%** | **3.16** | **+3.41** | **$126.30** | **-$32.67** | **EVALUATED** |
| | **TimesFM Neutral** | **79** | **20.25%** | **1.35** | **+11.02** | **$94.75** | **-$103.58** | **EVALUATED** |

### 4.2 Legacy Ablation Comparison: `PHASE10_BREAKOUT_SCREENING_V1`

| Cohort | Count | Win Rate | Profit Factor | Net R | Empirical Utility Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Base Strategy (Breakout Close)** | 203 | 12.32% | 0.91 | -6.78 | EVALUATED (Negative Drift Baseline) |
| **TimesFM Compatible ($q_{50} \ge entry$)**| **0** | **N/A** | **N/A** | **0.00** | **NO_ACCEPTED_CANDIDATES / NOT_ESTABLISHED** |
| **TimesFM Incompatible** | 61 | 13.11% | 1.73 | +9.67 | EVALUATED |
| **TimesFM Neutral** | 142 | 11.97% | 0.72 | -16.45 | EVALUATED |

---

## 5. Quantitative Finding & Forensic Conclusion on Trading Utility

### Core Empirical Discovery
1. **TimesFM Does NOT Provide Incremental Trading Alpha at `ENTRY_READY`**:
   - The Base Strategy alone across 105 retest candidates achieved **+11.25 Net R** (Profit Factor 1.27).
   - Filtering with TimesFM "COMPATIBLE" degraded performance to **-3.18 Net R** (Profit Factor 0.65, Win Rate 7.69%).
   - Trades classified as "INCOMPATIBLE" by TimesFM actually delivered **+3.41 Net R** with a 3.16 Profit Factor and higher Mean MFE ($126.30 vs $17.15).
2. **Phase 10 Illusion Explained**:
   - In Phase 10, the filter appeared to "eliminate negative drift" solely because the underlying candidates were buy-at-the-top breakout signals that failed into pullbacks. TimesFM's autoregressive momentum correctly predicted that pullback.
   - When trades are properly executed at the *end* of the pullback (`ENTRY_READY`), TimesFM's linear trend extrapolation penalizes healthy retest consolidation and favors late continuation.
3. **Formal Determination**:
   - **TRADING UTILITY = NOT ESTABLISHED**.
   - TimesFM 3.0 cannot be used as an autonomous order gate or trade disqualifier.
   - TimesFM remains strictly in advisory `SHADOW` observation mode.

---

## 6. Binance vs. BingX Microstructure & Cross-Venue Basis

| Metric | Measured Value | Standard Deviation / Range | Audit Note |
| :--- | :--- | :--- | :--- |
| **BTC Basis Mean** | +0.0017% (+1.7 bps) | $\pm 0.0012\%$ | Aligned within 5 bps normal regime |
| **BTC Basis 99th Percentile ($p_{99}$)**| **+0.0042% (+4.2 bps)** | Elevated Buffer | Strictly separated from maximum |
| **BTC Maximum Observed Basis** | **+0.0068% (+6.8 bps)** | Transient Spike | Peak divergence across test sample |
| **Quote Timestamp Delta** | 12 ms | [4 ms, 38 ms] | Real-time quote synchronization |
| **Estimated Fill Slippage** | 0.02% (2.0 bps) | Nominal | Derived from BingX best bid/ask |

*Terminology Rule Enforced: 99th percentile basis ($p_{99}$) is never labeled "max". The maximum observed basis is strictly tracked as a distinct outlier metric.*

---

## 7. Sustained VPS Runtime Telemetry (Section 30 Verification)

Benchmarked on production VPS (`15.235.193.47`) running Ubuntu Linux, Python 3.14 venv, and live `ophelia-api` & `ophelia-control` services across 40 continuous sampling periods:

| Operational Dimension | Minimum | Maximum | Median | P95 | Target / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CPU Utilization (%)** | 97.7% | 100.0% | 99.7% | 100.0% | Normal under sustained load |
| **RAM Utilization (MB)** | 6,208.0 MB | 6,234.4 MB | 6,218.8 MB | 6,233.5 MB | Stable / No memory leak |
| **Swap Usage (MB)** | 2,086.7 MB | 2,088.7 MB | 2,087.4 MB | 2,088.0 MB | Stable |
| **System Load Average (1m)**| 4.59 | 4.70 | 4.65 | 4.70 | Stable |
| **DB Lock Latency (ms)** | 0.04 ms | 0.45 ms | **0.08 ms** | 0.14 ms | WAL mode excellent (< 1 ms) |
| **API Latency (ms)** | 107.85 ms | 640.45 ms | **112.04 ms** | 502.23 ms | Responsive |
| **TimesFM Candidate Latency**| 1.81 ms | 6.10 ms | **3.70 ms** | 5.52 ms | Fast econometric inference |
| **Binance Stream Health** | CONNECTED | CONNECTED | CONNECTED | CONNECTED | PASS (0 disconnects) |
| **BingX Quote Health** | ALIGNED | ALIGNED | ALIGNED | ALIGNED | PASS (0 stale quotes) |
| **Scheduler Misses** | 0 | 0 | 0 | 0 | PASS |
| **Forecast Failures** | 0 | 0 | 0 | 0 | PASS |

---

## 8. Test Suite Verification (Section 29)

All 16 required tests pass on both local workstation and remote VPS:

1. `test_timesfm_primary_5m_architecture`: **PASS** (12 x 5m steps, full path persisted)
2. `test_timesfm_5m_no_lookahead`: **PASS** (Adversarial future bar corruption yields identical forecast)
3. `test_retest_entry_ready_candidate_generation`: **PASS** (Advances through touch and confirmation)
4. `test_candidate_snapshot_at_entry_ready`: **PASS** (16-char context & snapshot hashes frozen at $T$)
5. `test_timesfm_forecast_freeze`: **PASS** (Stored forecast immutable in SQLite)
6. `test_candidate_direction_neutral_r_calculation`: **PASS** (Signed PnL / positive risk for LONG and SHORT)
7. `test_zero_treatment_population_handling`: **PASS** (Reports `NO_ACCEPTED_CANDIDATES`, never false alpha)
8. `test_compatibility_not_zeroing_entire_population`: **PASS** (Supportive and unsupportive cohorts coexist)
9. `test_quantile_raw_vs_postprocessed`: **PASS** (Raw quantiles recorded, crossing audited, not called calibrated)
10. `test_dispersion_uncalibrated_state`: **PASS** (`DISPERSION_BUCKET_UNCALIBRATED` preserved)
11. `test_basis_percentile_vs_max_consistency`: **PASS** (Max observed basis $\ge p_{99}$, strictly distinct)
12. `test_long_short_outcome_symmetry`: **PASS** (Identical normalized R for symmetrical win/loss geometry)
13. `test_historical_live_boundary`: **PASS** (`TRADING_AUTHORITY = FALSE`, zero order routes)
14. `test_binance_1m_to_5m_continuity`: **PASS** (Aligned non-overlapping 5m bars without data gaps)
15. `test_future_basis_leakage`: **PASS** (Candidate evaluation at $T$ excludes quotes $> T$)
16. `test_future_retest_leakage`: **PASS** (Causal retest evaluation at bar $N$ excludes bar $N+1$)

Regression Test Suite (`tests/test_canonical_multi_venue.py`, `tests/test_binance_data_engine.py`, `tests/test_cross_venue_basis.py`, `tests/test_timesfm_trade_compatibility.py`, `tests/test_candidate_research.py`): **28/28 PASSED (100%)**. Total active suite: **44/44 PASSED**.

---

## 9. Android Observability Parity

- **Screen Updated**: `AutonomousTradingScreen.kt` updated with Phase 10.1 title `MULTI-VENUE & TIMESFM 5M VALIDATION (PHASE 10.1)`.
- **Card Content**: Displays Primary Architecture (`5m / 12-Step Path`), Context (`AT ENTRY_READY`), Evidence Dimensions (`DIR / DISP / COMPAT`), and explicit Calibration notice (`NOT CALIBRATED`).
- **Safety Badge**: Affirms `ADVISORY RESEARCH ONLY • ZERO AUTONOMOUS TRADING AUTHORITY • NO REAL ORDERS OR SLOT MUTATIONS BY ML`.

---

## 10. Unresolved Limitations & Next Steps

1. **Dispersion Calibration**: Raw dispersion is exposed, but historical percentile buckets (e.g. rolling 90-day distribution) require longer longitudinal backfill.
2. **Regime-Conditioned Forecasting**: Current forecaster operates uniformly across chop and trend. Future iterations should condition TimesFM on structural regime state (`TREND` vs `RANGE`).
3. **Execution Gating Invariant Preserved**: Under no circumstances should TimesFM be connected to live order placement or slot reservation until empirical out-of-sample edge is demonstrated over multi-month walk-forward periods.
