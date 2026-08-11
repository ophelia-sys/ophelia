# OPHELIA — INSTITUTIONAL FEATURE REGISTRY
**Last Updated:** 2026-08-11
**Purpose:** A durable registry of all institutional features and mathematical models available to Ophelia. Use this document as the source of truth for feature availability, current implementation status, and data lineage requirements.

## 1. Volatility Family
| Feature | Implementation | Description | Data Provenance | Status |
|---------|----------------|-------------|-----------------|--------|
| **Log Returns** | `institutional.volatility.calculate_log_returns` | Simple 1-period logarithmic return. | OHLCV | VALIDATED |
| **Realized Volatility (RV)** | `institutional.volatility.calculate_realized_volatility` | $\sqrt{\sum (r_t^2)}$. Native timeframe volatility, no arbitrary annualization. | OHLCV | VALIDATED |
| **Parkinson Volatility** | `institutional.volatility.calculate_parkinson_volatility` | Estimator based on High/Low prices. Less sensitive to opening gaps. | OHLCV | VALIDATED |
| **Garman-Klass Volatility** | `institutional.volatility.calculate_garman_klass_volatility` | Includes OHLC. More efficient than Parkinson, assumes continuous trading. | OHLCV | VALIDATED |
| **Average True Range (ATR)** | `institutional.volatility.calculate_atr` | Standard TR rolling mean. | OHLCV | VALIDATED |

## 2. Trend & Regime Family
| Feature | Implementation | Description | Data Provenance | Status |
|---------|----------------|-------------|-----------------|--------|
| **Kaufman Efficiency Ratio (KER)**| `institutional.trend.calculate_efficiency_ratio` | Direction / Volatility over $N$ periods. Range: 0 to 1. | OHLCV | VALIDATED |
| **Directional Persistence** | `institutional.trend.calculate_directional_persistence` | Ratio of positive returns to total returns in window. | OHLCV | VALIDATED |
| **ATR Scaled Trend** | `institutional.trend.calculate_atr_scaled_trend` | $(Close - SMA) / ATR$. Normalizes trend strength against volatility. | OHLCV | VALIDATED |
| **EMA Structure** | `institutional.trend.get_ema_structure` | Descriptive alignment state of fast, slow, and baseline EMAs. | OHLCV | VALIDATED |
| **HMM Regime** | `institutional.regime.classify_regime_hmm` | 3-state HMM on standardized returns & RV. | OHLCV | **STUBBED / SLOW PATH** |
| **Structural Break (PELT)** | `institutional.structural_break.detect_structural_break` | Change point detection for variance/regime shifts. | OHLCV | **STUBBED / SLOW PATH** |

## 3. Momentum Family
| Feature | Implementation | Description | Data Provenance | Status |
|---------|----------------|-------------|-----------------|--------|
| **Robust Momentum Z-Score** | `institutional.momentum.calculate_standardized_momentum` | Returns robustly normalized using rolling median and Median Absolute Deviation (MAD). | OHLCV | VALIDATED |
| **Momentum Acceleration** | `institutional.momentum.calculate_momentum_acceleration` | Rate of Change (ROC) of standardized momentum. | OHLCV | VALIDATED |
| **Volume Imbalance** | `institutional.momentum.calculate_volume_imbalance` | Ratio of up-volume to down-volume based on return direction. Proxy only (not OFI). | OHLCV | VALIDATED |

## 4. Liquidity & Microstructure Family
| Feature | Implementation | Description | Data Provenance | Status |
|---------|----------------|-------------|-----------------|--------|
| **Mid Price** | `institutional.liquidity.calculate_mid_price` | $(BestBid + BestAsk)/2$. | L1 Book (Top) | VALIDATED |
| **Relative Spread** | `institutional.liquidity.calculate_relative_spread` | $(BestAsk - BestBid) / MidPrice$. | L1 Book (Top) | VALIDATED |
| **Queue Imbalance** | `institutional.liquidity.calculate_queue_imbalance` | $(BidQty1 - AskQty1) / (BidQty1 + AskQty1)$. | L1 Book (Top) | VALIDATED |
| **Depth Imbalance** | `institutional.liquidity.calculate_depth_imbalance` | Volume imbalance up to Top-K levels. | L2 Book | VALIDATED |
| **Microprice** | `institutional.liquidity.calculate_microprice` | Volume-weighted mid price at top of book. | L1 Book (Top) | VALIDATED |
| **Book Concentration** | `institutional.liquidity.calculate_book_concentration` | HHI of order book levels to measure liquidity dispersion. | L2 Book | VALIDATED |
| **Book Slope** | `institutional.liquidity.calculate_order_book_slope` | Regression of cumulative quote notional vs. price distance (BPS). | L2 Book | VALIDATED |
| **Visible Impact** | `institutional.liquidity.calculate_visible_impact_bps` | Expected slippage (in BPS) for a simulated order sweeping the book. | L2 Book | VALIDATED |
| **Amihud Illiquidity** | `institutional.liquidity.calculate_amihud_illiquidity` | Absolute Return / Dollar Volume. | OHLCV | VALIDATED |
| **Kyle Lambda** | `institutional.liquidity.estimate_kyle_lambda` | Regression of price change on order flow. | Trades | **STUBBED** |

## 5. Order Flow & Advanced Data Family
| Feature | Implementation | Description | Data Provenance | Status |
|---------|----------------|-------------|-----------------|--------|
| **Cumulative Volume Delta (CVD)** | `institutional.order_flow.calculate_cvd` | Cumulation of aggressor-side volumes. | Aggressor Trades | VALIDATED |
| **Taker Volume Imbalance (TVI)** | `institutional.order_flow.calculate_taker_volume_imbalance` | Ratio of Taker Buy vs Taker Sell volume. | Aggressor Trades | VALIDATED |
| **Order Flow Imbalance (OFI)** | `institutional.order_flow.calculate_ofi` | True order flow imbalance based on non-gapped L1 updates. | Continuous L1 Updates | **UNAVAILABLE** (BingX constraint) |
| **Open Interest (OI)** | `institutional.open_interest.analyze_open_interest_state` | Open Interest hypothesis mapping (Initiation/Covering). | OI Feed | VALIDATED |
| **Funding** | `institutional.funding.analyze_funding_state` | Robust rolling Z-score of funding rate. | Funding Feed | VALIDATED |
| **Liquidations** | `institutional.liquidation.analyze_liquidation_state` | Liquidation imbalance. | Liquidation Feed | **UNAVAILABLE** (API absent) |
