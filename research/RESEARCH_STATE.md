# OPHELIA — RESEARCH STATE
**Date:** 2026-08-12

## CHRONOLOGICAL RESEARCH HISTORY

### Phase 5.1: Baseline Directional Prediction
- **Dataset:** Binance BTCUSDT 1m (Jan 2023 - Oct 2023)
- **Target:** Forward 1m / 5m absolute return
- **Horizon:** 1m, 5m
- **Features:** Price momentum, volatility, RSI, MACD
- **Model:** LightGBM
- **Validation method:** Walk-forward expanding window
- **Cost assumption:** 12 bps taker round-trip
- **Result:** Weak directional signal, gross EV near 0. Net EV deeply negative.
- **Classification:** REJECTED
- **Reason:** Signal magnitude was too small to overcome 12 bps execution friction.

### Phase 5.2: Institutional Feature Expansion
- **Dataset:** Binance BTCUSDT 1m
- **Target:** Forward 5m return
- **Horizon:** 5m
- **Features:** Added Institutional Math (Kaufman, GK Vol, CVD, OI delta)
- **Model:** XGBoost
- **Validation method:** K-Fold Purged Cross-Validation
- **Cost assumption:** 12 bps taker round-trip
- **Result:** Marginal gross EV improvement (+0.2 bps) but still wildly unprofitable net (-11.8 bps).
- **Classification:** REJECTED
- **Reason:** Features had predictive power, but raw 5m return distribution lacks sufficient variance to clear costs.

### Phase 5.3: Triple-Barrier Event Prediction
- **Dataset:** Binance BTCUSDT 1m
- **Target:** Triple-barrier (Stop Loss, Take Profit, Time Timeout)
- **Horizon:** 60-minute maximum timeout
- **Features:** Full Institutional Math suite
- **Model:** Random Forest Classifier (Meta-labeling)
- **Validation method:** Chronological OOS split
- **Cost assumption:** 12 bps taker
- **Result:** Precision improved to 54%, but low trigger frequency and execution costs still resulted in long-term negative EV.
- **Classification:** REJECTED
- **Reason:** Meta-labeling filters out bad trades but does not magically increase the absolute size of the winning trades to clear friction.

### Phase 5.4: Historical Microstructure Baseline
- **Dataset:** Binance Vision BTCUSDT 1m + AggTrades
- **Target:** Forward 5m return
- **Horizon:** 5m
- **Features:** Added snapshot_ofi_proxy, end_spread, queue imbalance
- **Model:** LightGBM
- **Validation method:** Development vs Validation split
- **Cost assumption:** 12 bps taker
- **Result:** Gross EV improved from -0.35 bps to +0.46 bps (incremental +0.81 bps).
- **Classification:** PROVISIONAL
- **Reason:** Required locked OOS confirmation to verify if the edge was real or overfitted.

### Phase 5.4.1: Locked OOS Microstructure Confirmation
- **Dataset:** Binance Vision BTCUSDT 1m (Nov 6 - Nov 10, 2023)
- **Target:** Forward 5m return
- **Horizon:** 5m
- **Features:** Frozen Phase 5.4 Microstructure features
- **Model:** Frozen Phase 5.4 LightGBM
- **Validation method:** Locked, strictly chronological, untouched OOS
- **Cost assumption:** 12 bps taker
- **Result:** The +0.81 bps incremental improvement completely vanished. OOS Gross EV collapsed back below 0.
- **Classification:** REJECTED
- **Reason:** Microstructure edge on 1m bars decayed out-of-sample; it was an artifact of the validation set.

### Phase 5.5: Regime-Aware Multi-Timeframe Selection
- **Dataset:** Binance BTCUSDT 1m
- **Target:** Forward absolute move
- **Horizon:** 5m to 60m
- **Features:** Regime filters (Vol, Trend, Momentum)
- **Model:** Conditional logic filters
- **Validation method:** OOS filter evaluation
- **Cost assumption:** 12 bps taker
- **Result:** 0 market regimes provided a sufficient base rate of high-volatility moves to clear the 12 bps hurdle on a 1-minute execution cadence.
- **Classification:** REJECTED
- **Reason:** Market structure constraint; the opportunities literally do not exist frequently enough in 1m BTCUSDT data.

### Phase 5.6: Strategic Economic Feasibility Lab
- **Dataset:** Binance BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT (Nov 1 - Nov 15, 2023)
- **Target:** Branch A (Maker Economics), Branch B (HTF Economics), Branch C (Asset Efficiency)
- **Horizon:** 1m/5m (Maker), 15m/1h/4h (HTF)
- **Features:** NA (Feasibility modeling)
- **Model:** Statistical simulation
- **Validation method:** Analytical reconciliation
- **Cost assumption:** 12 bps taker, 2/0/-1.2 bps maker
- **Result:** Maker is unprofitable (-0.56 bps EV/fill). HTF (1h/4h) has sufficient variance (>12 bps). SOLUSDT has 10x volatility-to-cost ratio.
- **Classification:** ACCEPTED
- **Reason:** Identified the mathematically viable path forward: High-Timeframe (1h+) on High-Volatility Altcoins (SOLUSDT).

## KNOWN_BAD IDEAS
- **1-minute Taker Trading on BTCUSDT:** Execution friction (12 bps) mathematically dominates the average absolute move (8.7 bps). It is structurally unprofitable.
- **Pure Maker Trading on Binance:** Without toxic-flow filtering, resting bids are overwhelmingly run over by adverse selection (-0.56 bps loss per fill on average).
- **Aliasing 'Imbalance' to Canonical OFI:** BingX orderbook snapshots do not provide the exact event-by-event order additions/cancellations needed to calculate rigorous canonical OFI. Using snapshots as a proxy introduces severe noise.
- **Using '1T' pandas frequency string:** Deprecated. Use '1min'.
- **Ignoring Causal Alignment:** Using `merge` instead of `merge_asof(direction='backward')` leaks future data into higher-timeframe features.

## KNOWN_UNRESOLVED QUESTIONS
- **Actual BingX maker/taker fee assumptions:** The 12 bps taker cost is a conservative proxy. The actual production BingX fee schedule for the targeted VIP tier needs confirmation.
- **True canonical L2 OFI availability:** Can we acquire millisecond-level L2 delta feeds (not just 100ms snapshots) to calculate true canonical OFI?
- **Kronos incremental value:** The repository references Kronos for latency analysis, but its exact production integration is not fully modeled.
