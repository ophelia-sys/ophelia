# OPHELIA AG HANDOFF

**Version:** 1.0  
**Timestamp:** 2026-08-14T13:00 UTC  
**Objective:** Authoritative project handoff for continuing the Ophelia repository. Do not restart or duplicate completed work.

---

## 1. CURRENT PROJECT STATUS

| Phase | Description | Status | Details |
|---|---|---|---|
| **Phase 4** | Institutional Data Layer | **COMPLETE** | Full BingX API data models & validation. |
| **Phase 4.1 - 4.4** | Mathematical Features | **COMPLETE** | `InstitutionalMathEngine` implemented with volatility, momentum, trend, liquidity, and volume profile logic. |
| **Phase 4.5** | Order Flow / OFI | **COMPLETE** | CVD and TVI implemented. Canonical OFI determined UNAVAILABLE due to API structure. |
| **Phase 4.5.1** | Repository Lineage Audit | **COMPLETE** | Enforced that approximate metrics are never mapped to Canonical OFI. |
| **Phase 8.3** | Live Shadow Validation | **COMPLETE** | `s3_shadow_engine.py` and `s3_outcome_tracker.py` running and logging states to SQLite. |
| **Phase 8.4** | Probability Engine Architecture | **COMPLETE** | V4 Pipeline Architecture established. Model is completely untrained. |
| **Phase 8.5** | Historical Research Dataset | **COMPLETE** | Infrastructure built for triple-barrier and feature calculation (`process_pipeline.py`). Reconstructability audit finished. |
| **Phase 8.6** | Empirical Dataset Gen. | **IN PROGRESS** | 7-day small sample downloaded for BTC, ETH, SOL, XRP, BNB. 22-point audit generated. **STOPPED pending user approval.** |

---

## 2. CURRENT ARCHITECTURE

```text
BingX Data [LIVE]
    ↓
Institutional Data Layer [LIVE]
    ↓
MarketDataSnapshot [LIVE]
    ↓
Institutional Math Engine [LIVE]
    ↓
MarketState [LIVE]
    ↓
=====================================================
Legacy DecisionEngine [LIVE]  AND   V4 Shadow Pipeline [SHADOW]
=====================================================
                                    ↓
                                Trade Geometry [SHADOW]
                                    ↓
                                Probability Engine [UNAVAILABLE / UNTRAINED]
                                    ↓
                                Opportunity Gate [SHADOW]
                                    ↓
                                Telemetry / Outcome Tracking [SHADOW]
                                    ↓
                                Future calibrated trading decision [RESEARCH]
                                    ↓
Execution [DISABLED GLOBALLY]
```

---

## 3. DATA PROVENANCE

**BingX (Live Trading / Shadow)**
- **OHLCV, Trades:** Live REST / WebSocket.
- **Microstructure (Spread, Microprice, Imbalances, Slope, Concentration, Impact):** Calculated from live L2 Orderbook snapshots. Subject to snapshot pacing (no tick-by-tick delta).
- **CVD / TVI:** Approximate calculations from trade streams.
- **Open Interest / Funding:** Live REST polling, archived locally into `bingx_oi.sqlite`.

**Binance USD-M Futures (Historical Research Phase 8.6+)**
- **Historical 1m OHLCV, Open Interest, Funding Rate:** Sourced from Binance via `ingest_small_sample.py`.

> [!WARNING]
> Binance data is classified strictly as **EXCHANGE-SPECIFIC RESEARCH SOURCE**.
> Its transferability to BingX is a HYPOTHESIS that must be validated in Phase 8.7. Do NOT assume it is "cross-exchange transferable".

---

## 4. CRITICAL OFI INVARIANT

Canonical Cont-Kukanov-Stoikov Order Flow Imbalance (OFI) requires sequential, tick-by-tick L2 orderbook updates. 
BingX provides **gapped snapshots**, meaning exact state transitions cannot be guaranteed.

Therefore, **Canonical OFI is UNAVAILABLE.**
The Phase 4.5.1 audit strictly forbids mapping any of the following to OFI:
- `depth_imbalance` $\rightarrow$ `OFI` (FORBIDDEN)
- `queue_imbalance` $\rightarrow$ `OFI` (FORBIDDEN)
- `CVD` $\rightarrow$ `OFI` (FORBIDDEN)
- `TVI` $\rightarrow$ `OFI` (FORBIDDEN)
- `microprice` $\rightarrow$ `OFI` (FORBIDDEN)

---

## 5. MICROSTRUCTURE METRICS IMPLEMENTED

- **Mid Price**: `(Best Bid + Best Ask) / 2`
- **Absolute Spread**: `Best Ask - Best Bid`
- **Relative Spread**: `Absolute Spread / Mid Price`
- **Queue Imbalance**: `(Bid Size - Ask Size) / (Bid Size + Ask Size)` at BBO.
- **Depth Imbalance**: `(Total Bid Depth - Total Ask Depth) / (Total Bid Depth + Total Ask Depth)` over full visible book.
- **Microprice**: Volume-weighted mid price: `(Best Bid * Ask Size + Best Ask * Bid Size) / (Bid Size + Ask Size)`.
- **Book Slope**: Corrected formulation implemented. 
  - `X` = price distance from mid in BPS.
  - `Y` = cumulative quote notional in USDT.
  - Output = `USDT / BPS`. (Calculated separately for Bid Slope and Ask Slope).
- **Book Concentration**: Ratio of BBO size to total visible depth.
- **Visible Book Impact**: Simulated price impact (in BPS) for a standardized order size (e.g., $10k, $50k) walking the book.

---

## 6. INSTITUTIONAL MATH INVENTORY (`institutional_math.py`)

A. **Volatility**: 
   - `calculate_realized_volatility`, `calculate_parkinson_volatility`, `calculate_garman_klass_volatility`, `calculate_atr`. 
   - Reaches MarketState. Historically Reconstructable.
B. **Trend**: 
   - `calculate_efficiency_ratio`, `calculate_directional_persistence`, `calculate_atr_scaled_trend`. 
   - Reaches MarketState. Historically Reconstructable.
C. **Momentum**: 
   - `calculate_standardized_momentum`, `calculate_momentum_acceleration`. 
   - Reaches MarketState. Historically Reconstructable.
D. **Normalization**: 
   - `calculate_rolling_percentile`, `calculate_robust_z_score`.
E. **Order Flow**: 
   - `calculate_cvd`, `calculate_taker_volume_imbalance`. 
   - Reaches MarketState. Not reconstructable historically without tick data. Canonical OFI is UNAVAILABLE.
F. **Volume Profile / Liquidity**: 
   - `calculate_vwap`, `calculate_amihud_illiquidity`. 
   - Reaches MarketState. Historically Reconstructable.
G. **Derivatives**: 
   - `analyze_open_interest_state`, `analyze_funding_state`. 
   - Reaches MarketState. Historically available via Binance.
H. **Microstructure**: 
   - Spread, Queue Imbalance, Slope. 
   - Reaches MarketState. Not reconstructable historically.
I. **Regime / Statistical**: 
   - `classify_regime_hmm`, `detect_structural_break`. 
   - Currently stubbed/unavailable.
J. **Unavailable**: 
   - Proper tick-level OFI, Orderbook flow toxicity.

> [!IMPORTANT]
> Mathematical implementation $\neq$ empirical validation. Many features exist but lack proven predictive evidence.

---

## 7. V4 PROBABILITY ENGINE STATUS

Current architecture flow:
`MarketState` $\rightarrow$ `TradeGeometry` $\rightarrow$ `Probability Engine` $\rightarrow$ `Opportunity Gate`

**Status:** **UNTRAINED / MODEL_UNAVAILABLE**
The engine currently fabricates NO probabilities. It outputs `UNAVAILABLE` or stubbed values. Do not plug in LLM reasoning as the runtime engine; the engine must remain deterministic math/ML models running locally.

---

## 8. PHASE 8.5 HISTORICAL RESEARCH

Historically Reconstructable from 1m OHLCV (Binance):
- ATR, Realized Volatility, Parkinson, Garman-Klass, Trend, Momentum, Efficiency, VWAP.

Potentially Available from Binance:
- Open Interest, Funding Rate.

Historically UNAVAILABLE (Do not fabricate):
- BingX L2 Microstructure, historical Spread, true historical CVD/TVI, Canonical OFI.

---

## 9. PHASE 8.6 CURRENT PLAN

Phase 8.6 is currently **STOPPED**.
- A 7-day representative sample (BTC, ETH, SOL, XRP, BNB) was downloaded from Binance USD-M Futures.
- The pipeline (`RAW` $\rightarrow$ `NORMALIZED` $\rightarrow$ `FEATURES` $\rightarrow$ `LABELS`) was run successfully.
- The 22-point data integrity audit was completed (Zero missing intervals, natural class balance preserved, triple-barrier logic verified).
- **DO NOT download the multi-year dataset until the user explicitly approves the 7-day audit.**

---

## 10. PHASE 8.6 CORRECTIONS TO ENFORCE

1. **Natural class distribution must remain untouched.** No artificial balancing/oversampling.
2. No global oversampling or undersampling.
3. Binance $\rightarrow$ BingX mismatch is NOT considered eliminated.
4. Binance OI/Funding transferability is NOT assumed.
5. 2–3 years and 2,400 events are planning estimates, NOT hard targets.
6. Raw data must remain immutable.
7. No model training during Phase 8.6.
8. No predictive claims from the 7-day sample.
9. Triple-barrier intrabar ambiguity must **never be guessed**.
10. All features must obey causal timestamp availability.
11. Dataset/version metadata must be preserved.
12. **ESS Terminology Clarification**: The current value represents the aggregate count of non-overlapping labeled events across the five symbols. It is NOT a statistical Effective Sample Size. A true ESS will be determined later using an appropriate dependence/autocorrelation methodology.

---

## 11. TRIPLE-BARRIER LABELING METHODOLOGY

- **Horizons**: 15m, 30m, 1h, 4h.
- **Upper Barrier**: Dynamic Take Profit based on ATR.
- **Lower Barrier**: Dynamic Stop Loss based on ATR.
- **Vertical Barrier**: Timeout.
- **Tie/Ambiguity Handling**: If both barriers are touched inside the *same 1m candle*, the ordering is mathematically unknowable. The label is marked as `AMBIGUOUS` (`np.nan`) and excluded from training. **Never guess.**

---

## 12. LIVE SHADOW STATE

Live telemetry daemons are currently running:
- `institutional/data/archive/oi_poller.py`
- `institutional/data/s3_shadow_engine.py`
- `institutional/data/s3_outcome_tracker.py`

**Database Status (`s3_shadow_log.sqlite`):**
- Logged **1045** `UNAVAILABLE` decision rows.
- No real signals fired (expected, as model is untrained).

**Database Status (`bingx_oi.sqlite`):**
- Contains **265** OI observation rows.

Execution remains globally **DISABLED**.

---

## 13. TEST INVENTORY

> [!WARNING]
> Local pytest execution currently FAILS due to a corrupted/incomplete virtual environment.
> Errors: `ModuleNotFoundError: No module named 'numba'` and `No module named 'sklearn'`.

Tests that theoretically pass (when environment is configured):
- `test_market_state.py`
- `test_institutional_math.py`

Test completion status is unverifiable right now until `pip install numba scikit-learn` is executed. Do not assume any test passes unless verified.

---

## 14. IMPORTANT DESIGN PHILOSOPHY

**Ophelia does NOT keep a feature because it sounds sophisticated.**

Every feature must eventually prove:
1. Incremental predictive value
2. Out-of-sample robustness
3. Calibration quality
4. Economic value after realistic costs

If a feature fails those tests, **REMOVE IT**. No feature (e.g. CVD, TVI, OI, Funding, Microprice, GEX) receives privileged status merely because it is labeled "institutional."

---

## 15. PRODUCTION STATUS

- **ARCHITECTURAL COMPLETION:** ~80%. The pipeline (from data ingestion to mathematical computation to decision staging) is structurally built.
- **RESEARCH COMPLETION:** ~5%. The probability engine is entirely untrained. Predictive models, feature calibration, and triple-barrier baselines have not been constructed.
- **PRODUCTION READINESS:** 0%. Live execution is strictly disabled. No funds are at risk.

---

## 16. IMMEDIATE NEXT ACTION FOR NEW AGENT

1. Read `OPHELIA_AG_HANDOFF.md`.
2. Verify repository state.
3. Review Phase 8.6 status.
4. Verify Binance USD-M endpoints functionality.
5. Review the generated 22-point audit for the 7-day sample.
6. **STOP.** Do not download the multi-year historical dataset. Present the audit results to the user and wait for explicit approval to continue.
