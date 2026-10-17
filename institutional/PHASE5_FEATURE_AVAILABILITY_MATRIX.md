# PHASE 5: FEATURE AVAILABILITY MATRIX

This matrix enforces the strict separation between Historical Research and Live Production capabilities to prevent dataset hallucination and look-ahead bias.

| FEATURE CATEGORY | FEATURE NAME | SOURCE | HISTORICAL/LIVE LINEAGE |
|------------------|--------------|--------|-------------------------|
| **PRICE / TREND** | OHLCV | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Kaufman Efficiency Ratio | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | ATR-Scaled Trend Distance | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Log-Return Momentum | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Fair Value Gaps (FVG) | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| **VOLATILITY** | Realized Volatility | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Parkinson Volatility | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Garman-Klass Volatility | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | ATR (Average True Range) | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| **VOLUME / PROFILE**| Volume (Total) | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Session VWAP | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Rolling VWAP | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Point of Control (POC) | Klines/Ticks | 3. APPROXIMATELY RECONSTRUCTIBLE (1m binning limit) |
| | Value Area High/Low | Klines/Ticks | 3. APPROXIMATELY RECONSTRUCTIBLE (1m binning limit) |
| | Amihud Illiquidity | Klines | 1. HISTORICALLY RECONSTRUCTIBLE |
| **ORDER FLOW** | Aggressor Volume | Trades | 3. APPROXIMATELY RECONSTRUCTIBLE (via 1m taker_buy_volume) |
| | CVD (Cumulative Vol Delta) | Trades | 3. APPROXIMATELY RECONSTRUCTIBLE (1m bin resolution) |
| | TVI (Tick Volume Indicator) | Trades | 2. LIVE ONLY (Requires tick-level trade sequence) |
| | Flow-Price Divergence | Trades/Klines | 3. APPROXIMATELY RECONSTRUCTIBLE |
| **MICROSTRUCTURE**| Spread / Relative Spread | Orderbook (L2) | 2. LIVE ONLY |
| | Queue Imbalance | Orderbook (L2) | 2. LIVE ONLY |
| | Depth Imbalance | Orderbook (L2) | 2. LIVE ONLY |
| | Microprice | Orderbook (L2) | 2. LIVE ONLY |
| | Book Concentration / Slope | Orderbook (L2) | 2. LIVE ONLY |
| | Visible-Book Impact | Orderbook (L2) | 2. LIVE ONLY |
| | Order Flow Imbalance (OFI) | Orderbook (L2) | 4. UNAVAILABLE (Canonical rule) |
| **DERIVATIVES** | Open Interest (OI) | API / Dumps | 1. HISTORICALLY RECONSTRUCTIBLE (Needs download) |
| | Funding Rate | API / Dumps | 1. HISTORICALLY RECONSTRUCTIBLE (Needs download) |
| | OI Change / Z-Score | API / Dumps | 1. HISTORICALLY RECONSTRUCTIBLE (Needs download) |
| | Funding Z-Score | API / Dumps | 1. HISTORICALLY RECONSTRUCTIBLE (Needs download) |
| **NORMALIZATION** | Robust MAD Z-Score | Math | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Empirical CDF / Rank | Math | 1. HISTORICALLY RECONSTRUCTIBLE |
| | Evidence Entropy | Math | 1. HISTORICALLY RECONSTRUCTIBLE |
| **MACRO / OPTIONS**| GEX / Gamma Walls | Options Data | 4. UNAVAILABLE (Intraday irrelevance/cost) |
| | CFTC COT | Reports | 4. UNAVAILABLE (Intraday irrelevance) |
