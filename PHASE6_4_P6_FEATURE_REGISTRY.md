# PHASE 6.4 - P6 FEATURE REGISTRY (FUNDING / POSITIONING PRESSURE)

## Conceptual Source
Perpetual Futures Funding Rate (Binance Public Data). This metric captures the cost of holding a position and acts as a proxy for the imbalance between long and short positioning pressure.

## Timestamp & Causality Semantics (MANDATORY ALIGNMENT)
Binance funding settles nominally every 8 hours (00:00, 08:00, 16:00 UTC).
- **Exact Source Timestamp Used:** The `fundingTime` provided by Binance, representing the exact millisecond the funding rate was settled.
- **Availability Semantics:** A funding rate settled at `T_fund` is considered available at any `T_decision >= T_fund`.
- **Missing-Data & Grid Alignment Behavior:** The funding series is mapped onto the 5m grid using a strict `asof` / forward-fill logic. This guarantees **LAST-KNOWN-AVAILABLE FUNDING**. No future funding rate will ever be leaked to a prior 5m candle.
- **Warmup Behavior:** First 24 hours of data are used to initialize rolling metrics (Z-score).

## Features

### 1. `funding_rate`
- **Definition:** The raw last-known-available funding rate expressed as a decimal (e.g., 0.0001 = 0.01%).
- **Causality:** Forward-filled from the most recent `T_fund <= T_decision`.

### 2. `funding_rate_zscore_1d`
- **Definition:** Rolling 24-hour Z-Score of the `funding_rate`.
- **Formula:** `(funding_rate - rolling_mean(funding_rate, 288)) / rolling_std(funding_rate, 288)`
- **Zero-Variance Behavior:** If standard deviation is 0 (funding rate was completely flat for 24 hours), output 0.0.
- **Current Observation Norm:** The current observation *is* included in the rolling window to prevent leakage of future normalization.

### 3. `funding_rate_change_8h`
- **Definition:** The absolute change in the funding rate compared to 8 hours prior.
- **Formula:** `funding_rate(T) - funding_rate(T - 96)` (where 96 is the 5m index offset for 8 hours).

### 4. `funding_price_interaction`
- **Definition:** Interaction term combining positioning pressure with recent price momentum. Evaluates if the market is moving against the crowd paying funding.
- **Formula:** `funding_rate(T) * log_return_1h(T)`
- **Price Semantics:** `log_return_1h` is `ln(close(T) / close(T-12))`. Both funding and close are available at `T_decision`.

---
*Registry Frozen for Phase 6.4 Out-of-Sample evaluation.*
