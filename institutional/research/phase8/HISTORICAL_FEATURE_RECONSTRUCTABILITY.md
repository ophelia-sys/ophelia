# HISTORICAL FEATURE RECONSTRUCTABILITY MATRIX

This document explicitly defines which features from the live `InstitutionalMathEngine` can be reconstructed historically for ML training without train/serve mismatch.

## Group A: Price & Volatility
- **Reconstructability:** **FULL**
- **Features:** Realized Volatility, Parkinson, Garman-Klass, ATR, Efficiency Ratio, Directional Persistence, Robust Momentum, Momentum Acceleration, VWAP.
- **Requirements:** 1m OHLCV.
- **Train/Serve Mismatch Risk:** Low. Math is purely deterministic based on OHLCV arrays.
- **Status:** **APPROVED FOR MODEL 0 (BASELINE)**

## Group D: Derivatives
- **Reconstructability:** **PARTIAL**
- **Features:** Open Interest, $\Delta$OI, Funding Rate, Funding Z-Score.
- **Requirements:** Historical snapshots of OI and Funding.
- **Train/Serve Mismatch Risk:** Medium (Historical snapshot timestamps may not perfectly align with exact 1m candle closes).
- **Status:** **APPROVED FOR MODEL 1** (Only included if they prove incremental OOS value over Model 0).

## Group B: Order Flow
- **Reconstructability:** **HISTORICALLY_UNAVAILABLE**
- **Features:** CVD, TVI.
- **Reasoning:** Requires historical tick-level aggTrades with exact aggressor flags. Fabricating CVD from candle volume is strictly prohibited.
- **Status:** Must be collected via V4 Shadow telemetry for future research.

## Group E: Microstructure
- **Reconstructability:** **HISTORICALLY_UNAVAILABLE**
- **Features:** Spread, Queue Imbalance, Depth Imbalance, Microprice, Book Slope, Visible Impact, Canonical OFI.
- **Reasoning:** Requires deep, execution-venue-specific L2 snapshots. Substituting Binance L2 for BingX L2 is strictly prohibited.
- **Status:** Must be collected via V4 Shadow telemetry for future research.
