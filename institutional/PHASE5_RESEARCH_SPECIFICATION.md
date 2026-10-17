# PHASE 5: QUANTITATIVE RESEARCH SPECIFICATION

This document outlines the strict quantitative research architecture for evaluating and selecting statistically validated features for Ophelia. The governing principle is: **Incremental Out-of-Sample Predictive Value After Realistic Costs.**

## 1-3. Feature Inventory & Lineage

The comprehensive feature inventory, classifying all metrics by historical reconstructibility vs live availability, has been extracted to:
- `PHASE5_FEATURE_AVAILABILITY_MATRIX.md`
- `PHASE5_DATA_REQUIREMENTS.md`

## 4. Candidate Feature Groups

The features will be evaluated sequentially in grouped modules to isolate incremental value:
1. **Price & Volatility**: OHLCV, Returns, Realized Vol, ATR, Parkinson.
2. **Trend & Momentum**: Kaufman ER, Log-return Momentum, ATR-scaled distance.
3. **Volume Profile**: Rolling VWAP, POC proximity.
4. **Order Flow**: 1m Aggressor CVD.
5. **Derivatives**: OI Change, Funding Z-score (requires new data).

## 5. Volume Profile Methodology

Tick-level profile is computationally unviable and historically unavailable. The mathematically defensible alternative is **1m-binned Volume-by-Price**. 
- **Method**: Distribute 1m volume equally across the 1m `Low` to `High` range. 
- **Metrics**: Rolling Session VWAP, Distance to POC (Point of Control), and Value Area High/Low limits. 
- **Approximation Label**: `1m_VP_APPROX`.

## 6. Order-Flow Historical Feasibility

Binance 1m data provides `taker_buy_volume`. 
- **Aggressor Buy Volume** = `taker_buy_volume`
- **Aggressor Sell Volume** = `volume - taker_buy_volume`
- **Historical CVD**: Feasible by cumulating `(Buy Vol - Sell Vol)` over rolling windows.
- **TVI / Absorption**: `LIVE-ONLY`. True micro-absorption requires tick sequence.

## 7. Derivatives Feasibility

- **Open Interest & Funding**: `HISTORICALLY RECONSTRUCTIBLE` via Binance Vision API datasets.
- **Action**: Deferred download. Will be acquired for specific BTC/ETH/SOL analysis, mapped precisely to 1m UTC timestamps.

## 8. GEX / COT Feasibility

- **GEX (Gamma Exposure)**: `REJECTED`. Fragmented crypto options data; minimal predictive power for 1m-1h horizons.
- **COT Reports**: `REJECTED`. Weekly frequency is incompatible with intraday modeling.

## 9. Label Design

Simple directional prediction (`P(price goes up)`) is naive. Ophelia targets will use **Cost-Adjusted Triple Barrier**:
- **Upper Barrier (Take Profit)**: Dynamic (e.g., 2 * ATR)
- **Lower Barrier (Stop Loss)**: Dynamic (e.g., 1 * ATR)
- **Time Horizon (Vertical Barrier)**: Fixed periods (e.g., 1h, 4h).
- **Target**: `P(Hits Upper Barrier First | Time < T and Return > Net Cost Hurdle)`.

## 10. Cost Model

A feature must overcome market friction to be viable.
**Net Return = Expected Gross Return - (Fees + Spread + Estimated Slippage/Impact)**
- **Baseline Hurdle**: 6 bps (0.06%) per round-trip for Tier 0 BingX takers. 
- Any feature providing <6 bps expected edge will be rejected regardless of raw statistical significance.

## 11. Validation Architecture

We will implement a strict **Combinatorial Purged Cross-Validation (CPCV)** or **Walk-Forward** framework:
- **Purge**: Remove training samples that overlap with validation outcomes.
- **Embargo**: Add a dead-zone post-validation to prevent serial correlation leakage.
- **Standardization**: All empirical CDFs and Z-scores must be fitted *only* on the rolling training window.

## 12. Baseline Model

The benchmark is a simple, cost-aware logic engine:
`BASE = OHLCV + Returns + ATR + Realized Volatility + Log-Return Momentum`

## 13. Candidate ML Models

1. **Regularized Logistic Regression (L1/L2)**: Fast, interpretable baseline.
2. **LightGBM / XGBoost**: Non-linear, handles missing features gracefully.
3. **Random Forest (ExtraTrees)**: High variance reduction benchmark.

## 14. Probability Calibration

Outputs must represent true empirical frequencies.
- **Metrics**: Brier Score, Expected Calibration Error (ECE).
- **Calibration Methods**: Isotonic Regression or Platt Scaling applied to validation folds.
- **Verification**: Ensure 70% confidence actually results in 70% barrier hit rates.

## 15. Feature Ablation Protocol

To prove **Incremental OOS Value**:
1. Train `BASE` model. Record LogLoss, Brier, Expected Net Return.
2. Train `BASE + FEATURE_X`. 
3. If `Δ Net Return` is ≤ 0, or `Δ Brier` shows no improvement: `REJECT FEATURE_X`.

## 16. Cross-Asset Validation

Features will be evaluated for generalization:
- Train BTC → Test BTC
- Train BTC → Test ETH / SOL
- If a feature is only significant on one asset, it will be flagged as an idiosyncratic regime parameter, not a generalized market invariant.

## 17. Binance -> BingX Transfer Validation

A mandatory gate before live deployment.
- Train Model on **Binance Historical**.
- Test Model on **BingX Paper-Live Data**.
- If performance degrades heavily, the feature suffers from exchange micro-structural divergence and must be rejected or retrained.

## 18. Live-Only Feature Strategy

Features like Spread, Microprice, Queue Imbalance, and OFI cannot be historically backtested. 
- They will act as **Live Execution Filters** (DecisionEngine), overriding the ML Setup Model if local liquidity conditions are hostile.

## 19. Exact Phase 5 Implementation Sequence

1. Define baseline dataset and Target Label (Triple Barrier).
2. Engineer `BASE` features (Volatility, Momentum).
3. Establish Purged Walk-Forward CV harness.
4. Benchmark `BASE` model metrics.
5. Engineer Volume Profile / CVD. Ablation test against `BASE`.
6. Download OI/Funding. Ablation test against `BASE+VOL`.
7. Calibrate probabilities.
8. Validate Cross-Asset.

---

## 20. CLASSIFICATION OF CANDIDATE FEATURES

| Feature | Classification | Justification |
|---------|----------------|---------------|
| **OHLCV / Returns** | `P0` | Core required data |
| **ATR / Realized Vol**| `P0` | Required for regime and barrier scaling |
| **Log-Return Mom.** | `P0` | Baseline directional momentum |
| **1m Aggressor CVD** | `P1` | Research candidate for flow dominance |
| **Volume Profile (1m)** | `P1` | Research candidate for mean-reversion |
| **Open Interest** | `P1` | Research candidate for crowding (needs data) |
| **Funding Rate** | `P1` | Research candidate for bias (needs data) |
| **TVI / True Flow** | `LIVE_ONLY` | Tick sequence historically unavailable |
| **Microprice/Spread** | `LIVE_ONLY` | Orderbook snapshots historically unavailable |
| **OFI (Order Flow)** | `UNAVAILABLE` | Strictly prohibited structurally |
| **GEX / COT Reports** | `REJECTED` | Mismatched horizon, poor crypto coverage |
