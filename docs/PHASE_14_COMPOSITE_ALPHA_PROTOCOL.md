# PHASE 14 PRE-REGISTERED RESEARCH PROTOCOL: CONTROLLED MULTI-FACTOR ALPHA DISCOVERY

**Document Status**: LOCKED & FROZEN PRE-EXPERIMENT  
**Date**: 2026-10-19  
**Repository**: `ophelia-sys/ophelia`  
**Execution Authority**: SHADOW ONLY (`TRADING_AUTHORITY=False`, `EXECUTION_MODE=SHADOW`, `LIVE_ORDERS_FORBIDDEN=True`)  

---

## 1. Research Question & Objective

Phase 13 demonstrated that across 170,450 candidate events in 2023, standalone microstructure signals fail to clear crypto perpetual transaction friction:
- Standalone `HTF_ALIGNED_DISPLACEMENT` produced +5.83 bps gross mean 60m return ($p = 0.189$), becoming -3.27 bps net after 9.1 bps friction.
- Standalone `LIQUIDITY_SWEEP_SFP` produced +5.08 bps gross mean 60m return ($p = 0.118$), becoming -4.02 bps net after 9.1 bps friction.
- All other 8 standalone signal families produced zero or negative gross returns.

**Phase 14 Core Question**:  
Does conditioning these two nominally positive signals on contextual market regime filters (higher-timeframe trend alignment, volume expansion, volatility regime, order-flow absorption, or mutual confluence) produce measurable incremental gross edge exceeding the exchange friction threshold (9.1 bps round-trip), or does added complexity merely diminish sample size without improving out-of-sample expectancy?

---

## 2. Data Sources & Provenance Boundary

1. **Development & Validation Universe (2023 Full Year)**:
   - File: `data/processed/binance_um_universe_1m_v2.parquet`
   - Checksum (SHA-256): `d2e839edecfae88b798993cff9545fa626071efcb722f266fbe15e0bea3e20b5`
   - Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (Binance USDT-M Futures)
   - Features: Complete OHLCV, `quote_volume`, `delta_v`, `taker_buy_volume`, aggressive buy/sell volumes.
   - Chronological Splits (Preserving 24-hour purge embargos):
     - `TRAIN`: 2023-01-01 00:00:00 to 2023-07-31 23:59:00 UTC (7 months)
     - `EMBARGO_1`: 2023-08-01 00:00:00 to 2023-08-01 23:59:00 UTC (Purge)
     - `VALIDATION`: 2023-08-02 00:00:00 to 2023-10-14 23:59:00 UTC (2.5 months)
     - `EMBARGO_2`: 2023-10-15 00:00:00 to 2023-10-15 23:59:00 UTC (Purge)
     - `TEST`: 2023-10-16 00:00:00 to 2023-12-31 23:59:00 UTC (2.5 months)

2. **Out-of-Time Confirmation Universe (Q1 2024)**:
   - File: `data/processed/phase12_fresh_universe_1m.parquet`
   - Checksum (SHA-256): `91de7196ace28474ef5fbeaa3c004e2df38b4c3658e451bd0d575b5e12060409`
   - Period: 2024-01-01 00:00:00 UTC to 2024-03-31 23:59:00 UTC (91 days, 131,040 1m bars/symbol).
   - Features: OHLCV (order-flow delta not present; order-flow hypotheses evaluated strictly on 2023).
   - Provenance Integrity: While Phase 12 evaluated TimesFM on this file, this period has **never** been evaluated for Phase 13 or Phase 14 composite microstructure rules.

---

## 3. Pre-Registered Hypothesis Family ($m = 10$)

To prevent combinatorial data-snooping, the candidate family is frozen strictly to 10 hypotheses (2 standalone benchmarks + 8 contextual composites).

### Standalone Benchmarks
1. `BENCH_HTF_ALIGNED_DISPLACEMENT`:
   - 5m candle $|body| \ge 1.5 \times ATR_{14}$ aligned with 4H EMA20/50 trend (`BULL` for LONG, `BEAR` for SHORT).
2. `BENCH_LIQUIDITY_SWEEP_SFP`:
   - 5m candle sweeps 15m swing low by >0.1% and closes back above (LONG), or sweeps 15m swing high by >0.1% and closes back below (SHORT).

### Contextual Composites
3. `COMP_SFP_HTF_TREND`:
   - `LIQUIDITY_SWEEP_SFP` filtered by 4H trend: LONG only when 4H trend is `BULL`; SHORT only when 4H trend is `BEAR`.
   - *Thesis*: SFP in the direction of HTF trend buys pullbacks in an ongoing expansion, avoiding low-probability counter-trend reversals.
4. `COMP_SFP_RVOL_CONFIRM`:
   - `LIQUIDITY_SWEEP_SFP` with 5m relative volume $RVOL \ge 1.5$.
   - *Thesis*: Volume expansion confirms aggressive absorption by institutional limit orders at the sweep level.
5. `COMP_SFP_VOL_EXPANSION`:
   - `LIQUIDITY_SWEEP_SFP` in non-compressed volatility regime: $ATR_{14} / ATR_{50} \ge 0.75$.
   - *Thesis*: Eliminates low-volatility chop where post-reversal excursions cannot overcome the 9.1 bps friction hurdle.
6. `COMP_DISPLACEMENT_RVOL`:
   - `HTF_ALIGNED_DISPLACEMENT` with $RVOL \ge 2.0$.
   - *Thesis*: Ultra-high relative volume confirms strong conviction behind the trend impulse.
7. `COMP_DISPLACEMENT_VOL_EXPANSION`:
   - `HTF_ALIGNED_DISPLACEMENT` in expanded volatility regime: $ATR_{14} / ATR_{50} \ge 1.25$.
   - *Thesis*: Momentum displacement exiting a compression regime creates sustained expansion.
8. `COMP_SFP_CVD_ABSORPTION`:
   - `LIQUIDITY_SWEEP_SFP` with opposing CVD delta: LONG with $CVD_z \le -1.0$; SHORT with $CVD_z \ge 1.0$ (gated on `AVAILABLE` CVD status).
   - *Thesis*: Net aggressive market orders fail to drive price further, verifying absorption by passive liquidity.
9. `COMP_DUAL_CONFLUENCE`:
   - Simultaneous occurrence of `LIQUIDITY_SWEEP_SFP` and `HTF_ALIGNED_DISPLACEMENT` on the same 5m bar in the same direction.
   - *Thesis*: Highest-conviction signal combining structural reclaim with trend momentum.
10. `COMP_HTF_1H_SWING_SFP`:
    - Liquidity sweep and reclaim of the 1-Hour swing level (instead of 15m).
    - *Thesis*: Higher-timeframe swing points provide wider subsequent mean-reversion horizons.

---

## 4. Execution Horizon & Friction Model

- **Primary Horizon**: 60-Minute Forward Directional Return ($R_{60m}$).
- **Secondary Horizons**: 15m, 30m, 120m, plus first-passage Stop Room (5m swing, 15m swing, 1h swing, ATR envelope).
- **Friction Models**:
  - `FEE_ONLY` (5.0 bps): 2.5 bps entry + 2.5 bps exit (proxy for passive maker / VIP fee tiers).
  - `BASELINE_TAKER` (9.1 bps): 4.0 bps entry fee + 4.0 bps exit fee + 1.1 bps adverse slippage.
  - `CONSERVATIVE_SLIP` (15.0 bps): 4.0 bps entry fee + 4.0 bps exit fee + 7.0 bps slippage (volatile market condition).
- **Execution Timing**:
  - Signal evaluates causally at the close of 5m decision bar $i$ (`decision_ts_ms = timestamp + 300,000`).
  - Forward trajectory evaluates from minute $i+1$ onward (zero lookahead).

---

## 5. Dependence-Aware Statistical Inference

1. **Synchronized Time-Block Bootstrap**:
   - Resampling unit is real chronological time across all 3 symbols simultaneously.
   - Primary block duration: **6 Hours**.
   - Sensitivity evaluation: **2 Hours** and **24 Hours**.
   - Number of resamples: $B = 1,000$.
2. **Confirmatory Eligibility Criteria (TEST & Q1 2024)**:
   - Minimum sample size: $N \ge 30$.
   - Minimum active time clusters: $B_{\text{active}} \ge 10$.
   - Hypotheses with $N < 30$ or $B_{\text{active}} < 10$ are classified as `INCONCLUSIVE`.
3. **Multiplicity Control**:
   - Benjamini–Hochberg False Discovery Rate (FDR) applied across the 10 pre-registered hypotheses at nominal level $q = 0.05$.

---

## 6. Pre-Declared Decision Criteria

Each candidate hypothesis will receive exactly one conclusion:
- **`NO EDGE FOUND`**:
  - Net expectancy after 9.1 bps friction $\le 0.0$ OR FDR $q \ge 0.05$.
- **`EXPLORATORY CANDIDATE — NOT CONFIRMED`**:
  - Net expectancy $> 0$ on TRAIN/VALIDATION, but fails confirmatory TEST or out-of-time confirmation.
- **`STATISTICALLY SUPPORTED CANDIDATE UNDER MODELED COSTS`**:
  - Net expectancy $> 0$ at 9.1 bps on confirmatory TEST, raw $p < 0.05$, FDR $q < 0.05$, robust across 2h/6h/24h blocks, and confirmed with positive net expectancy on Q1 2024 out-of-time data.
- **`INCONCLUSIVE`**:
  - Fails sample size ($N < 30$) or cluster count ($B_{\text{active}} < 10$) on the confirmatory split.
