# OPHELIA RESEARCH MASTER STATE

| PHASE | FAMILY | HYPOTHESIS | DATA | MODEL | TARGET | RESULT | DECISION | CONFIDENCE | ARTIFACTS | NEXT ACTION |
|-------|--------|------------|------|-------|--------|--------|----------|------------|-----------|-------------|
| 5.1 | BASE | Core ML framework capability | OHLCV 5m | LightGBM | target_60_up_10 | Marginal | FROZEN | HIGH | Baseline Reports | Frozen as BASE |
| 5.3 | CVD | Cumulative Volume Delta predicts flow | aggTrades | LightGBM | target_60_up_10 | Strong Predictive | FROZEN | HIGH | CVD Results | Frozen as core benchmark |
| 6.1-B | FFD | Fractional Differencing retains memory | OHLCV | LightGBM | target_60_up_10 | Weak | REJECTED | HIGH | Stage B Results | Removed |
| 6.1-C | Kalman | Kalman filters extract true state | OHLCV | LightGBM | target_60_up_10 | Highly Correlated, Weak | REJECTED | HIGH | Stage C Results | Removed |
| 6.1-D | HMM | HMM identifies volatility regimes | OHLCV | LightGBM | target_60_up_10 | Lookahead risk | REJECTED | HIGH | Stage D Results | Removed |
| 6.1-D | EWMA | EWMA/GARCH Volatility | OHLCV | LightGBM | target_60_up_10 | No improvement | REJECTED | HIGH | Stage D Results | Removed |
| 6.2 | P1 | Open Interest Positioning | BingX OI | LightGBM | target_60_up_10 | Data gaps | REJECTED | HIGH | P1 Orthogonality | Removed |
| 6.2 | P2 | Liquidation Data | Binance Liq | N/A | target_60_up_10 | Skipped | SKIPPED | N/A | N/A | Skipped |
| 6.2 | P3 | Spot vs Perp Divergence | Binance Spot/Perp | LightGBM | target_60_up_10 | No correlation | REJECTED | HIGH | P3 Results | Removed |
| 6.3 | P4 | Large-Trade Microstructure | aggTrades | LightGBM | target_60_up_10 | Failed 2024 OOS | REJECTED | HIGH | P4 Results | Removed |
| 6.3 | P5 | Cross-Asset Correlation | Multi-Coin | LightGBM | target_60_up_10 | Inconsistent | REJECTED | HIGH | P5 Results | Removed |
| 6.4 | P6 | Funding Rates | Funding Data | LightGBM | target_60_up_10 | Structurally orthogonal | REJECTED | HIGH | P6 Results | Removed |
| 6.4 | VWAP | VWAP/Supertrend standalone | OHLCV | N/A | N/A | Weak | REJECTED | HIGH | VWAP test | Removed |
| 6.4 | P7 | Volume Acceptance Proxy | OHLCV | LightGBM | target_60_up_10 | Failed 2024 OOS | REJECTED | HIGH | P7 Audit | Removed |
