# HISTORICAL DATA SOURCES

## 1. Classification of Features

To prevent assumption leakage, all features are classified into four transferability tiers:

1. **EXCHANGE_INDEPENDENT**: Pure mathematical transformations on normalized price (e.g., Efficiency Ratio, Momentum Z-Score). Highly transferable.
2. **CROSS_EXCHANGE_TRANSFERABLE**: Features driven by global macroeconomic flow (e.g., global Open Interest, macro Funding Rates). Transferable with minor noise.
3. **EXCHANGE_SPECIFIC**: Features tightly coupled to a specific exchange's matching engine or retail behavior (e.g., specific liquidations, minor altcoin volume).
4. **EXECUTION_VENUE_SPECIFIC**: Liquidity features dictating exact fill prices (e.g., Spread, L2 Imbalance, Visible Impact). STRICTLY non-transferable.

## 2. Binance Research Data
- **Use Case:** Deep historical research using Binance USD-M Futures.
- **Classification Hypotheses:**
  - OHLCV: `EXCHANGE_SPECIFIC_RESEARCH_SOURCE` (potentially cross-exchange transferable).
  - Open Interest: `BINANCE_SPECIFIC_RESEARCH_SOURCE` (potentially transferable to BingX).
  - Funding: `BINANCE_SPECIFIC_RESEARCH_SOURCE` (potentially transferable to BingX).
  *Note: These are hypotheses only. They must explicitly prove transferability via OOS validation in Phase 8.7 before being labeled EXCHANGE_INDEPENDENT.*
- **Availability:** 
  - 1m OHLCV: Excellent (multiple years).
  - Funding/OI: Good, but varies by asset inception date.
- **Constraint:** Binance data MUST NOT be used to simulate BingX microstructure. 

## 3. BingX Historical Data
- **Use Case:** Authoritative data for execution and `EXECUTION_VENUE_SPECIFIC` features.
- **Availability:**
  - 1m OHLCV: Available via API (subject to pagination/rate limits).
  - L2/Trades: Deep historical archives are generally unavailable publicly.
- **Constraint:** We cannot fabricate historical L2/Trades. V4 Shadow telemetry will construct this dataset organically.
