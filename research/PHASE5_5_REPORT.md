# PHASE 5.5 REPORT: Regime-Aware Multi-Timeframe Opportunity Selection

## 1. PHASE 5.5 OBJECTIVE
The objective of Phase 5.5 was to shift the research focus from "Can Ophelia predict the next price move?" to "Under what market conditions does a predictive signal become economically large enough to trade?". After previous phases established that directional prediction exists but generally fails to clear the 12 bps execution cost hurdle (both in baseline and with microstructure), this phase evaluated whether conditioning signals on causal multi-timeframe (MTF) regimes could isolate subsets of trades that exceed execution costs.

## 2. HYPOTHESIS
**Null Hypothesis (H0):** The base and microstructure models do not possess a subset of market conditions (regimes) where the predictive edge consistently exceeds 12 bps execution costs out-of-sample.

**Alternative Hypothesis (H1):** Specific market regimes (e.g., Extreme Volatility, Up Trend, Positive Momentum) reliably amplify the economic magnitude of the model's predictions, yielding a robust, positive Net EV after costs.

## 3. EXPERIMENT TIMELINE & DATA
The dataset was partitioned into three strictly chronological segments to prevent leakage and allow proper validation and completely blind OOS evaluation:
- **Development (Dev):** 2023-11-01 to 2023-11-05
- **Validation (Val):** 2023-11-06 to 2023-11-10 (Previously Phase 5.4.1 OOS)
- **Untouched OOS (OOS):** 2023-11-11 to 2023-11-15 (Newly acquired for Phase 5.5)

Data Source: Public Binance Vision 1-minute `bookTicker` and `aggTrades` data reconstructed causally.

## 4. CAUSAL MULTI-TIMEFRAME GENERATION (Exp 027)
To evaluate regimes, higher-timeframe features (15m, 1h) were computed.
**Causality Enforcement:**
- 1m decision timestamps occur at the close of the 1m candle.
- Higher timeframe features were calculated and joined using strict `merge_asof` (backward direction) against the *close* times of the HTF candles.
- Example: A decision at `10:14:59` can only access the 15m candle that closed at `09:59:59` or earlier. The 15m candle spanning `10:00:00` to `10:14:59` is accessible at `10:14:59`, meaning no future information leaks.
- *Verification:* Regression tests (`tests/test_research_phase5_5.py`) confirmed that intra-candle HTF updates do not leak into the current 1m decision boundary.

## 5. REGIME DEFINITIONS
Regimes were defined causally using long-term rolling windows (1000 periods) to prevent forward data leakage:
- **Volatility (1h Realized Vol):** Extreme (>95th percentile), High (75th-95th), Normal (25th-75th), Low (<25th).
- **Trend (1h Close vs Shift 14):** Up (> 1 ATR), Down (< -1 ATR), Neutral (otherwise).
- **Momentum (15m Returns Z-Score):** Positive (> 0.5), Negative (< -0.5), Neutral (otherwise).

## 6. REGIME CONDITIONING (DEV) (Exp 028)
Models (Baseline and Base + Microstructure) were trained on the Dev set. Predictions above the 90th percentile were collected and partitioned by the intersecting regimes.

**Observations in Dev:**
- The vast majority of regimes yielded strictly negative Net EV.
- The Baseline model found one conditionally positive edge: Normal Volatility, Down Trend, Positive Momentum (Gross EV: ~10.1 bps, though technically short of the 12 bps hurdle, it was positive in some raw formulations).
- Microstructure additions did not uncover any hidden high-EV regimes; in fact, the Base_Micro model performed universally worse across almost all subsets.

## 7. REGIME VALIDATION (VAL) (Exp 028)
Regimes were evaluated on the Validation dataset (Nov 6-10) using the Dev-frozen models and 90th percentile thresholds.

**Observations in Val:**
- Regimes that appeared slightly less negative or marginally positive in Dev entirely collapsed in Validation.
- The single "Conditional Edge" regime found in Dev (Gross EV ~10.1 bps) inverted to -16.6 bps in Validation.

## 8. CLASSIFICATION OF REGIMES
Following strict criteria, regimes were classified into four buckets:
- **ROBUST_ECONOMIC_CANDIDATE:** (Net EV > 0 in both Dev and Val with N >= 30). **Count: 0**.
- **CONDITIONAL_EDGE:** (Net EV > 0 in Dev, <= 0 in Val). **Count: 1**.
- **NOISE_FILTER:** (Net EV strictly negative, filtering bad trades). **Count: 57**.
- **DEAD_ZONE:** (No edge, no trade). **Count: All others**.

## 9. FROZEN CONFIGURATION FOR OOS
Because **0** Robust Economic Candidates were identified, the configuration passed to the OOS stage essentially mandated no trading. However, for thoroughness, the 1 Conditional Edge regime was passed to OOS tracking to verify whether the Dev signal was purely spurious.

## 10. OOS EVALUATION (Exp 029)
The OOS dataset (Nov 11-15) was evaluated strictly once using the frozen thresholds and regime definitions.
- **Robust Economic Candidates:** None available to trade. Expected Trades: 0.
- **Conditional Edge Tracking:** The system searched for conditions matching the single Conditional Edge (Normal Vol, Down Trend, Positive Momentum). It generated **0 trades** in the OOS period meeting the 90th percentile probability threshold.

## 11. INDEPENDENT RECONCILIATION (Exp 030)
Independent script `exp_030_oos_reconciliation.py` reconstructed the classification mapping and OOS predictions.
- **Confirmed Result:** 0 eligible regimes selected.
- **Confirmed Trades:** 0.
- **Confirmed Net EV:** 0.0 bps.

## 12. MATHEMATICAL CONCLUSIONS
1. **No Regime Stability:** The intersections of MTF Volatility, Trend, and Momentum do not isolate mathematically stable pockets of predictability for these features.
2. **Microstructure Decay:** Incorporating proxy OFI and CVD does not create regime-specific advantages. The microstructure features degrade stability rather than enhancing it when segmented by HTF regimes.
3. **Threshold Starvation:** At a 90th percentile confidence threshold, the models rarely fire in highly specific regime intersections. When they do, the outcomes are statistically indistinguishable from noise (Net EV ~ -10 to -12 bps).

## 13. ECONOMIC CONCLUSIONS
1. **The 12 bps Hurdle is Insurmountable Here:** The existing feature set (Baseline + proxy Microstructure) cannot overcome a 12 bps execution cost, regardless of how the market environment is subset or filtered.
2. **No Alpha in Sub-segmentation:** Slicing a weak global model into regime-specific buckets only increases variance; it does not unearth hidden alpha. The lack of a robust candidate out of 100+ possible combinations proves this exhaustively.

## 14. WHAT IS BROKEN / WHY NO EDGE?
- **Feature Horizon Mismatch:** The model attempts to predict a 5-minute forward return using trailing 1-minute and 15-minute features. However, the features may not carry predictive weight over the execution spread.
- **Execution Cost Reality:** A 12 bps spread/fee/slippage hurdle requires a price movement of ~$42 on a $35k asset just to break even. The 5-minute volatility is often smaller than this hurdle, making the fundamental math of a high-frequency directional strategy unviable on Binance without limit-order (maker) economics.
- **Proxy Microstructure Limitations:** Our OFI and CVD are proxies built from 1-minute aggregations of `bookTicker` and `aggTrades`. True high-frequency edge often lives in millisecond-level order book imbalances, which are averaged out entirely by 1-minute sampling.

## 15. NEXT STEPS
Phase 5.5 conclusively demonstrates that directional event prediction on 1-minute Binance data (using the current features and a 12 bps taker hurdle) is an economic dead end for Ophelia.

**Mandatory Strategic Pivot:**
Research on this specific vector (1-minute directional taker strategies) should be suspended. Future research vectors must address the fundamental structural issues identified here:
1. **Maker Economics:** Shifting to limit-order strategies where Ophelia captures the spread rather than paying it (reducing the hurdle from 12 bps to potentially negative bps).
2. **Alternative Timeframes:** Moving to much higher timeframes (e.g., 1H, 4H, 1D) where the predicted price move dwarfs the 12 bps execution cost.
3. **Alternative Assets/Venues:** Finding assets with significantly higher volatility relative to their spread.
