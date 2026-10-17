# Phase 7.5: Survivorship & Bias Audit

To construct a mathematically defensible broad cross-section, we must explicitly audit for structural biases that invalidate backtests.

## 1. Delisted Symbol Bias (Survivorship)
- **The Threat:** If we query Binance's `exchangeInfo` endpoint today to get the list of symbols to backtest over 2021-2023, we exclude the 334 symbols that crashed, went bankrupt, or were delisted (e.g., LUNA, SRM, FTT). A momentum or mean-reversion strategy will look artificially profitable because the dataset implicitly guarantees all chosen coins "survived" to 2024.
- **The Fix:** The raw data download MUST include the 334 delisted coins. The universe selection algorithm must process them historically exactly as it would have at the time, up until the minute they were delisted.

## 2. Listing-Date Leakage
- **The Threat:** Selecting the "Top 100 coins by 2023 Volume" and trading them in 2022. Some of those coins may have been highly illiquid in 2022 before pumping in 2023. Selecting them based on future volume is look-ahead bias.
- **The Fix:** Point-in-time liquidity filtering. A coin is only eligible on day $T$ if its rolling 30-day median volume prior to day $T$ clears a static threshold.

## 3. Look-Ahead in Beta & Normalization
- **The Threat:** Normalizing cross-sectional momentum by standardizing against the full 2-year mean/variance of a coin.
- **The Fix:** Strict reliance on `.rolling()` or `.expanding()` windows shifted by 1 period. S2 successfully implemented trailing-only Beta (`beta_24h = cov / var_btc`).

## 4. Symbol Substitution Bias
- **The Threat:** Treating `1000SHIBUSDT` and `SHIBUSDT` as the same continuous instrument without properly adjusting historical nominal prices and volumes.
- **The Fix:** Each distinct Binance ticker must be treated as a distinct instrument. If a contract is delisted and a new denomination is listed, they are separate statistical entities.

## Summary Checklist
- [x] Are delisted coins excluded from historical universe? **(Threat Identified. Must include in download.)**
- [x] Are future winners accidentally influencing historical selection? **(Threat Identified. Must use Point-in-Time selection.)**
- [x] Is there any forward-looking use of today's volume ranking? **(Threat Identified. Must enforce $T-1$ ranking.)**
